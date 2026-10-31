"""Revision 4: the one authorised vector device (D-D6-3) replaces the two raster ink planes.

Everything else is revision 3. The device paths are top-left millimetres on the
45.553 x 72.497 flat (device.json); the PDF receives them in bottom-left points.
No tracing happens here: the single trace is read, never redone, and text is never traced.
"""
from pathlib import Path
import base64, copy, json, math, shutil, xml.etree.ElementTree as ET
from collections import Counter
import cv2, fitz, numpy as np
from PIL import Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import fidelity_master as fm, fidelity_assets as fa, day5_master as dm, day6_instrument as di
from .matte_colour import lin, enc

ROOT = fa.ROOT / 'docs/audit/day-6'
DEVICE = ROOT / 'device/device.json'
INSTRUMENT6 = ROOT / 'instrument/fidelity-instrument.json'
REVISION3 = fa.ROOT / 'docs/audit/day-5/master'
OUT = ROOT / 'bottle/revision-4'
SCHEMA = 'design_spec/4.0'
DEVIATION = 'vector edge replaces airbrush softness'
ROLE_ORDER = ['SHADOW', 'CREAM']
LAYER_ROLES = ['SHADOW', 'CREAM', 'LIVE TYPE', 'LOGO', 'RULES']
DAY5_BOXES = [('Tip', (389, 0, 539, 150)), ('Inner bend', (389, 350, 539, 500)), ('Lower return', (389, 650, 539, 800))]


def fonts():
    return dm.fonts()


def device():
    """The single authorised trace, checked against its own record before use."""
    data = json.loads(DEVICE.read_text())
    if data['trace_count'] != 1 or data['text_traced'] or not data['contour_passed']:
        raise ValueError('device.json is not the single passed, text-free trace of D-D6-3.')
    if [r['role'] for r in data['roles']] != ROLE_ORDER:
        raise ValueError('Device role order must be SHADOW below CREAM.')
    endmembers = json.loads(INSTRUMENT6.read_text())['endmembers']
    for role in data['roles']:
        if role['colour_srgb'] != endmembers[role['role'].lower()]['srgb']:
            raise ValueError('Device colour differs from the recorded endmember.')
        if role['fill_rule'] != 'evenodd' or not role['contour_check']['passed'] or role['contour_check']['limit_mm'] != .3:
            raise ValueError('Device role record is not the evenodd, 0.3 mm passed trace.')
    return data


def make_spec():
    parent = dm.make_spec()
    published = json.loads((REVISION3 / 'fidelity-check.json').read_text())['spec_hash']
    if fm.digest(parent) != published:
        raise ValueError('Revision 3 pins changed; revision 4 cannot name its parent.')
    spec = copy.deepcopy(parent); g = spec['graph']; d = device()
    g.pop('raster_assets')
    g['device_roles'] = [{'role': r['role'], 'colour_srgb': r['colour_srgb'], 'fill_rule': r['fill_rule'], 'paths': r['paths'],
                          'source_sha256': r['source_sha256'], 'contour_check': r['contour_check']} for r in d['roles']]
    g['device_asset'] = 'assets/device.json'
    g['device_coordinates'] = 'top-left millimetres on the flat, x right and y down; PDF receives x*mm, (height-y)*mm'
    g['layer_roles'] = list(LAYER_ROLES)
    spec.update(schema_version=SCHEMA, revision=4, parent_hash=fm.digest(parent), review_state='designer_review', production_ready=False)
    spec['assets'] = {'logo': parent['assets']['logo'], 'device': {'path': 'assets/device.json', 'sha256': fa.sha(DEVICE)}}
    spec['ink_model'] = {'authoritative': 'vector device fills; no raster planes; appearance proof composes rendered coverage planes in linear light',
                         'editable_export_preview': 'ordinary source-over of two vector fills, SHADOW below CREAM',
                         'route': 'vector_brand_device_D-D6-3', 'device_sha256': fa.sha(DEVICE),
                         'corrected_instrument_sha256': fa.sha(INSTRUMENT6), 'status': 'designer_review; corrected instrument scores the rendered planes'}
    spec['device_contour_check'] = {'limit_mm': .3, 'source_alpha_threshold': .5, 'passed': d['contour_passed'],
                                    'roles': {r['role']: r['contour_check'] for r in d['roles']}}
    spec['named_deviation'] = DEVIATION
    spec['decoration_proposal']['assumed_mockup_stack'] = ['clear substrate unverified', 'SHADOW deep-amber vector device fill', 'CREAM vector device fill', 'opaque white live type and vector mark']
    return spec


def validate_spec(spec):
    if spec != make_spec():
        raise ValueError('Revision4 pins changed; a new immutable revision is required.')
    return spec


def colour_hex(rgb):
    return '#' + ''.join(f'{round(v):02x}' for v in rgb)


def emit_pdf(graph, path, *, fonts_map, roles=tuple(ROLE_ORDER), live_type=True, rules=True, logo=True):
    """Vector device fills, live type, rules and the approved logo overlay; no raster."""
    names = {role: 'Fidelity-' + role + '-' + fa.sha(font)[:12] for role, font in fonts_map.items()}
    for role, font in fonts_map.items():
        pdfmetrics.registerFont(TTFont(names[role], str(font)))
    c = Canvas(str(path), pagesize=(fa.WIDTH * mm, fa.HEIGHT * mm), pageCompression=1)
    for role in graph['device_roles']:
        if role['role'] not in roles:
            continue
        c._code.append('/Span << /LayerRole (' + role['role'] + ') >> BDC')
        c.setFillColorRGB(*[v / 255 for v in role['colour_srgb']]); shape = c.beginPath()
        for p in role['paths']:
            points = p['points_mm']; shape.moveTo(points[0][0] * mm, (fa.HEIGHT - points[0][1]) * mm)
            for x, y in points[1:]:
                shape.lineTo(x * mm, (fa.HEIGHT - y) * mm)
            shape.close()
        c.drawPath(shape, fill=1, stroke=0, fillMode=0)
        c._code.append('EMC')
    if live_type:
        for line in graph['lines']:
            c._code.append('/Span << /ActualText <FEFF' + line['logical_text'].encode('utf-16-be').hex().upper() + '> >> BDC')
            c.setFillColorRGB(*[v / 255 for v in line['colour']])
            for run in line['runs']:
                c.saveState(); c.translate(run['x_mm'] * mm, run['baseline_z_mm'] * mm)
                c.scale(run['scale_x_mm_per_1000pt_unit'] * mm, run['scale_y_mm_per_1000pt_unit'] * mm)
                c.setFont(names[run['font_role']], 1000); c.drawString(0, 0, run['text']); c.restoreState()
            c._code.append('EMC')
    if rules:
        for e in graph['elements']:
            if e['id'] in ('logo_rule', 'name_rule'):
                a, z0, b, z1 = e['flat_bbox_mm']; c.setFillColorRGB(*[v / 255 for v in e['colour']['srgb_255']])
                c.rect((a + fa.WIDTH / 2) * mm, z0 * mm, (b - a) * mm, (z1 - z0) * mm, fill=1, stroke=0)
    c.save()
    if logo:
        mark = next(e for e in graph['elements'] if e['id'] == 'logo')
        element = fm._logo_svg(mark); element.attrib.update(x='0', y='0')
        with fitz.open(stream=ET.tostring(element), filetype='svg') as logo_doc:
            logo_pdf = logo_doc.convert_to_pdf()
        temp = Path(path).with_suffix('.with-logo.pdf')
        with fitz.open(path) as doc, fitz.open(stream=logo_pdf, filetype='pdf') as page:
            a, z0, b, z1 = mark['flat_bbox_mm']
            box = fitz.Rect((a + fa.WIDTH / 2) * mm, (fa.HEIGHT - z1) * mm, (b + fa.WIDTH / 2) * mm, (fa.HEIGHT - z0) * mm)
            doc[0].show_pdf_page(box, page, 0, keep_proportion=False); doc.save(temp)
        temp.replace(path)


def svg(graph, *, fonts_map):
    ns = 'http://www.w3.org/2000/svg'; ET.register_namespace('', ns)
    el = lambda tag, attrs={}: ET.Element('{' + ns + '}' + tag, {k: str(v) for k, v in attrs.items()})
    root = el('svg', {'width': str(fa.WIDTH) + 'mm', 'height': str(fa.HEIGHT) + 'mm', 'viewBox': f'0 0 {fa.WIDTH} {fa.HEIGHT}'})
    style = el('style')
    style.text = '\n'.join("@font-face{font-family:'%s';src:url(data:font/ttf;base64,%s)}" % (fm.font_data(role, fonts_map)['family'], base64.b64encode(path.read_bytes()).decode()) for role, path in fonts_map.items())
    root.append(style)
    for role in graph['device_roles']:
        g = el('g', {'id': role['role']})
        d = ' '.join('M ' + ' L '.join(f'{x:.6f},{y:.6f}' for x, y in p['points_mm']) + ' Z' for p in role['paths'])
        g.append(el('path', {'fill': colour_hex(role['colour_srgb']), 'fill-rule': role['fill_rule'], 'd': d})); root.append(g)
    g = el('g', {'id': 'LIVE_TYPE'})
    for line in graph['lines']:
        lg = el('g', {'id': line['id'], 'aria-label': line['logical_text']})
        for run in line['runs']:
            sx, sy = run['scale_x_mm_per_1000pt_unit'], run['scale_y_mm_per_1000pt_unit']
            t = el('text', {'transform': f"matrix({sx} 0 0 {sy} {run['x_mm']} {fa.HEIGHT - run['baseline_z_mm']})", 'font-size': 1000,
                            'font-family': fm.font_data(run['font_role'], fonts_map)['family'], 'fill': colour_hex(line['colour']), 'xml:space': 'preserve'})
            t.text = run['text']; lg.append(t)
        g.append(lg)
    root.append(g)
    for e in graph['elements']:
        if e['id'] == 'logo':
            root.append(fm._logo_svg(e))
        if e['id'] in ('logo_rule', 'name_rule'):
            a, z0, b, z1 = e['flat_bbox_mm']
            root.append(el('rect', {'id': e['id'], 'x': a + fa.WIDTH / 2, 'y': fa.HEIGHT - z1, 'width': b - a, 'height': z1 - z0, 'fill': colour_hex(e['colour']['srgb_255'])}))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def coverage_planes(folder, graph):
    """Render each role alone from the same emitter; the proof uses the PDF's own geometry.

    SHADOW is drawn below CREAM, so its visible coverage is s*(1-f) (source-over);
    the 8-bit planes are then held to f+s <= 1 exactly, as revision 3's planes were.
    """
    folder = Path(folder); rendered = {}
    for role in ROLE_ORDER:
        emit_pdf(graph, folder / (role.lower() + '-only.pdf'), fonts_map=fonts(), roles=(role,), live_type=False, rules=False, logo=False)
        rendered[role] = fm.render_artwork(folder / (role.lower() + '-only.pdf'))[:, :, 3].astype(float) / 255
    f = rendered['CREAM']; s = rendered['SHADOW'] * (1 - f)
    qa = np.round(f * 255).astype(np.uint8); qb = np.minimum(np.round(s * 255), 255 - qa).astype(np.uint8)
    colours = {r['role']: np.round(np.array(r['colour_srgb'])).astype(np.uint8) for r in graph['device_roles']}
    planes = {}
    for role, alpha in (('CREAM', qa), ('SHADOW', qb)):
        rgba = np.dstack((np.broadcast_to(colours[role], alpha.shape + (3,)), alpha))
        Image.fromarray(rgba).save(folder / ('swoosh-' + role.lower() + '.png')); planes[role] = rgba
    overlap = rendered['SHADOW'] * f
    record = {'rule': 'cream = rendered CREAM coverage; shadow = rendered SHADOW coverage x (1 - cream), the PDF source-over stacking; 8-bit shadow <= 255 - cream',
              'ppi': 1000, 'shape': list(qa.shape), 'max_alpha_sum_8bit': int((qa.astype(int) + qb.astype(int)).max()),
              'cream_coverage_px': float(f.sum()), 'shadow_coverage_px': float(rendered['SHADOW'].sum()), 'shadow_under_cream_px': float(overlap.sum()),
              'sources': {'cream': 'cream-only.pdf', 'shadow': 'shadow-only.pdf'}}
    return planes, record


def arabic_width_4x(type_rgba, factor):
    """F6: the exported Arabic ink extent on a factor-x concept grid, same threshold as the 1x check."""
    measurement = json.loads(fa.MEASUREMENT.read_text()); e = next(x for x in measurement['elements'] if x['id'] == 'arabic')
    x0, y0, x1, y1 = e['bbox_px']; pad = 8
    xs = (np.arange((x0 - pad) * factor, (x1 + pad) * factor, dtype=np.float32) + .5) / factor - .5
    ys = (np.arange((y0 - pad) * factor, (y1 + pad) * factor, dtype=np.float32) + .5) / factor - .5
    xx, yy = np.meshgrid(xs, ys)
    mx = ((fa.arc(xx) + fa.WIDTH / 2) / fa.WIDTH * (type_rgba.shape[1] - 1)).astype(np.float32)
    my = ((yy - fa.BODY_TOP) * fa.YS / fa.HEIGHT * (type_rgba.shape[0] - 1)).astype(np.float32)
    pre = type_rgba.astype(np.float32).copy(); pre[:, :, :3] *= pre[:, :, 3:4] / 255
    out = cv2.remap(pre, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    occupied = out[:, :, 3] > 96
    if not occupied.any():
        raise ValueError('No exported Arabic ink in the measured region.')
    cols = np.flatnonzero(occupied.any(axis=0)); rows = np.flatnonzero(occupied.any(axis=1))
    width = (cols.max() - cols.min() + 1) / factor; height = (rows.max() - rows.min() + 1) / factor
    delta_w = 100 * abs(width / (x1 - x0) - 1); delta_h = 100 * abs(height / (y1 - y0) - 1)
    return {'factor': factor, 'grid_ppi': [25.4 / fa.XS * factor, 25.4 / fa.YS * factor], 'alpha_threshold': 96,
            'concept_bbox_px': [x0, y0, x1, y1], 'exported_width_concept_px': float(width), 'exported_height_concept_px': float(height),
            'delta_width_percent': float(delta_w), 'delta_height_percent': float(delta_h), 'one_pixel_percent': 100 / (x1 - x0),
            'threshold_percent': 3, 'passed': bool(max(delta_w, delta_h) <= 3)}


def instrument(folder, cream_rgba, shadow_rgba):
    """Corrected proof (F2/F3) on the rendered vector planes beside the retained rows."""
    folder = Path(folder)
    pixels = np.array(Image.open(fa.CONCEPT).convert('RGB')); ground = np.array(Image.open(dm.INK / 'material-field.png').convert('RGB'))
    envelope = np.array(Image.open(dm.INK / 'stroke-support.png')) > 0
    previous = json.loads(INSTRUMENT6.read_text()); cream = np.array(previous['endmembers']['cream']['srgb'])
    result, amber, grey, flagged, stroke = di.corrected_proof(pixels, ground, cream_rgba, shadow_rgba, envelope, cream)
    for suffix, im in [('amber', amber), ('grey', grey), ('support', stroke.astype(np.uint8) * 255)]:
        Image.fromarray(im).save(folder / ('revision4_vector-' + suffix + '.png'))
    marked = grey.copy(); marked[flagged] = [255, 0, 140]; Image.fromarray(marked).save(folder / 'revision4_vector-fringe.png')
    rows = {'revision4_vector': result}
    for name in ('day5_two', 'day5_single', 'day4', 'full_resolution_shadow'):
        rows[name] = previous['results'][name]
    negatives = all(not (rows[n]['recomposition_passed'] and rows[n]['fringe_passed']) for n in ('day4', 'day5_single'))
    report = {'schema': 'day6_bottle_instrument/1', 'revision': 4, 'claude_findings': ['F2', 'F3'], 'rows': rows,
              'bar': {'recomposition_fraction_deltaE_le2': .99, 'fringe_flagged_pixels': 0, 'unchanged': True},
              'revision4_passed': bool(result['recomposition_passed'] and result['fringe_passed']),
              'negative_controls_fail': negatives, 'named_deviation': DEVIATION,
              'reading': 'The vector device is scored by the same corrected_proof as the retained rows; its number is reported, not excused.',
              'inputs': {'concept_sha256': fa.sha(fa.CONCEPT), 'material_field_sha256': fa.sha(dm.INK / 'material-field.png'),
                         'stroke_support_sha256': fa.sha(dm.INK / 'stroke-support.png'), 'corrected_instrument_sha256': fa.sha(INSTRUMENT6),
                         'cream_plane_sha256': fa.sha(folder / 'swoosh-cream.png'), 'shadow_plane_sha256': fa.sha(folder / 'swoosh-shadow.png')},
              'endmembers': previous['endmembers']}
    (folder / 'instrument.json').write_text(json.dumps(report, indent=2) + '\n')
    if not negatives:
        raise ValueError('Historical negative passed both corrected gates; stop and investigate instrument.')
    return report


def build(destination=OUT):
    p = Path(destination); p.mkdir(exist_ok=False, parents=True); a = p / 'assets'; a.mkdir()
    spec = make_spec(); g = spec['graph']; fonts_map = fonts()
    shutil.copyfile(fm.LOGO, a / 'bbrose-logo.svg'); shutil.copyfile(DEVICE, a / 'device.json')
    for role, font in fonts_map.items():
        shutil.copyfile(font, a / font.name); shutil.copyfile(REVISION3 / 'assets' / (role + '-OFL.txt'), a / (role + '-OFL.txt'))
    for name, data in [('design-spec.json', spec), ('design-graph.json', g)]:
        (p / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    (p / 'artwork.svg').write_bytes(svg(g, fonts_map=fonts_map)); emit_pdf(g, p / 'artwork.pdf', fonts_map=fonts_map)
    shutil.copyfile(p / 'artwork.pdf', p / 'artwork-pdf-compatible.ai')
    actual = fm.render_artwork(p / 'artwork.pdf'); Image.fromarray(actual).save(p / 'artwork.png')
    emit_pdf(g, p / 'live-type-logo.pdf', fonts_map=fonts_map, roles=())
    type_rgba = fm.render_artwork(p / 'live-type-logo.pdf'); Image.fromarray(type_rgba).save(p / 'live-type-logo.png')
    planes, plane_record = coverage_planes(p, g); f = planes['CREAM']; s = planes['SHADOW']
    # Revision 3 method, unchanged: project each coverage plane, combine in linear light over the
    # Poisson field blended with the measured shell; type last in linear light.
    pf = fa.project(f); ps = fa.project(s); pt = fa.project(type_rgba); af = pf[:, :, 3:4] / 255; ass = ps[:, :, 3:4] / 255; at = pt[:, :, 3:4] / 255
    background = np.array(Image.open(dm.INK / 'material-field.png').convert('RGB'))
    shell = np.array(Image.open(fm.PRESET / 'material-field.png').convert('RGB'))
    yy, xx = np.indices(background.shape[:2]); weight = np.clip(np.minimum.reduce([xx - 330, 684 - xx, yy - 585, 1380 - yy]) / 12, 0, 1)[:, :, None]
    background = enc(lin(background) * weight + lin(shell) * (1 - weight))
    ink = lin(pf[:, :, :3]) * af + lin(ps[:, :, :3]) * ass + lin(background) * np.maximum(0, 1 - af - ass)
    projection = enc(lin(pt[:, :, :3]) * at + ink * (1 - at)); Image.fromarray(projection).save(p / 'projected-master.png')
    af = f[:, :, 3:4] / 255; ass = s[:, :, 3:4] / 255; at = type_rgba[:, :, 3:4] / 255
    total = af + ass; rgb = (lin(f[:, :, :3]) * af + lin(s[:, :, :3]) * ass) * (1 - at) + lin(type_rgba[:, :, :3]) * at
    alpha = total * (1 - at) + at; texture = np.dstack((enc(rgb / np.maximum(alpha, 1e-12)), np.round(alpha[:, :, 0] * 255).astype(np.uint8)))
    Image.fromarray(texture).save(p / 'artwork-linear-proof-texture.png')
    report = instrument(p, f, s)
    from .fidelity_checks import inspect_pixels
    result = inspect_pixels(fa.project(actual), projection, json.loads(fa.MEASUREMENT.read_text()))
    arabic = arabic_width_4x(type_rgba, 4)
    checks = all(result[k] for k in ('all_elements_present', 'placement_passed', 'colour_passed', 'swoosh_passed'))
    result.update(revision=4, spec_hash=fm.digest(spec), parent_hash=spec['parent_hash'], device_contour_check=spec['device_contour_check'],
                  named_deviation=DEVIATION, coverage_planes=plane_record, arabic_export_4x=arabic, arabic_geometric_measurement=spec['arabic_instance'],
                  instrument={k: report['rows']['revision4_vector'][k] for k in ('recomposition_fraction_deltaE_le2', 'recomposition_passed', 'ground_only', 'fringe_flagged_pixels', 'fringe_passed')},
                  measurement_checks_passed=checks, measured_fidelity_passed=bool(checks and report['revision4_passed']),
                  measured_fidelity_rule='placement, colour, swoosh SSIM and presence AND the corrected instrument (recomposition >= 99%, no fringe)',
                  review_state='designer_review',
                  projection_composite='linear additive from the PDF-rendered vector coverage planes plus actual live-text PDF; PDF preview uses ordinary over')
    (p / 'fidelity-check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return {'revision': 4, 'spec_hash': fm.digest(spec), 'parent_hash': spec['parent_hash'], 'review_state': 'designer_review',
            'recomposition_fraction_deltaE_le2': report['rows']['revision4_vector']['recomposition_fraction_deltaE_le2']}


def critic_inputs(folder=OUT):
    """F4 inputs, prepared only: the integrator reserves spend and makes the call."""
    p = Path(folder); concept = np.array(Image.open(fa.CONCEPT).convert('RGB')); projected = np.array(Image.open(p / 'projected-master.png').convert('RGB'))
    divider = np.full((concept.shape[0], 32, 3), 128, np.uint8)
    Image.fromarray(np.hstack([concept, divider, projected])).save(p / 'critic-input-projected.png')
    flat = np.array(Image.open(p / 'artwork.png')); grey = np.full(flat.shape[:2] + (3,), 128, np.uint8)
    Image.fromarray(fa.composite(grey, flat)).save(p / 'critic-input-grey.png')
    previous = json.loads((REVISION3 / 'critic.json').read_text())
    brief = {'schema': 'critic_brief/day6-1', 'revision': 4, 'call_state': 'prepared, not sent; the integrator reserves spend before the call',
             'finding': 'F4', 'primary_input': {'file': 'critic-input-projected.png', 'sha256': fa.sha(p / 'critic-input-projected.png'),
                                                'content': 'concept 147 (left) beside the revision 4 projected master (right) at one scale, neutral divider'},
             'supplementary_input': {'file': 'critic-input-grey.png', 'sha256': fa.sha(p / 'critic-input-grey.png'),
                                     'content': 'revision 4 flat editable preview on neutral grey 128; diagnostic view, not the product ground'},
             'instruction': 'Score the illustration and fidelity dimensions on the projected bottle beside concept 147 (primary input). '
                            'The product ground is amber liquid; the grey flat is attached as supplementary evidence only and must not be the basis of the illustration score. '
                            'Weights, thresholds and the ten dimensions are unchanged; the illustration minimum stays 7.',
             'also_rescore': 'revision 3 both ways (docs/audit/day-5/master/projected-master.png beside concept 147; its artwork.png on grey) and print both, per F4',
             'stop_rule': 'Owner prompt section 5: if the illustration dimension is still below 7 on the projected bottle, report it and stop touching the swoosh for the rest of the rescue.',
             'revision3_record': {'critical_illustration': previous['critical_illustration'], 'creative_mean': previous['creative_mean'], 'fidelity_mean': previous['fidelity_mean']},
             'calibration': 'docs/audit/day-6/critic-calibration.json (D-D6-1 and F5 points); no weight changes',
             'named_deviation': DEVIATION, 'spend': 'Day 6 budget, critic calls only; reserve before each call', 'cost_usd_so_far': 0}
    (p / 'critic-brief.json').write_text(json.dumps(brief, indent=2, ensure_ascii=False) + '\n')
    return brief


def crops(folder):
    """The Day 5 boxes, cut from the same corrected-instrument grey composites (300 PPI)."""
    p = Path(folder); original = Image.open(ROOT / 'instrument/day5_two-grey.png'); vector = Image.open(p / 'revision4_vector-grey.png')
    out = []
    for name, box in DAY5_BOXES:
        stem = name.lower().replace(' ', '-'); files = []
        for row, source in enumerate((original, vector)):
            path = p / f'{stem}-{row}.png'; source.crop(box).save(path); files.append(path)
        out.append((name, files))
    return out


def sheet(folder=OUT):
    from .day4_proofs import setup, words, heading, bar, image_on, render_pdf
    setup(); p = Path(folder); out = p / 'comparison-at-100-percent.pdf'; c = Canvas(str(out), pagesize=(210 * mm, 297 * mm))
    check = json.loads((p / 'fidelity-check.json').read_text()); report = json.loads((p / 'instrument.json').read_text()); spec = json.loads((p / 'design-spec.json').read_text())
    r4 = report['rows']['revision4_vector']; verdict = lambda ok: 'PASS' if ok else 'FAIL'
    heading(c, 'SUN REPAIR / revision 4', 'DESIGNER REVIEW - vector brand device under D-D6-3; shown for owner objection, used unless objected')
    W, H = 1024 * fa.XS, 1536 * fa.YS
    for x, file, label in [(5, fa.CONCEPT, 'Concept147'), (75, p / 'projected-master.png', 'R4 projected master (linear light)')]:
        image_on(c, file, x, 128, W, H); words(c, x + 10, 121, label, 8)
    c.setFillColorRGB(.502, .502, .502); c.rect(157 * mm, 139 * mm, fa.WIDTH * mm, fa.HEIGHT * mm, fill=1, stroke=0)
    image_on(c, p / 'artwork.png', 157, 139, fa.WIDTH, fa.HEIGHT); words(c, 157, 121, 'R4 flat editable preview', 8)
    arabic = check['arabic_export_4x']; placement = {r['id']: r for r in check['placement']}
    lines = ['One scale: 108 mm overall comparison convention; height datum remains unknown.',
             'Revision 4 = revision 3 with the single vector device in place of the two raster ink planes.',
             'Middle: linear-light B*(1-F-S)+cream*F+shadow*S from the PDF-rendered coverage planes, plus live type.',
             'Right: flat editable PDF, ordinary over of SHADOW then CREAM fills, on neutral grey.',
             'Named deviation: vector edge replaces airbrush softness (D-D6-3).',
             f"Corrected instrument on stroke support: {100 * r4['recomposition_fraction_deltaE_le2']:.2f}% within dE2 / bar 99% - {verdict(r4['recomposition_passed'])}; fringe {r4['fringe_flagged_pixels']} px - {verdict(r4['fringe_passed'])}.",
             f"Measurement: placement {verdict(check['placement_passed'])} (Arabic 1x {placement['arabic']['delta_scale_percent'][0]:.3f}%, 4x {arabic['delta_width_percent']:.3f}%); colour {verdict(check['colour_passed'])}; swoosh SSIM {check['swoosh_ssim']:.4f} - {verdict(check['swoosh_passed'])}.",
             'Critic not yet called: F4 inputs prepared (projected bottle beside concept 147; grey flat supplementary).']
    for i, text in enumerate(lines):
        words(c, 14, 106 - i * 8, text, 7)
    bar(c, 14, 29); c.showPage()
    heading(c, 'DEVICE BESIDE ORIGINAL / approval panel (D-D6-3)', 'One authorised trace of the 1000-PPI two-plane matte at its 50% alpha contour; text never traced')
    y = 254
    for role in spec['graph']['device_roles']:
        k = role['contour_check']
        words(c, 14, y, f"{role['role']}: reference->vector max {k['reference_to_vector_max_mm']:.3f} mm; vector->reference max {k['vector_to_reference_max_mm']:.3f} mm; limit {k['limit_mm']:.1f} mm - {verdict(k['passed'])}", 8); y -= 8
        words(c, 14, y, f"   colour sRGB {'/'.join(str(round(v)) for v in role['colour_srgb'])} (recorded endmember); {len(role['paths'])} closed paths, fill rule {role['fill_rule']}", 7); y -= 9
    words(c, 14, y, 'Left column: the original two-plane matte on grey. Right column: the vector device on grey. Same instrument composite, 300 PPI, 4x physical.', 7)
    for j, (name, files) in enumerate(crops(p)):
        x = 16 + j * 64; words(c, x, 205, name + ' / 4x physical crop', 8)
        for row, (path, caption) in enumerate(zip(files, ['Original two-plane matte on grey', 'Vector device on grey (revision 4)'])):
            yy = 145 - row * 62; image_on(c, path, x, yy, 50.8, 50.8); words(c, x, yy - 5, caption, 7)
    words(c, 14, 70, 'Named deviation: vector edge replaces airbrush softness.', 9)
    words(c, 14, 62, 'Shown for owner objection; used unless objected (D-D6-3). The same device scales to the stand header without PPI loss.', 8)
    words(c, 14, 54, 'Contour check: every 50%-alpha contour point lies within the stated distance of the vector outline, and back, at bottle scale.', 7)
    bar(c, 14, 29); c.showPage()
    heading(c, 'Corrected instrument (F2/F3) / revision 4 beside the retained rows', '300 PPI; sigma 0.08 mm; recomposition on stroke support alpha>0.02 only; ground-only residual separate; bars unchanged')
    y = 254; words(c, 14, y, 'Row: % within dE2 on stroke support (bar 99%); stroke dE median/p95; ground-only median/p95 (px); fringe px', 8); y -= 10
    labels = [('revision4_vector', 'Revision 4 vector device'), ('day5_two', 'Day 5 two-ink raster'), ('day5_single', 'Day 5 single-ink'), ('day4', 'Day 4 flat matte')]
    for key, label in labels:
        row = report['rows'][key]; g = row['ground_only']
        words(c, 14, y, f"{label}: {100 * row['recomposition_fraction_deltaE_le2']:.2f}% - {verdict(row['recomposition_passed'])}; stroke dE {row['stroke_deltaE_median']:.2f}/{row['stroke_deltaE_p95']:.2f}", 8); y -= 7
        words(c, 18, y, f"ground-only dE {g['median_deltaE']:.2f}/{g['p95_deltaE']:.2f} ({g['pixels']} px); fringe {row['fringe_flagged_pixels']} px - {verdict(row['fringe_passed'])}", 7); y -= 9
    words(c, 14, y, f"Negative controls (Day 4, Day 5 single-ink) fail under the corrected instrument: {report['negative_controls_fail']}.", 8); y -= 8
    words(c, 14, y, 'The vector device drops the airbrush edge by design (named deviation); its number is reported, not excused.', 8)
    # Arabic line unchanged from revision 3; F6 adds the 4x raster figure beside the 1x figure.
    rgba = fa.project(fm.render_artwork(p / 'live-type-logo.pdf')); crop = rgba[1037:1082, 340:525]; alpha = crop[:, :, 3:4] / 255
    rgb = (crop[:, :, :3] * alpha + 128 * (1 - alpha)).astype(np.uint8); chosen = p / 'cairo-selected-4x.png'
    Image.fromarray(rgb).resize((740, 180), Image.Resampling.NEAREST).save(chosen)
    for name in ('noto-padded-4x.png', 'cairo300-padded-4x.png'):
        shutil.copyfile(REVISION3 / name, p / name)
    words(c, 14, 158, 'Arabic / heaviest fitting Cairo instance, unchanged from revision 3', 10)
    for x, file, label in [(10, p / 'noto-padded-4x.png', 'Noto / natural proportion'), (84, p / 'cairo300-padded-4x.png', 'Cairo300 / uniform fit'), (139, chosen, 'Cairo340.17 / applied')]:
        im = Image.open(file); w = im.width * fa.XS; h = im.height * fa.YS
        c.setFillColorRGB(.502, .502, .502); c.rect(x * mm, 128 * mm, w * mm, 18 * mm, fill=1, stroke=0)
        image_on(c, file, x, 137 - h / 2, w, h); words(c, x, 152, label, 7)
    cairo = check['arabic_geometric_measurement']; one = placement['arabic']; ex = one['exported_bbox_px']; cb = one['concept_bbox_px']
    f6 = [f"Natural shaped ink: {cairo['width_at_25px']:.4f} x25px, width+{cairo['delta_width_percent']:.4f}%; bisection 300..400, no width squeeze.",
          f"1x source-grid export ({25.4 / fa.XS:.0f} PPI): {ex[2] - ex[0]}x{ex[3] - ex[1]} px versus {cb[2] - cb[0]}x{cb[3] - cb[1]} px: width+{one['delta_scale_percent'][0]:.3f}% (1 px = {arabic['one_pixel_percent']:.2f}%).",
          f"4x raster export ({arabic['grid_ppi'][0]:.0f} PPI): {arabic['exported_width_concept_px']:.2f} px versus {cb[2] - cb[0]} px: width+{arabic['delta_width_percent']:.3f}%, height {arabic['delta_height_percent']:.2f}% - {'PASS at 4x' if arabic['passed'] else 'still above 3%'}.",
          ('Why it passes at 4x: the 1x figure is quantised to whole concept pixels; the 4x grid resolves the edge and agrees with the continuous width. No design change (F6).' if arabic['passed']
           else 'The 4x figure stays above 3%: the line remains REVIEW at pixel scale; no design change (F6).'),
          'Live per-glyph Cairo objects retain shaped glyphs; automatic line reflow is limited.']
    for i, text in enumerate(f6):
        words(c, 14, 112 - i * 8, text, 7)
    bar(c, 14, 29); c.save(); render_pdf(out)
    return out


def native_script(folder=OUT):
    """Native AI generator for vector roles: compound paths via setEntirePath, no raster planes.

    Writes artwork-native.jsx; execution belongs to the integrator (D-D6-5).
    """
    p = Path(folder); spec = validate_spec(json.loads((p / 'design-spec.json').read_text())); g = spec['graph']
    logo = next(e for e in g['elements'] if e['id'] == 'logo'); root = fm._logo_svg(logo); root.attrib.update(x='0', y='0')
    (p / 'native-logo.svg').write_bytes(ET.tostring(root))
    data = {'w': fa.WIDTH * mm, 'h': fa.HEIGHT * mm, 'mm': mm, 'lines': g['lines'], 'fonts': {r: spec['fonts'][r]['postscript'] for r in spec['fonts']},
            'device': [{'role': r['role'], 'colour': r['colour_srgb'], 'paths': [[[x * mm, (fa.HEIGHT - y) * mm] for x, y in q['points_mm']] for q in r['paths']]} for r in g['device_roles']],
            'logo': str(p / 'native-logo.svg'), 'box': logo['flat_bbox_mm'], 'rules': [e for e in g['elements'] if e['id'].endswith('_rule')],
            'out': str(p / 'artwork-native.ai'), 'pdf': str(p / 'artwork-native-check.pdf'), 'census': str(p / 'artwork-native-census.json')}
    code = r'''(function(){var D=__DATA__,doc=null,mark=null,old=app.userInteractionLevel,report={};
    function quote(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
    function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return quote(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(quote(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
    function colour(rgb){var c=new RGBColor();c.red=rgb[0];c.green=rgb[1];c.blue=rgb[2];return c;}
    try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.documents.add(DocumentColorSpace.RGB,D.w,D.h);doc.artboards[0].artboardRect=[0,D.h,D.w,0];
    report.stage='device';for(var k=0;k<D.device.length;k++){var R=D.device[k],layer=(k===0)?doc.layers[0]:doc.layers.add();layer.name=R.role;doc.activeLayer=layer;var cp=layer.compoundPathItems.add();cp.name=R.role;
    for(var m=0;m<R.paths.length;m++){report.currentPath=R.role+'-'+m;var pi=cp.pathItems.add();pi.setEntirePath(R.paths[m]);pi.closed=true;pi.evenodd=true;pi.filled=true;pi.stroked=false;pi.fillColor=colour(R.colour);}}app.redraw();
    report.stage='type';var layer=doc.layers.add();layer.name='LIVE TYPE';
    for(var i=0;i<D.lines.length;i++){var line=D.lines[i],group=layer.groupItems.add();group.name=line.logical_text;
    for(var j=0;j<line.runs.length;j++){report.currentGlyph=line.id+'-'+j;var r=line.runs[j],tf=doc.textFrames.pointText([0,0]);tf.contents=r.text;tf.name=line.id+'-'+j;var at=tf.textRange.characterAttributes;report.stage='type.size';at.size=100;report.stage='type.font';at.textFont=app.textFonts.getByName(D.fonts[r.font_role]);report.stage='type.colour';at.fillColor=colour(line.colour);tf.move(group,ElementPlacement.PLACEATEND);
    var mat=app.getIdentityMatrix();mat.mValueA=r.scale_x_mm_per_1000pt_unit*D.mm*10;mat.mValueD=r.scale_y_mm_per_1000pt_unit*D.mm*10;mat.mValueTX=r.x_mm*D.mm;mat.mValueTY=r.baseline_z_mm*D.mm;tf.transform(mat,true,true,true,true,1,Transformation.DOCUMENTORIGIN);}}
    report.stage='rules';layer=doc.layers.add();layer.name='RULES';for(var i=0;i<D.rules.length;i++){var e=D.rules[i],b=e.flat_bbox_mm;var q=layer.pathItems.rectangle(b[3]*D.mm,(b[0]+D.w/D.mm/2)*D.mm,(b[2]-b[0])*D.mm,(b[3]-b[1])*D.mm);q.stroked=false;q.filled=true;q.fillColor=colour(e.colour.srgb_255);q.name=e.id;}
    report.stage='logo';layer=doc.layers.add();layer.name='LOGO';doc.activeLayer=layer;mark=app.open(new File(D.logo));var grp=mark.groupItems.add();for(var j=mark.pageItems.length-1;j>=0;j--){var item=mark.pageItems[j];if(item!==grp&&item.parent===mark.layers[0])item.moveToBeginning(grp);}var clone=grp.duplicate(doc,ElementPlacement.PLACEATBEGINNING);mark.close(SaveOptions.DONOTSAVECHANGES);mark=null;doc.activate();
    var b=D.box;clone.width=(b[2]-b[0])*D.mm;clone.height=(b[3]-b[1])*D.mm;clone.position=[(b[0]+D.w/D.mm/2)*D.mm,b[3]*D.mm];clone.name='APPROVED VECTOR LOGO';
    report.stage='census';report.frames=[];for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i],a=t.textRange.characterAttributes;report.frames.push({text:t.contents,font:a.textFont.name,size:a.size,bounds:t.visibleBounds});}
    report.layers=[];for(var i=0;i<doc.layers.length;i++){var L=doc.layers[i];var sub=0;for(var q=0;q<L.compoundPathItems.length;q++)sub+=L.compoundPathItems[q].pathItems.length;report.layers.push({name:L.name,paths:L.pathItems.length,compound:L.compoundPathItems.length,compound_subpaths:sub,rasters:L.rasterItems.length,placed:L.placedItems.length});}
    report.artboards=doc.artboards.length;report.paths=doc.pathItems.length;report.compound=doc.compoundPathItems.length;report.rasters=doc.rasterItems.length;report.placed=doc.placedItems.length;
    report.stage='save';var options=new IllustratorSaveOptions();options.pdfCompatible=true;doc.saveAs(new File(D.out),options);var po=new PDFSaveOptions();po.preserveEditability=false;doc.saveAs(new File(D.pdf),po);report.saved=true;
    }catch(e){report.saved=false;report.error=String(e);}finally{if(mark)mark.close(SaveOptions.DONOTSAVECHANGES);if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);app.userInteractionLevel=old;}
    var file=new File(D.census);file.encoding='UTF-8';file.open('w');file.write(json(report));file.close();return json({saved:report.saved,error:report.error});})();'''
    script = p / 'artwork-native.jsx'; script.write_text(code.replace('__DATA__', json.dumps(data)))
    return script


def native_validate(folder=OUT):
    """Validate an executed native build: live glyphs, vector-only layers, render agreement."""
    from .traced_text import pdf_live, expected_lines
    p = Path(folder); spec = validate_spec(json.loads((p / 'design-spec.json').read_text())); g = spec['graph']
    report = json.loads((p / 'artwork-native-census.json').read_text())
    report['route'] = 'Native glyph creation with measured Cairo; SHADOW and CREAM compound paths from the single device trace; no raster plane.'
    expected_paths = {r['role']: len(r['paths']) for r in g['device_roles']}
    if report['saved']:
        expected = Counter((r['text'], spec['fonts'][r['font_role']]['postscript']) for l in g['lines'] for r in l['runs'])
        found = Counter((r['text'], r['font']) for r in report['frames']); report['glyph_fonts_match'] = expected == found
        layers = {L['name']: L for L in report['layers']}
        # Illustrator reports Layer.pathItems.length as 0 when every path sits inside the layer's one compound path;
        # the device check counts the compound path's own sub-paths (census field compound_subpaths; an older census
        # without it is completed from the independent sub-path census of the same file bytes, when present).
        subpaths = {}
        for role in expected_paths:
            if 'compound_subpaths' in layers[role]:
                subpaths[role] = layers[role]['compound_subpaths']
        independent = p / 'artwork-native-subpath-census.json'
        if len(subpaths) < len(expected_paths) and independent.exists():
            census = json.loads(independent.read_text())
            if census['source_sha256'] == fa.sha(p / 'artwork-native.ai'):
                subpaths = dict(census['device_subpaths']['found']); report['device_subpath_source'] = 'artwork-native-subpath-census.json (same file bytes)'
        report['device_subpaths'] = {'expected': expected_paths, 'found': subpaths}
        report['device_paths_match'] = all(role in subpaths and subpaths[role] == expected_paths[role] and layers[role]['compound'] == 1 for role in expected_paths)
        report['live_text'] = pdf_live(p / 'artwork-native.ai', expected_lines(spec, p / 'assets'))
        arrays = []
        for name in ['artwork.pdf', 'artwork-native.ai']:
            with fitz.open(p / name) as pdf:
                pix = pdf[0].get_pixmap(dpi=600, alpha=True); v = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 4)
                arrays.append(v[:, :, :3].astype(float) + 128 * (1 - v[:, :, 3:4] / 255))
        report['render_shape_match'] = arrays[0].shape == arrays[1].shape
        if report['render_shape_match']:
            report['render_mae'] = float(np.abs(arrays[0] - arrays[1]).mean())
        with fitz.open(p / 'artwork-native.ai') as doc:
            report['raster_images'] = len(doc[0].get_images())
        report['passed'] = bool(report['glyph_fonts_match'] and report['device_paths_match'] and report['rasters'] == 0 and report['raster_images'] == 0
                                and report['live_text']['passed'] and report['render_shape_match'] and report['render_mae'] < 3)
    else:
        report['passed'] = False
    report['source_hashes'] = {n: fa.sha(p / n) for n in ['artwork.pdf', 'artwork-native.ai', 'design-spec.json', 'assets/device.json'] if (p / n).exists()}
    (p / 'artwork-native-validation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


def native_build(folder=OUT):
    """Integrator's act: run the prepared script in Illustrator, then validate. Not executed by B5."""
    from apps.ire.handoff.illustrator_exec import run_jsx
    script = native_script(folder); execution = run_jsx(str(script))
    if not (Path(folder) / 'artwork-native-census.json').exists():
        raise ValueError('Illustrator wrote no census: ' + json.dumps(execution))
    return native_validate(folder)


def traced_text_readiness(folder=OUT, tessdata=dm.ROOT / 'text-audit/tessdata'):
    """TRACED_TEXT on pdf and svg; native is pending the integrator's Illustrator run.

    The Day 5 text audit's tessdata (eng + ara) is named explicitly; a missing
    language is a refusal in the record, never a silently narrower check.
    """
    from .traced_text import inspect_bundle
    if not (Path(tessdata) / 'ara.traineddata').exists():
        raise ValueError('Arabic tessdata missing at ' + str(tessdata) + '; TRACED_TEXT cannot be verified.')
    p = Path(folder); report = inspect_bundle(p, tessdata=tessdata)
    report['tessdata'] = str(Path(tessdata).relative_to(fa.ROOT))
    report['formats']['native'] = {'passed': False, 'state': 'pending integrator', 'reason': 'Illustrator run belongs to the integrator (D-D6-5); artwork-native.jsx prepared by native_script(), not executed.'}
    report['ocr_positive_controls'] = 'not run by B5; formats cannot pass until the integrator records them'
    report['raster_planes_in_package'] = 0
    report['passed'] = False; report['state'] = 'pending native; pdf and svg live-text and raster-OCR results recorded'
    (p / 'traced-text.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report
