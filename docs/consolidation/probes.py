"""The probe functions, one per map row (registered on docs/consolidation/probe.py's table)."""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from __main__ import APP, REPO, ROUND3, probe, pytest_counts, round3_copy, sha


def load(path):
    return json.loads(Path(path).read_text())


def passes(reports):
    """{name: passed} of a qualification's reports."""
    return {name: bool(report.get('passed')) for name, report in reports.items()}


def deep_diff(a, b, path='', out=None, tol=1e-9):
    """Leaf paths where two JSON values differ (numbers by more than ``tol``)."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(path + '/' + str(key) + (' (missing left)' if key not in a else ' (missing right)'))
            else:
                deep_diff(a[key], b[key], path + '/' + str(key), out, tol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append('%s (length %d vs %d)' % (path, len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                deep_diff(x, y, '%s[%d]' % (path, i), out, tol)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if abs(a - b) > tol:
            out.append('%s (%r vs %r)' % (path, a, b))
    elif a != b:
        out.append('%s (%r vs %r)' % (path, str(a)[:60], str(b)[:60]))
    return out


def r3_brief(out):
    """Round 3's files brief as round_files_flow.files_brief makes it (the committed Arabic shade names of
    files-copy.json added), made an execution brief; and the picked picture's saved reading."""
    from apps.pipeline.services.round_files_job import execution_brief
    r3 = round3_copy(out)
    brief = load(r3 / 'files/inputs.json')['brief']
    names = load(r3 / 'files-copy.json').get('arabic_shade_names', {}) if (r3 / 'files-copy.json').exists() else {}
    for shade in brief['shades']:
        if not shade.get('name_arabic') and names.get(shade['name']):
            shade['name_arabic'] = names[shade['name']]
    return r3, execution_brief(brief), load(r3 / 'files/inspection.json')


def stand_in_painting(template_png, masks, dest, *, drift=(3, 2)):
    """A stand-in for a lost painting, $0: each printed face's own pixels (its mask, nothing outside it) filled with
    its own colour and a texture of lines, then the whole picture moved by ``drift`` (rows, columns) — paint the die
    must cut away where it lands off the faces, and a shift the proof must find. Labelled a stand-in wherever used."""
    template = np.asarray(Image.open(template_png).convert('RGB'))
    raw = template.copy()
    owner = masks['owner']
    colours = [(28, 40, 92), (186, 58, 74), (201, 164, 92), (90, 120, 60), (60, 90, 160), (140, 60, 120), (220, 120, 40)]
    rows = (np.arange(owner.shape[0]) % 9 == 0)[:, None] | (np.arange(owner.shape[1]) % 13 == 0)[None, :]
    for index, _name in enumerate(masks['names']):
        face = owner == index + 1
        raw[face] = colours[index % len(colours)]
        raw[face & rows] = (240, 230, 200)
    raw = np.roll(raw, drift, axis=(0, 1))
    Image.fromarray(raw).save(dest)
    return dest


# --- the dielines app ---------------------------------------------------------------------------------------------------

def carton(template, version=None, w=15.0, d=15.0, h=100.0):
    """A carton for round 3's bottle (15 × 15 × 100 mm, the brief's own sizes) drawn by the dieline engine."""
    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.validators.schema import DielineInputJSON
    payload = {'template': template, 'unit': 'mm', 'dimensions': {'width_mm': w, 'depth_mm': d, 'height_mm': h},
               'print_settings': {'bleed_mm': 3.0, 'safe_margin_mm': 4.0}, 'construction': {'glue_tab_mm': 10.0},
               'metadata': {'product_name': 'Lip Gloss', 'product_type': 'lip gloss'}}
    if version:
        payload['template_version'] = version
    return calculate_dieline(DielineInputJSON(**payload))


def coords_facts(c):
    cut = c.cut_polygon if hasattr(c, 'cut_polygon') else None
    return {'flat_mm': [round(c.flat_width_mm, 3), round(c.flat_height_mm, 3)], 'panels': len(c.panels),
            'folds': len(c.fold_lines), 'cut_area_mm2': round(cut.area, 1) if cut is not None else None}


@probe(1)
def p01(folder, out):
    """The dieline engine core: round 3's bottle carton drawn through calculate_dieline for each carton style it
    dispatches, unpinned and pinned, and validated; its own tests run."""
    from apps.dielines.exporters.svg_exporter import export_svg
    made = {}
    for template, version in (('straight_tuck_end_carton', None), ('straight_tuck_end_carton', '1.4'),
                              ('reverse_tuck_end_carton', '1.4'), ('tuck_top_auto_bottom_carton', None)):
        c = carton(template, version)
        problems = c.validate() if hasattr(c, 'validate') else None
        made['%s@%s' % (template, version or 'unpinned')] = dict(coords_facts(c), validate=problems)
    c = carton('straight_tuck_end_carton', '1.4')
    export_svg(c, 'round3-bottle-ste-1.4', str(folder))
    return {'cartons': made, 'tests': pytest_counts('apps/dielines/tests/test_geometry.py',
                                                    'apps/dielines/tests/test_trade_tuck.py')}


@probe(2)
def p02(folder, out):
    """The registry: every template id and version, the one an unpinned caller gets, the production ones."""
    from apps.dielines import registry
    rows = [{'id': t.template_id, 'version': t.version, 'production_ready': t.production_ready}
            for t in registry.all_templates()]
    current = {t: registry.resolve(t).version for t in sorted({r['id'] for r in rows})}
    pinned = registry.resolve('counter_tray_header', '1.0')
    return {'templates': len(rows), 'rows': rows, 'unpinned_gets': current,
            'production': [(t.template_id, t.version) for t in registry.production_templates()],
            'counter_tray_header_1_0': {'production_ready': pinned.production_ready},
            'tests': pytest_counts('apps/dielines/tests/test_registry.py',
                                   'apps/dielines/tests/test_template_registry_agreement.py')}


@probe(3)
def p03(folder, out):
    """The carton templates: round 3's bottle drawn on each archetype (trade tuck 1.4, ECMA STE 0.1, opposed tuck 0.1,
    Skynte side-seam 1.0) with the engine's own collision reports where it has them."""
    from apps.dielines.geometry import fold_check
    made = {}
    for template, version in (('straight_tuck_end_carton', '1.4'), ('reverse_tuck_end_carton', '1.4'),
                              ('ecma_a20_20_01_01_ste_carton', None), ('reference_opposed_tuck_carton', None),
                              ('skynte_foundation_tuck_carton', None)):
        try:
            c = carton(template, version)
            fold = fold_check.check(c)
            made[template + '@' + (version or 'current')] = dict(coords_facts(c), fold_passed=fold['passed'],
                                                                 fold_failed=fold.get('failed'))
        except Exception as error:
            made[template + '@' + (version or 'current')] = {'error': '%s: %s' % (type(error).__name__, str(error)[:300])}
    goal = {}
    for product, (w, d, h) in (('lipstick carton', (25.0, 25.0, 85.0)), ('lip balm carton', (22.0, 22.0, 78.0)),
                               ('palette box', (195.0, 125.0, 22.0))):
        for template in ('ecma_a20_20_01_01_ste_carton', 'reference_opposed_tuck_carton', 'skynte_foundation_tuck_carton',
                         'reverse_tuck_end_carton'):
            try:
                c = carton(template, '1.4' if template == 'reverse_tuck_end_carton' else None, w, d, h)
                goal['%s / %s' % (product, template)] = dict(coords_facts(c), fold_passed=fold_check.check(c)['passed'])
            except Exception as error:
                goal['%s / %s' % (product, template)] = {'error': type(error).__name__ + ': ' + str(error)[:160]}
    return {'cartons': made, 'goal_products': goal, 'tests': pytest_counts('apps/dielines/tests/test_opposed_tuck_archetype.py',
                                                    'apps/dielines/tests/test_ecma_ste_archetype.py',
                                                    'apps/dielines/tests/test_side_seam.py')}


@probe(4)
def p04(folder, out):
    """Qualification: round 3's bottle qualified on every registered adapter; fold_check on trade tuck 1.4."""
    from apps.dielines.qualification import runner
    user = {'width_mm': 15.0, 'depth_mm': 15.0, 'height_mm': 100.0, 'board_thickness_mm': 0.4, 'glue_tab_mm': 10.0,
            'bleed_mm': 3.0, 'safe_mm': 4.0}
    out_rows = {}
    for template in runner.registered_adapters():
        try:
            q = runner.qualify(dict(user), runner.adapter_for(template))
            out_rows[template] = {'supported': q.supported, 'violations': [str(v)[:120] for v in q.violations][:4]}
        except Exception as error:
            out_rows[template] = {'error': '%s: %s' % (type(error).__name__, str(error)[:200])}
    return {'qualified': out_rows, 'tests': pytest_counts('apps/dielines/tests/test_qualification_framework.py',
                                                          'apps/dielines/tests/test_opposed_tuck_qualification.py')}


@probe(5)
def p05(folder, out):
    """counter_tray_header 0.1: the Day 12 family display solved from its defaults, its die built and fold-checked; and
    the product-grid branch (solve_product_tray) solved for round 3's grid."""
    from apps.dielines.geometry import counter_tray_header as ct
    record = ct.full_record()
    die = ct.build_die(record)
    summary = ct.die_summary(die)
    fold = ct.fold_check(record, die)
    r3, brief, inspection = r3_brief(out)
    grid = ct.solve_product_tray(product_width_mm=15.0, product_depth_mm=15.0, product_height_mm=100.0, rows=3,
                                 columns=4, count=12, width_mm=110.0, depth_mm=85.0, height_mm=160.0, board_mm=1.5)
    grid_die = ct.build_product_tray_die(grid)
    grid_fold = ct.product_tray_fold_check(grid, grid_die)
    (folder / 'family-record.json').write_text(json.dumps(record, indent=1, default=str)[:400000])
    return {'family': {'schema': record.get('schema'), 'version': record.get('version'), 'sheet_mm': [die.sheet_w, die.sheet_h],
                       'parts': [p.name for p in die.parts], 'summary': str(summary)[:600],
                       'fold_passed': fold.get('passed'), 'fold_failed': [f.get('id') for f in fold.get('findings', [])
                                                                          if not f.get('ok', True)][:10]},
            'product_grid_0.1': {'schema': grid.get('schema'), 'parts': [p.name for p in grid_die.parts],
                                 'sheet_mm': [grid_die.sheet_w, grid_die.sheet_h], 'fold_passed': grid_fold.get('passed')},
            'tests': pytest_counts('apps/dielines/tests/test_counter_tray_header.py')}


@probe(6)
def p06(folder, out):
    """counter_tray_header 1.0: round 3's stand solved again exactly as the files build solves it (brief + the picked
    picture's reading) and compared with the committed record; then from the brief alone; then qualified."""
    from apps.dielines.geometry import counter_display as cd
    from apps.pipeline.services.round_files_stand import solve_stand
    r3, brief, inspection = r3_brief(out)
    committed = load(r3 / 'files/stand.json')
    again = solve_stand(brief, inspection)
    diffs = deep_diff(committed['record'], again['record'])
    alone = solve_stand(brief, None)
    q = cd.qualify(again['record'])
    die = cd.build_die(again['record'])
    (folder / 'stand-again.json').write_text(json.dumps(again['record'], indent=1, default=str))
    (folder / 'qualification.json').write_text(json.dumps(q, indent=1, default=str))
    return {'committed_vs_again': {'differing_leaves': len(diffs), 'first': diffs[:8]},
            'with_reading': {'height_mm': again['dimensions_mm']['height'], 'header_mm': again['header_mm'],
                             'holes': len(again['record']['holes']), 'sheet_mm': [die.sheet_w, die.sheet_h],
                             'parts': [p.name for p in die.parts]},
            'brief_alone': {'height_mm': alone['dimensions_mm']['height'], 'header_mm': alone['header_mm']},
            'qualification': {'passed': q['passed'], 'reports': passes(q['reports'])},
            'tests': pytest_counts('apps/dielines/tests/test_counter_display.py')}


@probe(7)
def p07(folder, out):
    """The 0.1 sheets: round 3's die written as an SVG and a layered die PDF by counter_tray_header_sheets."""
    import fitz
    from apps.dielines.exporters import counter_tray_header_sheets as sheets
    from apps.dielines.geometry import counter_display as cd
    r3, brief, inspection = r3_brief(out)
    record = load(r3 / 'files/stand.json')['record']
    die = cd.build_die(record)
    svg = sheets.write_svg(die, folder / 'die.svg')
    pdf = sheets.write_die_pdf(die, folder / 'die.pdf')
    with fitz.open(folder / 'die.pdf') as doc:
        layers = [ocg['name'] for ocg in doc.get_ocgs().values()]
        pages = len(doc)
    return {'svg_groups': svg, 'pdf_layers_written': pdf, 'pdf_pages': pages, 'pdf_ocgs': layers,
            'svg_bytes': (folder / 'die.svg').stat().st_size}


@probe(8)
def p08(folder, out):
    """The 1.0 die writer on round 3's die: every file written, the 1:1 PDF read back; the flat template made again and
    compared with the round's own; a $0 stand-in painting (drifted 3 px, spilling 6 px) settled by the die."""
    import fitz
    from apps.dielines.exporters import counter_display_files as cdf
    from apps.pipeline.services import round_files_faces as faces
    r3, brief, inspection = r3_brief(out)
    geometry = load(r3 / 'files/stand.json')
    record = geometry['record']
    die = cdf.cd.build_die(record)
    written = cdf.write_all(record, folder / 'die')
    readback = cdf.pdf_readback(folder / 'die' / 'die.pdf', die, record, [0, 0, 0, 0])
    setup = faces.flat_setup(geometry, folder / 'flat')
    same_template = sha(folder / 'flat' / 'template.png') == sha(r3 / 'files/flat/template.png')
    masks = cdf.flat_masks(die, setup['frame'])
    raw = stand_in_painting(folder / 'flat' / 'template.png', masks, folder / 'stand-in-raw.png')
    (folder / 'flat' / 'paintings' / '1').mkdir(parents=True, exist_ok=True)
    painting = faces.settle_flat(raw, folder / 'flat', folder / 'flat' / 'paintings' / '1', geometry)
    with fitz.open(folder / 'die' / 'die.pdf') as doc:
        ocgs = sorted(ocg['name'] for ocg in doc.get_ocgs().values())
    proof = painting['proof']
    return {'files': written['files'], 'ocgs': ocgs, 'nest': str(written['nest'])[:300],
            'readback_cut_crease': {k: v for k, v in readback.items() if k in ('CUT', 'CREASE')},
            'template_same_as_round3': same_template, 'frame': {k: setup['frame'][k] for k in ('size', 'dpi_at_1to1')
                                                                 if k in setup['frame']},
            'stand_in_proof': {'registration': proof.get('registration'), 'outside': proof.get('outside'),
                               'pdf': proof.get('pdf')},
            'continuity_folds': len(painting['continuity'].get('folds', painting['continuity'])
                                    if isinstance(painting['continuity'], dict) else painting['continuity'])}


# --- helpers for the rest -----------------------------------------------------------------------------------------------

def attempt(record, name, fn):
    """Run one sub-step; its result or its error goes into ``record[name]`` (one failure never hides the rest)."""
    try:
        record[name] = fn()
    except Exception as error:
        record[name] = {'error': '%s: %s' % (type(error).__name__, str(error)[:400])}
    return record[name]


def png_facts(path):
    with Image.open(path) as image:
        return {'size_px': list(image.size), 'mode': image.mode, 'bytes': Path(path).stat().st_size, 'sha256': sha(path)[:16]}


def stand_in_flat(folder, out):
    """Round 3's die, its flat template and a settled $0 stand-in painting (row 8's method), for the rows that cut
    faces from a painting. Labelled a stand-in: round 3's two real paintings were lost to the network."""
    from apps.dielines.exporters import counter_display_files as cdf
    from apps.pipeline.services import round_files_faces as faces
    r3, brief, inspection = r3_brief(out)
    geometry = load(r3 / 'files/stand.json')
    flat = folder / 'flat'
    setup = faces.flat_setup(geometry, flat)
    die = faces.die_of(geometry)
    masks = cdf.flat_masks(die, setup['frame'])
    raw = stand_in_painting(flat / 'template.png', masks, folder / 'stand-in-raw.png')
    (flat / 'paintings' / '1').mkdir(parents=True, exist_ok=True)
    painting = dict(faces.settle_flat(raw, flat, flat / 'paintings' / '1', geometry), n=1)
    return r3, brief, inspection, geometry, die, painting


# --- the carton exporters and previews ----------------------------------------------------------------------------------

@probe(9)
def p09(folder, out):
    """The carton exporters on round 3's bottle carton (straight tuck 1.4): the SVG, the CMYK production PDF and the
    .ai copied from it; pdf_layers read back."""
    import fitz
    from apps.dielines.exporters import pdf_layers, svg_exporter, production_pdf, ai_exporter
    c = carton('straight_tuck_end_carton', '1.4')
    rec = {}
    attempt(rec, 'svg', lambda: len(svg_exporter.export_svg(c, 'carton', str(folder))))
    def pdf():
        path = production_pdf.export_production_pdf(c, 'carton', product_name='Lip Gloss', output_dir=str(folder))
        with fitz.open(path) as doc:
            return {'path': Path(path).name, 'pages': len(doc), 'ocgs': sorted(o['name'] for o in doc.get_ocgs().values()),
                    'bytes': Path(path).stat().st_size}
    attempt(rec, 'production_pdf', pdf)
    attempt(rec, 'ai_from_pdf', lambda: Path(ai_exporter.export_ai_from_production_pdf(
        str(folder / 'carton_production.pdf'), 'carton', str(folder))).name)
    attempt(rec, 'pdf_layers_of', lambda: pdf_layers.layers_of(str(folder / 'carton_production.pdf')))
    rec['tests'] = pytest_counts('apps/dielines/tests/test_svg.py', 'apps/dielines/tests/test_production_pdf.py')
    return rec


@probe(10)
def p10(folder, out):
    """The die previews on round 3's bottle carton: the four-stage folded diagnostic, the folded mockup of a flat
    design picture, and the design preview SVG."""
    from apps.dielines.exporters import folded_diagnostic, mockup_3d, design_preview
    c = carton('straight_tuck_end_carton', '1.4')
    art = folder / 'flat-design.png'
    Image.new('RGB', (int(c.flat_width_mm * 10), int(c.flat_height_mm * 10)), (28, 40, 92)).save(art)
    rec = {}
    attempt(rec, 'folded_diagnostic', lambda: png_facts(folded_diagnostic.export_folded_diagnostic(
        c, str(folder / 'folded-diagnostic.png'), None, None)))
    attempt(rec, 'folded_mockup', lambda: png_facts(mockup_3d.export_folded_mockup(c, str(art), str(folder / 'mockup.png'))))
    attempt(rec, 'design_preview_svg', lambda: len(design_preview.export_design_preview_svg(c, 'carton', str(folder), str(art))))
    rec['tests'] = pytest_counts('apps/dielines/tests/test_design_preview.py')
    return rec


# --- the ideas half -----------------------------------------------------------------------------------------------------

@probe(11)
def p11(folder, out):
    """The round designer on round 3's brief at $0: the six research queries, the library's twelve matches (against
    the round's own library.json), the die first and its template sheet, the board and design prompts' sizes."""
    from apps.pipeline.services import round_designer as rd
    r3 = round3_copy(out)
    brief = load(r3 / 'brief.json')
    rec = {}
    attempt(rec, 'queries', lambda: rd.search_queries(brief, 2026))
    def library():
        found = rd.library_matches(brief)
        saved = load(r3 / 'library.json')
        saved_rows = saved.get('matches', saved) if isinstance(saved, dict) else saved
        same = [m.get('sha256') for m in found.get('matches', found)] if isinstance(found, dict) else [m.get('sha256') for m in found]
        old = [m.get('sha256') for m in saved_rows] if isinstance(saved_rows, list) else []
        return {'matches': len(same), 'same_as_round3': same == old, 'round3_matches': len(old)}
    attempt(rec, 'library', library)
    def die():
        from apps.pipeline.services.round_files_job import execution_brief
        from apps.pipeline.services.round_files_stand import build_stand
        from apps.pipeline.services import round_files_faces as faces
        geometry = build_stand(execution_brief(brief), None, folder / 'die' / 'stand')
        setup = faces.flat_setup(geometry, folder / 'die' / 'flat')
        return {'stand_mm': geometry['dimensions_mm'], 'header_mm': geometry['header_mm'], 'frame': setup['frame'].get('size'),
                'dpi_at_1to1': setup['frame'].get('dpi_at_1to1'), 'sheet': png_facts(folder / 'die' / 'flat' / 'sheet.png')}
    attempt(rec, 'die_first_from_brief', die)
    research = load(r3 / 'research.json')
    attempt(rec, 'boards_prompt_chars', lambda: len(rd.boards_prompt(brief, research, [], library=None)))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_flow.py', k='designer')
    return rec


@probe(12)
def p12(folder, out):
    """The round state machine: its steps for round 3's designer brief, and its own tests."""
    from types import SimpleNamespace
    from apps.pipeline.services import round_flow
    r3 = round3_copy(out)
    record = SimpleNamespace(product_brief=load(r3 / 'brief.json'))
    rec = {'designer_round': round_flow.is_designer_round(record), 'steps': list(round_flow.steps_for(record))}
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_flow.py')
    return rec


@probe(13)
def p13(folder, out):
    """The twenty-design flow: its pair plan for twenty ids, and its own tests (the media round file, ideas only)."""
    from apps.pipeline.services import round_ideas
    batches = round_ideas.pair_batches()
    pairs = sum(len(b) for b in batches) if isinstance(batches, list) else None
    return {'batches': len(batches), 'pairs': pairs, 'steps': list(round_ideas.IDEAS_STEPS),
            'tests': pytest_counts('apps/pipeline/tests/test_product_round_media.py', k='ideas')}


@probe(14)
def p14(folder, out):
    """The brief contract on round 3's brief: normalised, its printed copy."""
    from apps.pipeline.services import round_ideas_brief as rib
    r3 = round3_copy(out)
    brief = load(r3 / 'brief.json')
    value = rib.normalize_ideas_brief(brief)
    return {'designer': rib.is_designer_brief(brief), 'printed_copy': rib.printed_copy(brief),
            'keys': sorted(value), 'tests': pytest_counts('apps/pipeline/tests/test_round_flow.py', k='brief')}


@probe(15)
def p15(folder, out):
    """The ideas image calls: the reservation each design and reference picture holds."""
    from apps.pipeline.services import round_ideas_calls as ric
    return {'design_image_usd': ric.design_image_estimate('x' * 4000), 'reference_image_usd':
            ric.reference_image_estimate('x' * 4000) if ric.reference_image_estimate.__code__.co_argcount == 1 else None,
            'image_attempt_cap': ric.IdeasContext.image_attempt_cap,
            'tests': pytest_counts('apps/pipeline/tests/test_round_calls.py', k='ideas or flat or design')}


@probe(16)
def p16(folder, out):
    """The paid boundary on round 3's saved replies: each saved text reply parsed again by the boundary's parser;
    the ledger's totals read; its own tests."""
    from apps.pipeline.services import round_calls, spend_reservation
    r3 = round3_copy(out)
    parsed, failed = 0, []
    for path in sorted((ROUND3).rglob('*-call.response-0.json'))[:60]:
        data = load(path)
        text = ''.join(block.get('text', '') for block in data.get('content', []) if isinstance(block, dict)) \
            if isinstance(data, dict) else ''
        if not text:
            continue
        try:
            round_calls.parse_response_text(text)
            parsed += 1
        except Exception as error:
            failed.append('%s: %s' % (path.relative_to(ROUND3), str(error)[:80]))
    rec = {'saved_replies_parsed': parsed, 'saved_replies_refused': failed[:10]}
    attempt(rec, 'ledger_totals', spend_reservation.totals)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_calls.py')
    return rec


# --- the older rounds, juries and eyes ----------------------------------------------------------------------------------

@probe(17)
def p17(folder, out):
    """The whole-object round: Round 2's lip gloss brief normalised and its panel sheet drawn ($0)."""
    from apps.pipeline.services import round_product, round_sheet
    brief = round_product.normalize_brief(round_product.lip_gloss_brief())
    rec = {'panels': len(brief.get('panels', []))}
    def sheet():
        result = round_sheet.build(brief, folder)
        return {'schema': result.get('schema'), 'files': sorted(p.name for p in folder.iterdir())[:8]}
    attempt(rec, 'sheet', sheet)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_product_round_media.py', k='not ideas')
    return rec


@probe(18)
def p18(folder, out):
    """The Round 1 jury maths: twenty ids in pair batches of nine, and a fine order from two jurors' wins."""
    from apps.pipeline.services import rank_round
    ids = ['D%d' % i for i in range(1, 21)]
    batches = rank_round.pair_batches(ids)
    return {'batches': len(batches), 'pairs': sum(len(b) for b in batches),
            'tests': pytest_counts('apps/pipeline/tests/test_round_balm.py', k='pair or invalid or rank or jury')}


@probe(19)
def p19(folder, out):
    """The J1/J2 jury: its own tests (combine, anchors, schema) — its rubric is a 190 × 120 mm lid's."""
    from apps.pipeline.services import jury
    return {'lid_what': jury.LID_WHAT[:120] if isinstance(getattr(jury, 'LID_WHAT', None), str) else None,
            'tests': pytest_counts('apps/pipeline/tests/test_day8_jury.py')}


@probe(20)
def p20(folder, out):
    """The pitch's designer's eye: round 3's 1.0 die PDF (row 8's file) rendered, two fake looks agreed."""
    from apps.pipeline.services import designers_eye as de
    rec = {}
    pdf = Path(out) / '08' / 'die' / 'die.pdf'
    attempt(rec, 'render', lambda: len(de.render(str(pdf), [0, 0, 100, 100], dpi=50)))
    a = {'matches': False, 'differences': [{'check': 'colour', 'part': 'header', 'what': 'header ring colour', 'severity': 'major'}], 'checks': {}}
    b = {'matches': False, 'differences': [{'check': 'colour', 'part': 'header', 'what': 'header ring colour', 'severity': 'minor'}], 'checks': {}}
    attempt(rec, 'agreed', lambda: de.agreed([a, b]))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_targets.py', k='designers_eye')
    return rec


@probe(26)
def p26(folder, out):
    """The Day 13 creativity check written again into a scratch folder from its nine records ($0)."""
    from apps.pipeline.services import creativity_check as cc
    rec = {}
    attempt(rec, 'build', lambda: str(cc.build(folder / 'creativity'))[:400])
    rec['written'] = sorted(p.name for p in (folder / 'creativity').rglob('*') if p.is_file())[:20] \
        if (folder / 'creativity').exists() else []
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day13_creativity.py',
                                 'apps/pipeline/tests/test_day13_creativity_page.py')
    return rec


# --- research and the library -------------------------------------------------------------------------------------------

@probe(21)
def p21(folder, out):
    """Tavily on round 3's six saved searches: each saved result normalised again ($0, no search bought)."""
    from apps.pipeline.services.web_research_tavily import TavilySearchConnector
    saved = sorted((ROUND3 / 'research' / 'tavily').glob('[0-9]*.json'))
    rec = {'saved_searches': len(saved), 'per_search': []}
    for path in saved:
        data = load(path)
        rows = data.get('results') or data.get('response', {}).get('results') or []
        rec['per_search'].append({'file': path.name, 'results': len(rows), 'query': (data.get('query') or '')[:80]})
    sources = load(ROUND3 / 'research.json').get('sources', [])
    rec['research_sources_kept'] = len(sources)
    rec['normalize'] = TavilySearchConnector.normalize('lip gloss', {'results': [{'url': 'https://a.example/x', 'title': 'T',
        'content': 'c' * 900, 'score': .5}], 'answer': 'dropped', 'images': []}) if hasattr(TavilySearchConnector, 'normalize') else None
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_2c2a_tavily.py')
    return rec


@probe(22)
def p22(folder, out):
    """The ARIA gateway on round 3's research sources: each URL normalised and checked against its policy; its search."""
    from apps.pipeline.services import web_research as wr
    sources = load(ROUND3 / 'research.json').get('sources', [])
    config = wr.gateway_config()
    allowed, refused = 0, []
    for source in sources:
        url = source.get('url') if isinstance(source, dict) else None
        if not url:
            continue
        try:
            wr.check_url_policy(wr.normalize_url(url))
            allowed += 1
        except Exception as error:
            refused.append(str(error)[:80])
    rec = {'sources': len(sources), 'policy_allowed': allowed, 'policy_refused': refused[:5]}
    attempt(rec, 'run_search', lambda: wr.run_search('lip gloss', config) if wr.run_search.__code__.co_argcount >= 2 else wr.run_search('lip gloss'))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_2c2a_web_research.py')
    return rec


@probe(23)
def p23(folder, out):
    """The trend board: its own tests (plan, pick, fetch, read are DB-bound on a design task)."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_2c2a_tavily.py', 'apps/pipeline/tests/test_container_target.py',
                                   k='trend or subject')}


@probe(24)
def p24(folder, out):
    """The library on round 3's brief: the dashboard's index searched by its words and each shade colour."""
    from apps.dashboard import materials_library as ml
    from apps.pipeline.services import materials_retrieval as mr
    brief = load(ROUND3 / 'brief.json')
    rec = {'index_rows': len(mr.index_items()) if hasattr(mr, 'index_items') else None}
    hits = {}
    for shade in brief.get('shades', []):
        attempt(hits, shade['hex'], lambda shade=shade: len(ml.search_index(q='', colour=shade['hex'])))
    attempt(hits, 'words', lambda: len(ml.search_index(q='lip gloss stand', colour='')))
    rec['search_hits'] = hits
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day7_library_golden.py')
    return rec


@probe(25)
def p25(folder, out):
    """The image guard on round 3's own inputs: the picked picture and the flat template as a painting would send them."""
    from apps.pipeline.services import image_guard as ig
    rec = {'allowed_roots': [str(p) for p in ig.ALLOWED_ROOTS][:6], 'call_log': str(ig.CALL_LOG)}
    attempt(rec, 'picked_picture', lambda: ig.check([{'role': 'style reference', 'path': str(ROUND3 / 'files/source.png')}],
                                                   'paint the flat die'))
    attempt(rec, 'flat_template', lambda: ig.check([{'role': 'template', 'path': str(ROUND3 / 'files/flat/template.png')}],
                                                  'paint the flat die'))
    attempt(rec, 'competitor_word', lambda: ig.check([], 'a box like Fenty Beauty'))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day8_concepts.py', k='refused or rejected or competitor')
    return rec


# --- the execution half -------------------------------------------------------------------------------------------------

@probe(27)
def p27(folder, out):
    """The files outbox: its own tests (start, queue, recover, retry, fail) on the files page."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_round_files_page.py')}


@probe(28)
def p28(folder, out):
    """The files job: round 3's brief made an execution brief (its provisional estimates), and its tests."""
    from apps.pipeline.services.round_files_job import execution_brief
    brief = load(round3_copy(out) / 'files/inputs.json')['brief']
    value = execution_brief(brief)
    return {'estimates_mm': value['execution_estimates_mm'], 'dimensions_mm': value['dimensions_mm'],
            'tests': pytest_counts('apps/pipeline/tests/test_round_files_page.py', k='job or read or provider')}


@probe(29)
def p29(folder, out):
    """The owner gate on round 3's die: the stand faces' sizes on the die, and its tests (Accept / Redraw / Make)."""
    from apps.pipeline.services import round_files_faces as faces
    r3 = round3_copy(out)
    geometry = load(r3 / 'files/stand.json')
    die = faces.die_of(geometry)
    brief = load(r3 / 'files/inputs.json')['brief']
    from apps.pipeline.services.round_files_job import execution_brief
    sizes = {}
    for key in faces.FACES:
        f = faces.face_geometry(key, execution_brief(brief), die)
        sizes[key] = [round(f['w_mm'], 2), round(f['h_mm'], 2)]
    return {'face_sizes_mm': sizes, 'tests': pytest_counts('apps/pipeline/tests/test_round_files_faces.py',
                                                           k='accept or redraw or make or gate')}


@probe(30)
def p30(folder, out):
    """The face builder on round 3: a $0 stand-in painting settled on the die, every stand face cut from it, and the
    stand composed on the die as one raster (the files' input) — then its tests."""
    from apps.pipeline.services import round_files_faces as faces
    r3, brief, inspection, geometry, die, painting = stand_in_flat(folder, out)
    rec = {'proof_outside': painting['proof'].get('outside'), 'continuity': str(painting['continuity'])[:300]}
    drawn = {}
    def cut():
        for key in faces.FACES:
            if faces.stand_face(key):
                drawn[key] = faces.flat_face(folder, key, 1, painting, geometry)
        return {k: png_facts(v['face'])['size_px'] for k, v in drawn.items()}
    attempt(rec, 'faces_cut', cut)
    def compose():
        spec, placements = faces.compose_stand(drawn, inspection, brief, geometry, folder / 'on-die')
        return {'artwork_rasters': len(spec['artwork']), 'type_runs': len(spec.get('type_runs', [])),
                'logos': len(spec.get('logos', [])), 'placements': sorted(placements)}
    attempt(rec, 'compose_stand', compose)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_files_faces.py')
    return rec


@probe(31)
def p31(folder, out):
    """The dial type on round 3's drawn header face (faces/header/face.png): shade labels and the ring's words."""
    from apps.pipeline.services import round_files_dial as dial
    from apps.pipeline.services import round_files_faces as faces
    from apps.pipeline.services.round_files_job import execution_brief
    from apps.pipeline.services.round_files_reading import copy_fields
    r3, brief, _inspection = r3_brief(out)
    geometry = load(r3 / 'files/stand.json')
    face = faces.upright_face('header', brief, faces.die_of(geometry))
    inspection = load(r3 / 'files/inspection.json')
    drawn = load(r3 / 'files/faces/header/record.json')
    drawn['face'] = str(r3 / 'files/faces/header/face.png')
    rec = {'face': png_facts(drawn['face']), 'px_per_mm': drawn['template']['px_per_mm']}
    def run():
        placed = faces.marks('header', inspection, brief, face, drawn=drawn)
        return {'type_rows': len(placed['type']), 'texts': [r.get('text') for r in placed['type']][:8],
                'logos': len(placed.get('logos', [])), 'placement': str(placed.get('placement'))[:300]}
    attempt(rec, 'header_marks', run)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_files_faces.py', k='dial or ring or label or header')
    return rec


@probe(32)
def p32(folder, out):
    """The picture reading on round 3: its COPY fields from the brief and the saved inspection validated again."""
    from apps.pipeline.services import round_files_reading as reading
    r3 = round3_copy(out)
    brief = load(r3 / 'files/inputs.json')['brief']
    rec = {'copy_fields': reading.copy_fields(brief)}
    inspection = load(r3 / 'files/inspection.json')
    rec['panels'] = sorted(inspection.get('panels', {}))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_files_faces.py', k='reading or read')
    return rec


@probe(33)
def p33(folder, out):
    """Ornament lettering: its tests (words set live along a band)."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_round_files_faces.py', 'apps/pipeline/tests/test_round_files_export.py',
                                   k='ornament or lettering or arc')}


@probe(34)
def p34(folder, out):
    """The stand adapter: round 3's stand solved again (row 6) and its own tests in the 0.1 file."""
    return {'tests': pytest_counts('apps/dielines/tests/test_counter_tray_header.py', 'apps/pipeline/tests/test_round_files_faces.py',
                                   k='round_files_stand or stand_is_built')}


@probe(35)
def p35(folder, out):
    """The writer on round 3: the drawn header face written as a layered .ai with its live type and logo
    (native=False: Illustrator's save is not run here) and read back."""
    from apps.pipeline.services import round_files_export as export
    from apps.pipeline.services import round_files_faces as faces
    from apps.pipeline.services.round_files_job import execution_brief
    r3, brief, inspection = r3_brief(out)
    geometry = load(r3 / 'files/stand.json')
    die = faces.die_of(geometry)
    rec = {'logo_sha_ok': sha(export.LOGO) == export.LOGO_SHA256}
    attempt(rec, 'font_records', lambda: {k: v.get('postscript', v.get('name')) for k, v in export.font_records().items()}
            if isinstance(export.font_records(), dict) else len(export.font_records()))
    def write():
        drawn = load(r3 / 'files/faces/header/record.json')
        drawn['face'] = str(r3 / 'files/faces/header/face.png')
        spec, _trim = faces.face_spec('header', drawn, inspection, brief, die, 'header-probe')
        result = export.export_object(spec, folder / 'files', native=False)
        back = export.read_back_ai(result['ai'], result['type'], result['elements'])
        return {'ai': Path(result['ai']).name, 'type_runs': len(spec['type_runs']), 'logos': len(spec['logos']),
                'checks_failed': [k for k, v in back.get('checks', {}).items() if v is False],
                'checks': len(back.get('checks', {}))}
    attempt(rec, 'header_ai', write)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_files_export.py')
    return rec


@probe(36)
def p36(folder, out):
    """The retired tracing build: each archived module compiled, and an import tried (it sits out of the path)."""
    import py_compile, importlib.util
    root = REPO / 'archive/round_files_v1/services'
    rec = {}
    for path in sorted(root.glob('*.py')):
        try:
            py_compile.compile(str(path), doraise=True)
            compiled = True
        except Exception:
            compiled = False
        importable = importlib.util.find_spec('apps.pipeline.services.' + path.stem) is not None
        rec[path.stem] = {'compiles': compiled, 'importable_from_apps': importable}
    return rec


# --- the earlier masters and surfaces -----------------------------------------------------------------------------------

@probe(37)
def p37(folder, out):
    """The preservation master: digest, and its own tests in the round flow file."""
    from apps.pipeline.services import round_master_flow as mf
    return {'digest': mf.digest({'a': 1, 'b': 'ملمع'}), 'steps': list(getattr(mf, 'STEPS', [])),
            'tests': pytest_counts('apps/pipeline/tests/test_round_flow.py', k='master')}


@probe(38)
def p38(folder, out):
    """The balm round: glyph_metrics of round 3's words in both pinned faces, parse_response_text, its tests."""
    from apps.pipeline.services import round_balm_master as bm, round_balm_calls as bc
    rec = {}
    attempt(rec, 'latin', lambda: bm.glyph_metrics('BBROSE', 'latin'))
    attempt(rec, 'arabic', lambda: bm.glyph_metrics('ملمع شفاه', 'arabic'))
    attempt(rec, 'fence', lambda: bc.parse_response_text('note\n```json\n{"a": 1}\n```\nafter'))
    attempt(rec, 'two_fences', lambda: bc.parse_response_text('```json\n{}\n```\n```json\n{}\n```'))
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_round_balm.py', 'apps/pipeline/tests/test_round_balm_preservation.py')
    return rec


@probe(39)
def p39(folder, out):
    """zilal_tray's helpers on round 3's die: each printed face's upright size and outline; then its Day 12 tests."""
    from apps.pipeline.services import zilal_tray as zt
    from apps.pipeline.services import round_files_faces as faces
    geometry = load(round3_copy(out) / 'files/stand.json')
    die = faces.die_of(geometry)
    sizes = {}
    for key, spec in faces.FACES.items():
        if faces.stand_face(key):
            _part, poly = faces.die_face(die, spec['die'])
            w, h = zt.face_mm_size(poly, spec['quarters'])
            outline = zt.upright_polygon(poly, spec['quarters'], w, h)
            turned = zt.turn(np.zeros((4, 6, 3), np.uint8), spec['quarters']).shape[:2]
            sizes[key] = {'w_h_mm': [round(w, 2), round(h, 2)], 'outline_area_mm2': round(outline.area, 1),
                          'turned_4x6': list(turned)}
    return {'faces': sizes, 'K_px_per_mm': zt.K, 'tests': pytest_counts('apps/pipeline/tests/test_day12_display.py')}


@probe(40)
def p40(folder, out):
    """zilal_display.drawn_panel on round 3's drawn header and front faces."""
    from apps.pipeline.services import zilal_display as zd
    r3 = round3_copy(out)
    rec = {}
    for key in ('header', 'front', 'bottle', 'cap'):
        path = r3 / 'files/faces' / key / 'face.png'
        if path.exists():
            attempt(rec, key, lambda path=path: {'size': list(Image.open(path).size),
                                                 'panel': zd.drawn_panel(np.asarray(Image.open(path).convert('RGB')))})
        else:
            rec[key] = 'no face.png (the round has none for this face)'
    return rec


@probe(41)
def p41(folder, out):
    """zilal_header: its Day 12 pick read, and its master built again into a scratch folder."""
    from apps.pipeline.services import zilal_header as zh
    rec = {}
    attempt(rec, 'the_pick', lambda: str(zh.the_pick())[:300])
    attempt(rec, 'build', lambda: str(zh.build(folder / 'header'))[:400])
    return rec


@probe(42)
def p42(folder, out):
    """zilal_master: the Day 11 pick loaded; its tests."""
    from apps.pipeline.services import zilal_master as zm
    rec = {}
    attempt(rec, 'load_pick', lambda: str(zm.load_pick())[:300])
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day11_zilal.py', timeout=900)
    return rec


@probe(43)
def p43(folder, out):
    """The Ẓilāl object, sticker, box and cartons: their tests."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_day11_zilal_pack.py', 'apps/pipeline/tests/test_day13_lipstick_carton.py')}


@probe(44)
def p44(folder, out):
    """The Ẓilāl lipstick and balm: the balm's trim rows on an empty wrap; their tests."""
    from apps.pipeline.services import zilal_balm_master as zbm
    rec = {}
    attempt(rec, 'trim_rows', lambda: str(zbm.trim_rows(np.zeros((644, 896, 3), np.uint8), zbm.BODY_MM))[:200])
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day12_balm.py', 'apps/pipeline/tests/test_day11_lipstick.py',
                                 'apps/pipeline/tests/test_day12_lipstick.py')
    return rec


@probe(45)
def p45(folder, out):
    """lid_master's colour maths (the only part the flow uses): pure red to Lab, ΔE00 of round 3's three shades; its
    Day 10 tests."""
    from apps.pipeline.services import lid_master as lm
    hexes = [s['hex'] for s in load(ROUND3 / 'brief.json')['shades']]
    rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in hexes], float)
    lab = lm.srgb_to_lab(rgb)
    return {'red_lab': [round(v, 4) for v in lm.srgb_to_lab(np.array([255., 0., 0.]))],
            'shade_de00': {'%s→%s' % (hexes[i], hexes[j]): round(float(lm.delta_e00(lab[i], lab[j])), 2)
                           for i in range(3) for j in range(i + 1, 3)},
            'tests': pytest_counts('apps/pipeline/tests/test_day10_master.py')}


@probe(46)
def p46(folder, out):
    """Product drawing on round 3: the stand folded and the stand loaded, drawn from a $0 stand-in painting (the round
    designer's own flat_drawings)."""
    from types import SimpleNamespace
    from apps.pipeline.services import round_designer as rd
    r3, brief, inspection, geometry, die, painting = stand_in_flat(folder, out)
    ctx = SimpleNamespace(brief=load(r3 / 'files/inputs.json')['brief'])
    drawn = rd.flat_drawings(ctx, painting, geometry, folder / 'drawings')
    return {'folded': png_facts(drawn['folded']), 'loaded': png_facts(drawn['loaded']),
            'tests': pytest_counts('apps/pipeline/tests/test_round_files_faces.py', k='drawing or folded or loaded')}


@probe(47)
def p47(folder, out):
    """The Day 8/9 lid builds: the astrolabe and gravure devices drawn; their tests."""
    from apps.pipeline.services import lid_devices as ld
    rec = {}
    attempt(rec, 'gravure', lambda: {k: (len(v) if hasattr(v, '__len__') else v) for k, v in ld.gravure().items()})
    attempt(rec, 'astrolabe', lambda: {k: (len(v) if hasattr(v, '__len__') else v) for k, v in ld.astrolabe().items()})
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day8_concepts.py', 'apps/pipeline/tests/test_day9_orn_b1.py')
    return rec


@probe(48)
def p48(folder, out):
    """The palette cartons: the lipstick carton's die and the palette box's die drawn; their tests."""
    from apps.pipeline.services import stick_carton as sc, palette_box as pb
    rec = {}
    attempt(rec, 'stick_die', lambda: coords_facts(sc.die(sc.PRODUCTS['lipstick'])[0]))
    attempt(rec, 'palette_box_die', lambda: coords_facts(pb.die()[0]))
    rec['products'] = sorted(sc.PRODUCTS)
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day11_carton.py')
    return rec


@probe(49)
def p49(folder, out):
    """Live type and fonts: the GRANTED census, the exclusions, the two pinned faces the writer validates."""
    from apps.ire import font_pool
    from apps.pipeline.services import round_files_export as export
    granted = font_pool.files_of('granted')
    rec = {'granted_files': len(granted), 'excluded': len(font_pool.excluded())}
    attempt(rec, 'writer_fonts', lambda: str(export.font_records())[:400])
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_day7_fonts.py')
    return rec


@probe(50)
def p50(folder, out):
    """The approved logo: its file and pin; its placement and refusal tests in the writer's file."""
    from apps.pipeline.services import round_files_export as export
    return {'logo': str(export.LOGO.relative_to(REPO)), 'pinned': export.LOGO_SHA256[:16], 'file_matches': sha(export.LOGO) == export.LOGO_SHA256,
            'tests': pytest_counts('apps/pipeline/tests/test_round_files_export.py', k='logo')}


@probe(51)
def p51(folder, out):
    """The tracers: flat_motif.read_flat on round 3's drawn header face; their tests."""
    from apps.pipeline.services import flat_motif
    png = ROUND3 / 'files/faces/header/face.png'
    rec = {}
    attempt(rec, 'read_flat', lambda: {k: (v if isinstance(v, (int, float, str)) else type(v).__name__)
                                      for k, v in flat_motif.read_flat(png.read_bytes(), 107.0, 78.2).items()})
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_rescue_day5.py', k='traced')
    return rec


@probe(52)
def p52(folder, out):
    """The finish proof: its tests (foil limits read from an engine .ai)."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_day9_orn_b2.py', 'apps/pipeline/tests/test_day11_golden_hour.py',
                                   k='foil or relief')}


@probe(53)
def p53(folder, out):
    """The IRE emitters: Illustrator present?, and the PDF-compatible .ai emitter's tests."""
    from apps.ire.handoff import illustrator_exec
    return {'illustrator_available': illustrator_exec.illustrator_available(),
            'tests': pytest_counts('apps/ire/tests/test_pdf_ai_emitter.py')}


@probe(54)
def p54(folder, out):
    """The Day 13 print pack read back; its tests."""
    return {'tests': pytest_counts('apps/pipeline/tests/test_day14_print_pack.py')}


@probe(55)
def p55(folder, out):
    """The day modules: the Day 8 pick record and the Day 13 creativity page's state; their tests."""
    from apps.pipeline.services import day8_pick, day13_creativity_page as page
    rec = {}
    attempt(rec, 'day8_checked', lambda: str(day8_pick.checked())[:200])
    attempt(rec, 'day13_state', lambda: str(page.state())[:200])
    rec['tests'] = pytest_counts('apps/pipeline/tests/test_rescue_day5.py', 'apps/pipeline/tests/test_day13_creativity_page.py')
    return rec


@probe(56)
def p56(folder, out):
    """The day pages: each route resolved to its view."""
    from django.urls import reverse, resolve, get_resolver
    names = [p.name for p in get_resolver('apps.dashboard.urls').url_patterns if getattr(p, 'name', None)]
    day = [n for n in names if any(t in str(n) for t in ('day5', 'day6', 'day8', 'day9', 'day10', 'day13', 'creativity', 'palette_pick', 'stand_master', 'serum'))]
    return {'routes': day, 'tests': pytest_counts('apps/pipeline/tests/test_day13_creativity_page.py')}


@probe(57)
def p57(folder, out):
    """The palette M-series: its file count and its layout kernel's tests."""
    files = sorted((APP / 'apps/pipeline/services').glob('palette_*.py'))
    return {'files': len(files), 'lines': sum(len(p.read_text().splitlines()) for p in files),
            'tests': pytest_counts('apps/pipeline/tests/test_palette_layout_kernel.py')}
