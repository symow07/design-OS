"""Who imports the 12 held engines (docs/ENGINE_MAP.md, "Held"): an AST scan of live code — apps/ and tools/, no
tests, no migrations, no archive — each importer classed as a chain engine, another held engine, or other live code.
$0; writes engines/runs/held-importers.json.

    bbrose_design_os/venv/bin/python docs/consolidation/held_importers.py
"""
import ast, json, os, re, sys
from collections import defaultdict
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bbrose_design_os')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engines', 'runs', 'held-importers.json')
mods = {}
for base in ('apps', 'tools'):
    for dp, dn, fn in os.walk(os.path.join(ROOT, base)):
        dn[:] = [d for d in dn if d not in ('tests', 'migrations', '__pycache__', 'archive')]
        for f in fn:
            if f.endswith('.py') and not f.startswith('test_'):
                path = os.path.join(dp, f)
                rel = os.path.relpath(path, ROOT)[:-3].replace(os.sep, '.')
                mods[rel[:-9] if rel.endswith('.__init__') else rel] = path
def imports(name, path):
    tree = ast.parse(open(path).read())
    pkg = name if path.endswith('__init__.py') else name.rsplit('.', 1)[0]
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = pkg.split('.')
                base = '.'.join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
            out.add(base)
            out |= {base + '.' + a.name for a in node.names}
        elif isinstance(node, ast.Call) and getattr(node.func, 'attr', getattr(node.func, 'id', '')) in ('import_module',):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                out.add(node.args[0].value)
    return {m for m in out if m in mods}
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
CHAIN = r'apps\.(dielines\.(geometry\.(engine|registry|trade_tuck|fold_check|counter_display)|registry|qualification(\.\w+)*|exporters\.counter_display_files)|pipeline\.services\.(round_designer|round_flow|round_calls|spend_reservation|round_files_gate|round_files_faces|round_files_export|product_drawing))$'
held_of = {m: k for m in mods for k, rx in HELD.items() if re.match(rx, m)}
graph = {m: imports(m, p) for m, p in mods.items()}
report = {}
for engine in HELD:
    members = {m for m, k in held_of.items() if k == engine}
    by = defaultdict(set)
    for m, deps in graph.items():
        if m in members:
            continue
        for d in deps & members:
            kind = 'chain' if re.match(CHAIN, m) else 'held' if m in held_of else 'other'
            by[kind].add(m)
    report[engine] = {'modules': len(members), **{k: sorted(v) for k, v in by.items()}}
others = defaultdict(set)
for e, r in report.items():
    for m in r.get('other', []):
        others[m].add(e.split()[0])
with open(OUT, 'w') as f:
    json.dump({'schema': 'held_importers/1', 'engines': report, 'other_holders': {m: sorted(e, key=int) for m, e in sorted(others.items())}}, f, indent=1)
    f.write('\n')
for engine, r in report.items():
    print(engine, 'chain', len(r.get('chain', [])), 'held', len(r.get('held', [])), 'other', len(r.get('other', [])))
print('OTHER HOLDERS', len(others))
for m in sorted(others):
    print(' ', m, sorted(others[m], key=int))
