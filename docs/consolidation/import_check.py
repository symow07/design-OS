"""Imports every module under bbrose_design_os/apps and config (tests and migrations excepted) and lists the ones that
fail; with --baseline <file>, fails only on a module that was not already failing there.

    bbrose_design_os/venv/bin/python docs/consolidation/import_check.py [--write <file>] [--baseline <file>]"""
import importlib
import json
import os
import sys
import traceback
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / 'bbrose_design_os'
sys.path.insert(0, str(APP))
os.chdir(APP)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402

django.setup()
names = []
for base in ('apps', 'config'):
    for path in sorted((APP / base).rglob('*.py')):
        rel = path.relative_to(APP)
        if any(part in ('tests', 'migrations', '__pycache__') for part in rel.parts) or rel.name.startswith('test'):
            continue
        name = '.'.join(rel.with_suffix('').parts)
        names.append(name[:-9] if name.endswith('.__init__') else name)
failed = {}
for name in names:
    try:
        importlib.import_module(name)
    except BaseException as error:  # a module that raises SystemExit on import is a failure too
        failed[name] = '%s: %s' % (type(error).__name__, str(error)[:160])
print('modules %d · failing %d' % (len(names), len(failed)))
args = sys.argv[1:]
if '--write' in args:
    Path(args[args.index('--write') + 1]).write_text(json.dumps(failed, indent=1) + '\n')
if '--baseline' in args:
    before = json.loads(Path(args[args.index('--baseline') + 1]).read_text())
    new = {k: v for k, v in failed.items() if k not in before}
    for k, v in new.items():
        print('NEW FAILURE', k, v)
    sys.exit(1 if new else 0)
for k, v in failed.items():
    print('  ', k, v)
