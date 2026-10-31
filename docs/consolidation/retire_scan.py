"""What the running app really loads, and what only the old roots hold (the owner's goal of 2026-10-29, "retire the 12
old engines"): an AST scan of apps/, tools/ and config/ — imports, relative imports, and string references to modules
(include('…'), import_module('…'), patch targets) — from the roots Django and Celery load: config (settings, urls,
celery, wsgi), each installed app's apps, models, admin, migrations, management commands and tasks, the restart
scripts' imports and the chain's ten engines. A module reachable only through an OLD root (the routes, tasks and
commands the goal retires, named in OLD_ROOTS) is held by the old layer alone. $0; writes engines/runs/retire-scan.json.

    bbrose_design_os/venv/bin/python docs/consolidation/retire_scan.py
"""
import ast
import json
import os
import re
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', 'bbrose_design_os'))
OUT = os.path.join(HERE, 'engines', 'runs', 'retire-scan.json')
APPS = ['core', 'pipeline', 'dashboard', 'accounts', 'dielines', 'ire', 'intelligence']
CHAIN = ['apps.dielines.geometry.engine', 'apps.dielines.registry', 'apps.dielines.geometry.trade_tuck',
         'apps.dielines.geometry.fold_check', 'apps.dielines.qualification', 'apps.dielines.geometry.counter_display',
         'apps.dielines.exporters.counter_display_files', 'apps.pipeline.services.round_designer',
         'apps.pipeline.services.round_flow', 'apps.pipeline.services.round_calls',
         'apps.pipeline.services.spend_reservation', 'apps.pipeline.services.round_files_gate',
         'apps.pipeline.services.round_files_faces', 'apps.pipeline.services.round_files_export',
         'apps.pipeline.services.product_drawing']
HELD = {
    '3 carton choosers': r'apps\.dielines\.geometry\.(ecma_ste|opposed_tuck|side_seam)$',
    '9 carton exporters': r'apps\.dielines\.(exporters\.(artwork_layers|label_layout)|services\.export_service)$',
    '20 designers eye': r'apps\.pipeline\.services\.designers_eye$',
    '21 tavily': r'apps\.pipeline\.services\.web_research_tavily$',
    '22 web research': r'apps\.pipeline\.services\.web_research$',
    '23 trend board': r'apps\.pipeline\.services\.trend_board$',
    '24 library retrieval': r'apps\.(pipeline\.services|ire)\.materials_retrieval$',
    '49 font_pool': r'apps\.ire\.font_pool$',
    '51 tracers': r'apps\.pipeline\.services\.(line_art|flat_motif)$',
    '53 IRE composer': r'apps\.ire\.(compose(_\w+)?|composer_vocabulary|emitters(\.\w+)*)$',
    '54 native_handoff': r'apps\.pipeline\.services\.native_handoff$',
    '57 palette M-series': r'apps\.pipeline\.services\.palette_\w+$',
}


def modules():
    found = {}
    for base in ('apps', 'tools', 'config'):
        for folder, dirs, files in os.walk(os.path.join(ROOT, base)):
            dirs[:] = [d for d in dirs if d not in ('tests', '__pycache__', 'archive', 'node_modules')]
            for name in files:
                if name.endswith('.py') and not name.startswith('test_'):
                    path = os.path.join(folder, name)
                    dotted = os.path.relpath(path, ROOT)[:-3].replace(os.sep, '.')
                    found[dotted[:-9] if dotted.endswith('.__init__') else dotted] = path
    return found


def edges(name, path, known):
    tree = ast.parse(open(path).read())
    package = name if path.endswith('__init__.py') else name.rsplit('.', 1)[0]
    out = set()
    # a task's registered name (shared_task(name='apps.pipeline.tasks.x')) is a label, not a module reference
    labels = {id(kw.value) for node in ast.walk(tree) if isinstance(node, ast.Call) for kw in node.keywords if kw.arg == 'name'}
    for node in ast.walk(tree):
        if id(node) in labels:
            continue
        targets = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = package.split('.')
                base = '.'.join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
            targets = [base] + [base + '.' + alias.name for alias in node.names]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(('apps.', 'tools.')):
            text = node.value
            targets = [text, text.rsplit('.', 1)[0], text.rsplit('.', 2)[0]]
        for target in targets:
            while target and target not in known and '.' in target:
                target = target.rsplit('.', 1)[0]
            if target in known and target != name:
                out.add(target)
    return out


def roots(known):
    out = {'config.settings', 'config.urls', 'config.celery', 'config.wsgi'}
    for app in APPS:
        for name in known:
            parts = name.split('.')
            if parts[:2] != ['apps', app]:
                continue
            tail = parts[2:]
            if tail in ([], ['apps'], ['models'], ['admin'], ['tasks'], ['signals'], ['urls']) or tail[:1] in (['migrations'], ['models']) \
                    or tail[:2] == ['management', 'commands']:
                out.add(name)
    out.update(name for name in CHAIN if name in known)
    for script in ('restart_worker.sh', 'restart_site.sh'):
        text = open(os.path.join(ROOT, 'tools', script)).read()
        out.update(m for m in re.findall(r'from (apps\.[\w.]+) import', text) if m in known)
    return out


known = modules()
graph = {name: edges(name, path, known) for name, path in known.items()}
#: the roots the goal retires — the old task API, the old pages, the old ARIA pipeline's tasks, signals and commands —
#: given as file names; a module only they reach is held by the old layer alone
CUT = json.load(open(os.path.join(HERE, 'retire_roots.json')))
OLD_ROOTS, NEW_ROOTS = CUT['old_roots'], CUT['new_roots']


def reach(starts, blocked=()):
    seen, queue, via = set(), deque(), {}
    for start in starts:
        if start in known and start not in blocked:
            seen.add(start)
            queue.append(start)
            via[start] = start
    while queue:
        name = queue.popleft()
        for target in graph[name]:
            if target not in seen and target not in blocked:
                seen.add(target)
                via[target] = via[name]
                queue.append(target)
    return seen, via


all_roots = roots(known)
everything, _ = reach(all_roots)
kept, kept_via = reach((all_roots - set(OLD_ROOTS)) | set(NEW_ROOTS), blocked=set(OLD_ROOTS))
held_of = {name: label for name in known for label, rx in HELD.items() if re.match(rx, name)}
rows = {}
for name in sorted(known):
    if name not in everything:
        verdict = 'loaded by nothing'
    elif name in kept:
        verdict = 'kept (reached from %s)' % kept_via[name]
    else:
        verdict = 'old only: to archive with its old engine'
    rows[name] = {'verdict': verdict, 'engine': held_of.get(name, ''), 'imports_held': sorted(
        held_of[target] for target in graph[name] if target in held_of)}
summary = defaultdict(int)
for row in rows.values():
    summary[row['verdict'].split(' (')[0]] += 1
kept_held = sorted({held_of[n] for n in kept if n in held_of})
json.dump({'schema': 'retire_scan/1', 'old_roots': OLD_ROOTS, 'new_roots': NEW_ROOTS, 'summary': dict(summary),
           'held_engines_still_kept': kept_held, 'modules': rows}, open(OUT, 'w'), indent=1)
print(json.dumps(dict(summary)), 'held engines still kept:', kept_held)
