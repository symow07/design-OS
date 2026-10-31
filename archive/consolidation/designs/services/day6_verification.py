"""Day 6 release verification record: source identity, artifact hashes, test groups, prior days untouched."""
from pathlib import Path
import datetime, hashlib, json, subprocess, xml.etree.ElementTree as ET
from . import fidelity_assets as fa

ROOT = fa.ROOT
APP = fa.APP
DAY = ROOT / 'docs/audit/day-6'
PRIOR = ['docs/audit/day-1', 'docs/audit/day-2', 'docs/audit/day-3', 'docs/audit/day-4', 'docs/audit/day-5',
         'OWNER_BLOCKER_CLEARANCE.md', 'OWNER_REVIEW_QUEUE.md', 'CLAUDE.md', '.claude']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def source_hashes():
    files = sorted(p for folder in ('apps', 'tools', 'config') for p in (APP / folder).rglob('*.py') if '__pycache__' not in p.parts)
    return {str(p.relative_to(APP)): sha(p) for p in files}


def artifact_manifest(folder=DAY):
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(folder).rglob('*')) if p.is_file()}


def prior_days_unchanged(baseline='rescue-day-5'):
    changed = git('diff', '--name-only', baseline, 'HEAD', '--', *PRIOR).splitlines()
    return {'baseline': baseline, 'paths': PRIOR, 'changed': changed, 'unchanged': not changed}


def junit_group(label, xml_path, command):
    """Counts read from the JUnit file pytest wrote; subtests are separate records."""
    root = ET.parse(xml_path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root)
    total = sum(int(s.get('tests')) for s in suites)
    failures = sum(int(s.get('failures')) for s in suites); errors = sum(int(s.get('errors')) for s in suites)
    skipped = sum(int(s.get('skipped')) for s in suites); seconds = round(sum(float(s.get('time')) for s in suites), 2)
    failed = [c.get('classname') + '::' + c.get('name') for s in suites for c in s.iter('testcase')
              if c.find('failure') is not None or c.find('error') is not None]
    return {'group': label, 'tests': total, 'passed': total - failures - errors - skipped, 'failures': failures,
            'errors': errors, 'skipped': skipped, 'seconds': seconds, 'failed_cases': failed, 'command': command,
            'junit_sha256': sha(xml_path), 'junit': str(Path(xml_path))}


def json_or_absent(relative):
    path = ROOT / relative
    return json.loads(path.read_text()) if path.exists() else {'absent': relative}


def build(*, groups, entry_commit, takeover_commit, release_tag='rescue-day-6', baseline_tag='rescue-day-5', notes):
    record = {'schema': 'day6_release_verification/1', 'day': 6, 'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'software_verified_designer_review', 'entry_commit': entry_commit, 'takeover_commit': takeover_commit,
              'head': git('rev-parse', 'HEAD'), 'baseline_tag': baseline_tag, 'release_tag': release_tag,
              'builder': 'Claude Code (D-D6-5); Codex work inherited at usage cutoff', 'creative_acceptance': False,
              'source_hashes': source_hashes(), 'artifact_manifest': artifact_manifest(),
              'prior_days_and_owner_files_unchanged': prior_days_unchanged(baseline_tag), 'test_groups': groups,
              'counts_overlap': True, 'migration': json_or_absent('docs/audit/day-6/library/migration-proof.json'),
              'migration_diagnosis': {k: v for k, v in json_or_absent('docs/audit/day-6/library/migration-diagnosis.json').items() if k != 'first_20'},
              'reconciliation': json_or_absent('docs/audit/day-6/library/post-migration-reconciliation.json'),
              'surfaces_fidelity': json_or_absent('docs/audit/day-6/stand/surfaces/fidelity-summary.json'),
              'negative_control_day4': json_or_absent('docs/audit/day-6/stand/surfaces/negative-control-day4.json'),
              'traced_text': json_or_absent('docs/audit/day-6/stand/text-audit/TRACED_TEXT.json'),
              'render_determinism': json_or_absent('docs/audit/day-6/stand/render/determinism.json'),
              'render_checks': json_or_absent('docs/audit/day-6/stand/render/checks/checks.json'),
              'sightlines': json_or_absent('docs/audit/day-6/stand/sightlines.json'),
              'cut_layout_native_compare': json_or_absent('docs/audit/day-6/cut-layout/native-compare.json'),
              'bottle_revision_4': json_or_absent('docs/audit/day-6/bottle/revision-4/fidelity-check.json'),
              'spend': json_or_absent('docs/audit/day-6/spend.json'), 'publication': json_or_absent('docs/audit/day-6/publication.json'),
              'notes': notes}
    (DAY / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record
