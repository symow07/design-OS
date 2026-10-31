"""Day 7 §7: the two unbound surfaces, composed from D1's grammar as revision 2 realised it — header.back (the back of the
header board: the mark and the name only, centred, on the same field) and base.front (the front face of the base board:
the field strip continued below the lip, nothing else). Each face gets the Day 6 package (graph, spec, SVG, PDF, PDF-
compatible AI, PNG, native AI + validation through day6_native) under docs/audit/day-7/surfaces/, bound in its own
surface-bindings.json with revision 2 as parent. Composed faces: no source element is measured, so no fidelity instrument
applies; the record says so. Nothing of Day 6 is rewritten.
"""
from pathlib import Path
import copy, datetime, json, shutil
import fitz
from . import fidelity_assets as fa, fidelity_master as fm, day5_master as dm
from . import day6_surfaces as d6s
from .day6_measurement import ROOT as DAY6, write

OUT = fa.ROOT / 'docs/audit/day-7/surfaces'
R2 = DAY6 / 'stand/surfaces-r2'
HEADER_W, HEADER_H = 180.0, 100.0
BASE_W, BASE_H = 180.0, 6.0           # the base board's front face: 180 mm wide, one board thickness (6 mm, cut-layout record)
BASE_OFFSET = 220.0                   # the strip continues below riser 1 (214–220): the base face sits at 220–226
NAME_IDS = ('SUN', 'REPAIR', 'SERUM', 'arabic')   # the name, bilingual; the benefit line is not the name
MARK_IDS = ('logo', 'name_rule')


def field_for(global_field, w, offset):
    field = copy.deepcopy(global_field)
    for endpoint in ('start_mm', 'end_mm'):
        field[endpoint] = [field[endpoint][0] * w / 180, field[endpoint][1] - offset]
    return field


def header_back(m, global_field):
    face = m['faces'][0]; assert face['surface_id'] == 'header.front'
    kept = [e for e in face['elements'] if e['id'] in MARK_IDS or (e.get('copy') and e['id'] in NAME_IDS)]
    x0 = min(e['bbox_mm'][0] for e in kept); x1 = max(e['bbox_mm'][2] for e in kept); shift = HEADER_W / 2 - (x0 + x1) / 2
    elements = []
    for e in kept:
        e = copy.deepcopy(e); a, b, c, d = e['bbox_mm']; e['bbox_mm'] = [a + shift, b, c + shift, d]; elements.append(e)
    lines = [d6s.line_graph(e, HEADER_H) for e in elements if e.get('copy')]
    marks = [e for e in elements if not e.get('copy')]
    graph = {'surface_id': 'header.back', 'width_mm': HEADER_W, 'height_mm': HEADER_H, 'lines': lines, 'elements': marks,
             'field': field_for(global_field, HEADER_W, 0.0), 'device_roles': []}
    return graph, {'composition': 'the mark and the name of the front (logo, name rule, SUN, REPAIR, SERUM, the Arabic name) at the front\'s measured sizes and '
                   'vertical positions, centred on the face (shift %.2f mm); the front\'s field at offset 0; no device on the back' % shift, 'shift_mm': round(shift, 3),
                   'left_out': ['benefit (Revive + Smooth)', 'the swoosh device']}


def base_front(global_field):
    graph = {'surface_id': 'base.front', 'width_mm': BASE_W, 'height_mm': BASE_H, 'lines': [], 'elements': [],
             'field': field_for(global_field, BASE_W, BASE_OFFSET), 'device_roles': []}
    return graph, {'composition': 'the front strip\'s field continued at offset %.0f mm (below riser 1); no element, no device (the posed device ends at the strip\'s 220 mm)' % BASE_OFFSET}


def package(folder, graph, spec):
    folder.mkdir(parents=True); assets = folder / 'assets'; assets.mkdir()
    for r, p in dm.fonts().items():
        shutil.copyfile(p, assets / p.name); shutil.copyfile(dm.ROOT / 'master/assets' / (r + '-OFL.txt'), assets / (r + '-OFL.txt'))
    shutil.copyfile(fm.LOGO, assets / 'bbrose-logo.svg'); write(folder / 'design-spec.json', spec); write(folder / 'design-graph.json', graph)
    (folder / 'artwork.svg').write_bytes(d6s.svg(graph)); (folder / 'native-vectors.svg').write_bytes(d6s.svg(graph, vectors_only=True))
    d6s.emit_pdf(graph, folder / 'artwork.pdf'); d6s.emit_pdf(graph, folder / 'native-vectors.pdf', vectors_only=True)
    shutil.copyfile(folder / 'artwork.pdf', folder / 'artwork-pdf-compatible.ai')
    with fitz.open(folder / 'artwork.pdf') as doc:
        doc[0].get_pixmap(dpi=300, alpha=False).save(folder / 'artwork.png')


def build(destination=OUT, *, native=True):
    dst = Path(destination); dst.mkdir(parents=True, exist_ok=False)
    m = json.loads((DAY6 / 'concept-D1-measurement.json').read_text()); fit = json.loads((R2 / 'field-fit.json').read_text())
    parent = json.loads((R2 / 'surface-bindings.json').read_text()); parent_sha = fa.sha(R2 / 'surface-bindings.json')
    fonts = {r: {'filename': p.name, 'sha256': fa.sha(p), 'family': fm.font_data(r, dm.fonts())['family'], 'postscript': fm.font_data(r, dm.fonts())['postscript']}
             for r, p in dm.fonts().items()}
    specs = []
    for graph, how in (header_back(m, fit['field']), base_front(fit['field'])):
        identity = graph['surface_id']
        spec = {'schema_version': 'surface_spec/day7-1', 'revision': 'day7-1', 'surface_id': identity, 'graph': graph, 'parent_bindings_sha256': parent_sha,
                'parent_revision': parent.get('revision'), 'composition': how, 'measurement_sha256': fa.sha(DAY6 / 'concept-D1-measurement.json'),
                'field_fit_sha256': fa.sha(R2 / 'field-fit.json'), 'source_status': 'composed from D1\'s grammar (revision 2 field, front elements); not measured',
                'deviations': [], 'review_state': 'designer_review', 'production_ready': False, 'fonts': fonts}
        package(dst / identity, graph, spec)
        specs.append({'surface_id': identity, 'size_mm': [graph['width_mm'], graph['height_mm']], 'spec_hash': fm.digest(spec), 'pdf_sha256': fa.sha(dst / identity / 'artwork.pdf'),
                      'source_status': spec['source_status']})
    write(dst / 'surface-bindings.json', {'schema': 'day7_surface_bindings/1', 'revision': 'day7-1', 'parent_bindings_sha256': parent_sha, 'parent_revision': parent.get('revision'),
                                          'surfaces': specs, 'review_state': 'designer_review', 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                          'not_done': ['render (the Day 6 scene models the seven bound faces only)', 'cut layout ARTWORK layer (no skin part exists for these faces)',
                                                       'Illustrator compare (follows the cut layout)'],
                                          'fidelity': 'composed faces: no source element is measured, so the per-surface instrument does not apply'})
    results = {}
    if native:
        from . import day6_native
        for s in specs:
            results[s['surface_id']] = day6_native.build(dst / s['surface_id'])
    return specs, results


if __name__ == '__main__':
    import sys
    specs, results = build(native='--no-native' not in sys.argv)
    print(json.dumps({'surfaces': specs, 'native': {k: {'passed': v.get('passed'), 'failed_checks': v.get('failed_checks')} for k, v in results.items()}}, ensure_ascii=False))


def text_audit(destination=OUT):
    """TRACED_TEXT for the two faces through the Day 6 auditor's own pieces: positive controls on the revision-2 header
    (the auditor's control lines), each Day 7 face inspected live by glyph, font and position in every format, the negative
    control; the report beside the faces. The seven Day 6 faces keep their own revision-2 audit."""
    from . import day6_text_audit as ta
    dst = Path(destination); audit = dst / 'text-audit'; audit.mkdir(exist_ok=True); data = ta.tessdata(audit)
    controls, _header_live = ta.positive_controls(R2 / 'header.front', audit, data)
    passed = len(controls) == len(ta.CONTROL_LINES) and all(c['detected'] for c in controls)
    surfaces = {sid: ta.inspect_surface(dst / sid, data=data, controls_passed=passed) for sid in ('header.back', 'base.front')}
    negative = ta.negative_control(R2 / 'header.front', audit, data)
    summary = {k: {'passed': v['passed'], 'state': v['state'], 'copy_lines': v['copy_lines'], 'formats': {f: x['passed'] for f, x in v['formats'].items()},
                   'package_complete': v['package']['complete'], 'native_validation_passed': v['package']['native_validation_passed'], 'f7_rule_met': v['f7_rule_met']}
               for k, v in surfaces.items()}
    report = {'code': 'TRACED_TEXT', 'scope': 'Day 7 §7: the two composed faces header.back and base.front (F7; §2.2 package rule)', 'revision': 'day7-1',
              'surfaces_root': str(dst.relative_to(fa.ROOT)), 'positive_controls': controls, 'positive_controls_passed': passed, 'surfaces': summary,
              'negative_controls': [negative], 'negative_controls_failed_as_required': negative['failed_as_required'],
              'state': 'passed' if passed and all(v['passed'] for v in surfaces.values()) and negative['failed_as_required'] else 'failed_or_unverified',
              'f7_package_rule_met': all(v['f7_rule_met'] for v in surfaces.values()),
              'controls_source': 'revision-2 header.front (the Day 6 auditor\'s control lines SUN and the Arabic name)'}
    write(dst / 'TRACED_TEXT.json', report); return report
