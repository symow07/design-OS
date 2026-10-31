"""Every part moved into a chain engine, compared with its donor: the function's (or class's, or constant's) source
in the donor file as archived (archive/consolidation/<job>/merged/, moved there unchanged by git mv) or as it stood at
26db887 (the donors still in apps then), against the same name in its target now. Identical text means identical
output on any input. $0; writes quality/runs/moved-parts.json.

    bbrose_design_os/venv/bin/python docs/consolidation/quality/moved_parts.py
"""
import ast
import difflib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
APPS = 'bbrose_design_os/apps/'
SV = APPS + 'pipeline/services/'
DL = APPS + 'dielines/'
A = 'archive/consolidation/'
#: (engine, target file, donor source: an archive path, or 'git:<rev>:<path>', names moved)
MOVES = [
    ('round_designer', SV + 'round_designer.py', 'git:26db887:' + SV + 'web_research_tavily.py', ['TavilySearchConnector']),
    ('round_designer', SV + 'round_designer.py', A + 'boards/merged/round_ideas_brief.py', ['CONTRACT']),
    ('round_designer', SV + 'round_designer.py', 'git:26db887:' + SV + 'round_ideas.py', ['COPY_START', 'COPY_END', '_line', '_validation', 'read']),
    ('round_flow', SV + 'round_flow.py', 'git:26db887:' + SV + 'round_ideas.py', ['record_break']),
    ('round_calls', SV + 'round_calls.py', A + 'paid-calls/merged/round_ideas_calls.py', ['IdeasContext']),
    ('round_calls', SV + 'round_calls.py', A + 'paid-calls/merged/image_guard.py', ['check', 'denylist', 'competitor_in']),
    ('round_calls', SV + 'round_calls.py', 'git:26db887:' + SV + 'round_balm_calls.py', ['parse_response_text']),
    ('round_calls', SV + 'round_calls.py', 'git:26db887:' + APPS + 'pipeline/agents/image_producer.py', ['download_image_bytes']),
    ('round_files_gate', SV + 'round_files_gate.py', A + 'face-gate/merged/round_files_flow.py', ['retain_failure']),
    ('round_files_gate', SV + 'round_files_gate.py', A + 'face-gate/merged/round_files_job.py', ['digest']),
    ('round_files_gate', SV + 'round_files_gate.py', A + 'die-solving/merged/round_files_stand.py', ['build_stand']),
    ('round_files_faces', SV + 'round_files_faces.py', 'git:26db887:' + SV + 'zilal_tray.py', ['turn', 'face_mm_size', 'upright_polygon', 'K']),
    ('round_files_faces', SV + 'round_files_faces.py', 'git:26db887:' + SV + 'lid_master.py', ['srgb_to_lab', 'delta_e00']),
    ('round_files_export', SV + 'round_files_export.py', 'git:26db887:' + SV + 'round_balm_master.py', ['glyph_metrics', 'shaped', 'FONT_PATHS', 'rgb', 'set_layers', 'raster']),
    ('counter_display', DL + 'geometry/counter_display.py', A + 'die-solving/merged/round_files_stand.py', ['solve_stand', 'stand_layout', 'observed_row_placement']),
    ('counter_display_files', DL + 'exporters/counter_display_files.py', A + 'die-writing/merged/pdf_layers.py', ['begin', 'end', 'layers_of']),
    ('counter_display_files', DL + 'exporters/counter_display_files.py', A + 'cartons/merged/production_pdf.py', ['_resolve_fonts', '_resolve_arabic_font', '_resolve_arabic_bold_font']),
    ('counter_display_files', DL + 'exporters/counter_display_files.py', A + 'cartons/merged/svg_exporter.py', ['write_svg']),
]


def source(spec):
    if spec.startswith('git:'):
        _, rev, path = spec.split(':', 2)
        return subprocess.run(['git', 'show', '%s:%s' % (rev, path)], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return (REPO / spec).read_text()


def parts(text):
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for name in names:
            out[name] = ast.get_source_segment(text, node)
    return out


rows, summary = [], {}
for engine, target, donor, names in MOVES:
    try:
        before = parts(source(donor))
    except subprocess.CalledProcessError as exc:
        before = {}
    after = parts((REPO / target).read_text())
    for name in names:
        a, b = before.get(name), after.get(name)
        state = ('absent in donor' if a is None else 'absent in target' if b is None else
                 'identical' if a == b else 'changed')
        changed = None
        if state == 'changed':
            al, bl = a.splitlines(), b.splitlines()
            diff = [line for line in difflib.unified_diff(al, bl, lineterm='', n=0)
                    if line[:1] in '+-' and not line.startswith(('+++', '---'))]
            changed = {'donor_lines': len(al), 'target_lines': len(bl),
                       'removed': [line[1:].strip()[:110] for line in diff if line.startswith('-')],
                       'added': [line[1:].strip()[:110] for line in diff if line.startswith('+')]}
        rows.append({'engine': engine, 'name': name, 'donor': donor, 'target': target, 'state': state, 'changed': changed})
        summary.setdefault(engine, {}).setdefault(state, 0)
        summary[engine][state] += 1
out = REPO / 'docs/consolidation/quality/runs/moved-parts.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'schema': 'consolidation_moved_parts/1', 'summary': summary, 'parts': rows}, indent=1) + '\n')
print(json.dumps(summary, indent=1))
for row in rows:
    if row['state'] != 'identical':
        print(row['engine'], row['name'], row['state'], row['changed'])
