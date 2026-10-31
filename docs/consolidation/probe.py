"""The engine cards' runs (the owner's consolidation, 2026-10-28, step 2): one real run per row of docs/ENGINE_MAP.md.

Each probe calls the engine's own entry functions on a current input (round 3's brief, die, picked picture or saved
replies, copied into a scratch folder first; never the round's own folder) or on its own fixture, and returns numbers;
files it writes go to the run folder. $0: the provider keys are blanked and every socket that is not loopback is
refused before any probe runs.

    bbrose_design_os/venv/bin/python docs/consolidation/probe.py <row> [<row> ...] --out <folder>

writes <folder>/<row>/ (the files) and docs/consolidation/engines/runs/<row>.json (what came out)."""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / 'bbrose_design_os'
ROUND3 = REPO / 'docs/rounds/lip-gloss-product-and-counter-stand-9634b86f91'
RUNS = Path(__file__).resolve().parent / 'engines' / 'runs'
PY = APP / 'venv/bin/python'

for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'WEB_SEARCH_API_KEY', 'TAVILY_API_KEY'):
    os.environ[key] = ''
_connect = socket.socket.connect


def _guarded(self, address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and (host.startswith('127.') or host in ('localhost', '::1') or host.startswith('/')):
        return _connect(self, address, *args, **kwargs)
    if self.family == socket.AF_UNIX:
        return _connect(self, address, *args, **kwargs)
    raise ConnectionRefusedError('probe: outbound connection refused (%r)' % (address,))


socket.socket.connect = _guarded


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup_django():
    sys.path.insert(0, str(APP))
    os.chdir(APP)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()


def round3_copy(out):
    """Round 3's records the probes read (brief, pick, stand, flat template, faces' records), copied; never written."""
    dest = out / 'round3'
    if not dest.exists():
        for rel in ('brief.json', 'pick.json', 'research.json', 'library.json', 'taste.json', 'board-pick.json',
                    'files/inputs.json', 'files/stand.json', 'files/inspection.json', 'files-copy.json', 'files/source.png',
                    'research.json', 'publication.json', 'handoff.json', 'files/calls.jsonl', 'files/image-calls.jsonl',
                    'files/reading-call.json', 'files/reading-call.response-0.json', 'files/faces-claim.json',
                    'files/flat/template.json', 'files/flat/template.png', 'files/flat/sheet.png', 'files/flat/owner.npy',
                    'files/stand/stand-die.json', 'files/stand/stand-geometry.json'):
            src = ROUND3 / rel
            if src.exists():
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / rel)
        for rel in ('files/faces', 'designs/g1', 'boards/g2'):
            if (ROUND3 / rel).exists():
                shutil.copytree(ROUND3 / rel, dest / rel, dirs_exist_ok=True)
    return dest


def pytest_counts(*targets, k=None, timeout=900):
    """The engine's own tests: counts of passed / failed / skipped and the seconds taken."""
    args = [str(PY), '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp',
            str(Path(os.environ['PROBE_OUT']) / '_pytest'), *targets]
    if k:
        args += ['-k', k]
    start = time.time()
    run = subprocess.run(args, cwd=APP, capture_output=True, text=True, timeout=timeout)
    tail = [line for line in run.stdout.splitlines() if line.strip()][-1:] or ['']
    failed = [line.split(' ', 1)[1] for line in run.stdout.splitlines() if line.startswith('FAILED ')]
    return {'tests': list(targets), 'k': k, 'summary': tail[0], 'failed': failed[:20], 'seconds': round(time.time() - start, 1)}


PROBES = {}


def probe(n):
    def wrap(fn):
        PROBES[n] = fn
        return fn
    return wrap


def main(argv):
    out = Path(argv[argv.index('--out') + 1])
    rows = [int(a) for a in argv if a.isdigit()]
    os.environ['PROBE_OUT'] = str(out)
    RUNS.mkdir(parents=True, exist_ok=True)
    setup_django()
    import probes  # noqa: F401  (the probe functions register themselves)
    for n in rows:
        folder = out / ('%02d' % n)
        folder.mkdir(parents=True, exist_ok=True)
        start = time.time()
        try:
            result = {'row': n, 'ok': True, 'result': PROBES[n](folder, out)}
        except Exception as error:
            result = {'row': n, 'ok': False, 'error': '%s: %s' % (type(error).__name__, error),
                      'trace': traceback.format_exc().splitlines()[-8:]}
        result['seconds'] = round(time.time() - start, 1)
        result['files'] = sorted(str(p.relative_to(out)) for p in folder.rglob('*') if p.is_file())[:40]
        (RUNS / ('%02d.json' % n)).write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str) + '\n')
        print(n, 'ok' if result['ok'] else 'ERROR ' + result['error'][:200], result['seconds'], 's')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main(sys.argv[1:])
