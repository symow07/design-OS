"""Day 7 release verification record: source identity, Day 7 artifact hashes, test groups, prior days untouched, the day's
records (previews, captions, index, fonts, mockups, surfaces, calibration, spend) — docs/audit/day-7/verification.json."""
from pathlib import Path
import datetime, json
from . import day6_verification as v6

ROOT = v6.ROOT
DAY = ROOT / 'docs/audit/day-7'
PRIOR = v6.PRIOR + ['docs/audit/day-6']


def prior_days_unchanged(baseline='rescue-day-6'):
    changed = v6.git('diff', '--name-only', baseline, 'HEAD', '--', *PRIOR).splitlines()
    decisions = v6.git('diff', '--numstat', baseline, 'HEAD', '--', 'CURRENT_DECISIONS.md').split()
    return {'baseline': baseline, 'paths': PRIOR, 'changed': changed, 'unchanged': not changed,
            'current_decisions': {'added_lines': int(decisions[0]) if decisions else 0, 'deleted_lines': int(decisions[1]) if decisions else 0,
                                  'append_only': (not decisions) or decisions[1] == '0'}}


def spend():
    import sqlite3
    db = sqlite3.connect(str(v6.APP / 'var/rescue_spend/ledger.sqlite3')); db.row_factory = sqlite3.Row
    rows = db.execute("SELECT operation, model, reserved, accounted, state FROM calls WHERE operation LIKE 'day7/%'").fetchall()
    out = {'calls': len(rows), 'reserved_usd': round(sum(r['reserved'] for r in rows) / 1e6, 6), 'accounted_usd': round(sum(r['accounted'] for r in rows) / 1e6, 6),
           'held': sum(1 for r in rows if r['state'] == 'reserved'), 'states': {}, 'by_prefix': {}}
    for r in rows:
        out['states'][r['state']] = out['states'].get(r['state'], 0) + 1
        prefix = r['operation'].rsplit('-', 1)[0]; p = out['by_prefix'].setdefault(prefix, {'calls': 0, 'accounted_usd': 0.0})
        p['calls'] += 1; p['accounted_usd'] = round(p['accounted_usd'] + r['accounted'] / 1e6, 6)
    out['allowance_usd'] = 12.0; out['model'] = sorted({r['model'] for r in rows})
    (DAY / 'spend.json').write_text(json.dumps(out, indent=2) + '\n'); return out


def build(*, groups, entry_commit, release_tag='rescue-day-7', baseline_tag='rescue-day-6', notes):
    record = {'schema': 'day7_release_verification/1', 'day': 7, 'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'software_verified_designer_review', 'entry_commit': entry_commit, 'head': v6.git('rev-parse', 'HEAD'),
              'baseline_tag': baseline_tag, 'release_tag': release_tag, 'builder': 'Claude Code (D-D6-5); D-D7-1 recorded first', 'creative_acceptance': False,
              'source_hashes': v6.source_hashes(), 'artifact_manifest': v6.artifact_manifest(DAY),
              'prior_days_and_owner_files_unchanged': prior_days_unchanged(baseline_tag), 'test_groups': groups, 'counts_overlap': True,
              'previews': v6.json_or_absent('docs/audit/day-7/library/previews-progress.json'),
              'captions': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/library/captions-progress.json').items() if k != 'batches'},
              'caption_check': (v6.json_or_absent('docs/audit/day-7/library/caption-check.json') or {}).get('summary', {'absent': 'caption-check.json'}),
              'index': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/library/materials-index.json').items() if k != 'items'},
              'fonts_excluded': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/library/fonts-excluded.json').items() if k != 'files'},
              'fonts_granted_catalogue': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/library/fonts-granted-catalogue.json').items() if k != 'items'},
              'arabic_line': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/fonts/arabic-line-comparison.json').items() if k not in ('pool', 'skipped', 'cairo_applied', 'naskh')},
              'mockups': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/mockups/mockups.json').items() if k != 'rows'},
              'surfaces': v6.json_or_absent('docs/audit/day-7/surfaces/surface-bindings.json'),
              'traced_text': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/surfaces/TRACED_TEXT.json').items() if k in ('state', 'f7_package_rule_met', 'surfaces')},
              'critic_calibration': {k: v for k, v in v6.json_or_absent('docs/audit/day-7/critic-calibration.json').items() if k in ('disagreements', 'summary')},
              'spend': spend(), 'notes': notes}
    (DAY / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record
