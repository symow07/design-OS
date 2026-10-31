"""The closure check of the consolidation: every import under bbrose_design_os/apps (at load or inside a function,
tests included) and every 'apps.…' path given to patch() must name a module that exists and, for `from X import Y`, a
name X defines. After a part moves or a row is archived, nothing may still point at its old place.

    bbrose_design_os/venv/bin/python docs/consolidation/dangling.py [--write <file>] [--baseline <file>]"""
import ast
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / 'bbrose_design_os'
files = {}
for path in sorted((APP / 'apps').rglob('*.py')):
    rel = path.relative_to(APP)
    if '__pycache__' in rel.parts or 'migrations' in rel.parts:
        continue
    name = '.'.join(rel.with_suffix('').parts)
    files[name[:-9] if name.endswith('.__init__') else name] = path
defined = {}


def names_of(module):
    if module not in defined:
        out = set()
        tree = ast.parse(files[module].read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    for n in ast.walk(target):
                        if isinstance(n, ast.Name):
                            out.add(n.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                out |= {(a.asname or a.name).split('.')[0] for a in node.names}
            elif isinstance(node, (ast.If, ast.Try)):
                for n in ast.walk(node):
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                        out.add(n.name)
                    elif isinstance(n, ast.Assign):
                        out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
                    elif isinstance(n, (ast.Import, ast.ImportFrom)):
                        out |= {(a.asname or a.name).split('.')[0] for a in n.names}
        if any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names) for n in tree.body):
            out.add('*')
        defined[module] = out
    return defined[module]


def resolve(module):
    return module in files


problems = set()
for module, path in files.items():
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError as error:
        problems.add((module, 'syntax error: %s' % error))
        continue
    package = module if path.name == '__init__.py' else module.rsplit('.', 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith('apps.') and not resolve(a.name):
                    problems.add((module, 'import %s' % a.name))
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = package.split('.')
                parts = parts[:len(parts) - (node.level - 1)]
                base = '.'.join(parts + ([base] if base else []))
            if not base.startswith('apps'):
                continue
            if not resolve(base):
                problems.add((module, 'from %s import …' % base))
                continue
            have = names_of(base)
            for a in node.names:
                if a.name == '*' or '*' in have:
                    continue
                if a.name not in have and not resolve(base + '.' + a.name):
                    problems.add((module, 'from %s import %s' % (base, a.name)))
    for m in re.finditer(r"""patch\(\s*['"](apps\.[\w.]+)['"]""", path.read_text()):
        target = m.group(1)
        mod, _, attr = target.rpartition('.')
        if resolve(target):
            continue
        if not resolve(mod) or (attr not in names_of(mod) and '*' not in names_of(mod)):
            problems.add((module, 'patch(%s)' % target))
problems = sorted(problems)
print('modules %d · dangling %d' % (len(files), len(problems)))
args = sys.argv[1:]
if '--write' in args:
    Path(args[args.index('--write') + 1]).write_text(json.dumps(problems, indent=0) + '\n')
if '--baseline' in args:
    before = {tuple(p) for p in json.loads(Path(args[args.index('--baseline') + 1]).read_text())}
    new = [p for p in problems if p not in before]
    for p in new:
        print('NEW', p[0], '→', p[1])
    sys.exit(1 if new else 0)
for p in problems[:40]:
    print('  ', p[0], '→', p[1])
