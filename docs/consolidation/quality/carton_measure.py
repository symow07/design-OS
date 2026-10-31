"""The carton die's files measured on three real inputs ($0): before the carton dies moved onto the one die writer
(production_pdf, svg_exporter, ai_exporter) and after (counter_display_files). The die writer's quality file reads
both records side by side.

    bbrose_design_os/venv/bin/python docs/consolidation/quality/carton_measure.py before|after

Writes docs/consolidation/quality/runs/carton-<label>/: each input's files and numbers.json. Each number:
- spot plates: the CutContour, Crease and /All separations the PDF declares;
- boxes: TrimBox against the cut's bounds, BleedBox against the bleed's, in mm;
- read-back: every cut and crease vertex the engine drew against the PDF's own lines on its CUT and CREASE layers
  (largest distance, mm), and every line the PDF drew against the engine's (a stray line shows here);
- fonts: each face the PDF uses and whether it is embedded;
- the SVG's layer groups and the .ai's bytes against the PDF's.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
APP = REPO / 'bbrose_design_os'
sys.path.insert(0, str(APP))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402

django.setup()
import fitz  # noqa: E402

from apps.dielines.geometry.engine import calculate_dieline  # noqa: E402
from apps.dielines.validators.schema import DielineInputJSON  # noqa: E402

PT = 72 / 25.4
INPUTS = {
    'reverse-tuck-1.4': dict(template='reverse_tuck_end_carton', template_version='1.4', w=22.0, d=22.0, h=105.0,
                             glue=12.0, t=0.45),
    'straight-tuck-1.4': dict(template='straight_tuck_end_carton', template_version='1.4', w=22.0, d=22.0, h=105.0,
                              glue=12.0, t=0.45),
    'straight-tuck-28x28x120': dict(template='straight_tuck_end_carton', template_version=None, w=28.0, d=28.0,
                                    h=120.0, glue=10.0, t=None),
}


def params(spec):
    construction = {'glue_tab_mm': spec['glue']}
    if spec['t'] is not None:
        construction.update(board_thickness_mm=spec['t'], thickness_compensation=True)
    kwargs = dict(template=spec['template'], unit='mm',
                  dimensions={'width_mm': spec['w'], 'depth_mm': spec['d'], 'height_mm': spec['h']},
                  print_settings={'bleed_mm': 3.0, 'safe_margin_mm': 4.0}, construction=construction,
                  metadata={'product_name': 'Rose Glaze Lip Gloss', 'product_type': 'lip gloss'})
    if spec['template_version']:
        kwargs['template_version'] = spec['template_version']
    return DielineInputJSON(**kwargs)


def writers():
    """The carton's writers as they stand: the one die writer's when it has them, else the old three."""
    from apps.dielines.exporters import counter_display_files as cdf
    if hasattr(cdf, 'write_carton_pdf'):
        return {'pdf': cdf.write_carton_pdf, 'svg': cdf.write_carton_svg, 'ai': cdf.carton_ai_from_pdf,
                'dxf': cdf.write_carton_dxf, 'cf2': cdf.write_carton_cf2, 'writer': 'counter_display_files'}
    from apps.dielines.exporters.ai_exporter import export_ai_from_production_pdf
    from apps.dielines.exporters.production_pdf import export_production_pdf
    from apps.dielines.exporters.svg_exporter import export_svg
    return {'pdf': export_production_pdf, 'svg': export_svg, 'ai': export_ai_from_production_pdf,
            'dxf': None, 'cf2': None, 'writer': 'production_pdf + svg_exporter + ai_exporter'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readback(pdf, coords):
    """The PDF's CUT and CREASE lines mapped back to the die's millimetres through its TrimBox (= the cut's bounds)."""
    cminx, cminy, cmaxx, cmaxy = coords.cut_polygon.bounds
    expected = {'CUT': [], 'CREASE': []}
    rings = [coords.cut_polygon.exterior] + list(coords.cut_polygon.interiors)
    expected['CUT'] = [tuple(p) for ring in rings for p in ring.coords]
    expected['CUT'] += [p for x1, y1, x2, y2 in coords.slit_lines for p in ((x1, y1), (x2, y2))]
    expected['CREASE'] = [p for x1, y1, x2, y2 in coords.fold_lines for p in ((x1, y1), (x2, y2))]
    with fitz.open(pdf) as doc:
        page = doc[0]
        trim = page.trimbox
        found = {'CUT': [], 'CREASE': []}
        layers = set()
        for drawing in page.get_drawings():
            layer = drawing.get('layer')
            layers.add(layer)
            if layer not in found:
                continue
            for item in drawing['items']:
                if item[0] == 'l':
                    pts = [item[1], item[2]]
                elif item[0] == 'c':
                    pts = [item[1], item[4]]
                elif item[0] == 're':
                    pts = [item[1].tl, item[1].tr, item[1].br, item[1].bl]
                else:
                    continue
                found[layer] += [(cminx + (p.x - trim.x0) / PT, cminy + (p.y - trim.y0) / PT) for p in pts]
    out = {}
    for layer in ('CUT', 'CREASE'):
        e, f = expected[layer], found[layer]
        if not f:
            out[layer] = {'engine_vertices': len(e), 'pdf_points': 0, 'engine_to_pdf_max_mm': None,
                          'pdf_to_engine_max_mm': None}
            continue
        out[layer] = {'engine_vertices': len(e), 'pdf_points': len(f),
                      'engine_to_pdf_max_mm': round(max(min(math.dist(a, b) for b in f) for a in e), 4),
                      'pdf_to_engine_max_mm': round(max(min(math.dist(a, b) for b in e) for a in f), 4)}
    out['layers_drawn'] = sorted(x for x in layers if x)
    return out


def measure(label, spec, folder, w):
    coords = calculate_dieline(params(spec))
    folder.mkdir(parents=True, exist_ok=True)
    job = label
    kwargs = dict(product_name='Rose Glaze Lip Gloss', product_type='lip gloss', bleed_mm=3.0, safe_margin_mm=4.0,
                  glue_tab_mm=spec['glue'], board_thickness_mm=spec['t'], output_dir=str(folder))
    pdf = w['pdf'](coords, job, **kwargs)
    svg = w['svg'](coords, job, output_dir=str(folder))
    ai = w['ai'](pdf, job, output_dir=str(folder))
    data = open(pdf, 'rb').read()
    rec = {'writer': w['writer'], 'flat_mm': [coords.flat_width_mm, coords.flat_height_mm]}
    rec['spot_plates'] = {name: (b'/' + name.encode()) in data for name in ('CutContour', 'Crease', 'All')}
    rec['overprint'] = b'/OP true' in data
    with fitz.open(pdf) as doc:
        page = doc[0]
        rec['page_mm'] = [round(page.rect.width / PT, 3), round(page.rect.height / PT, 3)]
        trim, bleed = page.trimbox, page.bleedbox
        cb, bb = coords.cut_polygon.bounds, coords.bleed_polygon.bounds
        rec['trimbox_vs_cut_mm'] = round(max(abs(trim.width / PT - (cb[2] - cb[0])),
                                             abs(trim.height / PT - (cb[3] - cb[1]))), 4)
        rec['bleedbox_vs_bleed_mm'] = round(max(abs(bleed.width / PT - (bb[2] - bb[0])),
                                                abs(bleed.height / PT - (bb[3] - bb[1]))), 4)
        rec['fonts'] = sorted({(f[3], f[1] != 'n/a') for f in page.get_fonts()})
        rec['fonts_all_embedded'] = all(embedded for _name, embedded in rec['fonts'])
        words = ' '.join(page.get_text().split())
        rec['title_words'] = [w_ for w_ in ('Specification', 'Flat size', 'Scale: 1:1', 'CutContour (cut)',
                                            'Crease (fold)') if w_ in words]
        ocgs = doc.get_ocgs()
        rec['layers'] = sorted(info['name'] for info in ocgs.values())
    rec['readback'] = readback(pdf, coords)
    rec['svg_groups'] = [g for g in ('bleed', 'cut-lines', 'fold-lines', 'safe-area') if 'id="%s"' % g in svg]
    rec['ai_is_the_pdf'] = sha(ai) == sha(pdf)
    rec['files'] = {Path(p).name: {'bytes': Path(p).stat().st_size, 'sha256': sha(p)} for p in (pdf, ai)}
    rec['files'][job + '.svg'] = {'bytes': len(svg.encode()), 'sha256': hashlib.sha256(svg.encode()).hexdigest()}
    for kind in ('dxf', 'cf2'):
        if w[kind]:
            path = folder / ('%s.%s' % (job, kind))
            rec[kind] = w[kind](coords, path)
            rec[kind]['readback'] = die_file_readback(kind, path, coords)
            rec['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        else:
            rec[kind] = None
    return rec


def die_file_readback(kind, path, coords):
    """The DXF's or CF2's cut and crease segments mapped back to the die's millimetres (the sheet's margin and its
    y-up axis undone): every engine vertex against the file's endpoints, and back."""
    from apps.dielines.exporters import counter_display_files as cdf
    _lines, _w, sheet_h = cdf.carton_lines(coords)
    bminx, bminy = coords.bleed_polygon.bounds[:2]
    m = cdf.CARTON_SHEET_MARGIN_MM
    back = lambda x, y: (x - m + bminx, (sheet_h - y) - m + bminy)  # noqa: E731
    found = {'CUT': [], 'CREASE': []}
    text = Path(path).read_text().splitlines()
    if kind == 'dxf':
        i = 0
        while i < len(text):
            if text[i] == 'LINE' and text[i - 1] == '0':
                fields = dict(zip(text[i + 1::2][:16], text[i + 2::2][:16]))
                layer = fields.get('8')
                if layer in found:
                    found[layer] += [back(float(fields['10']), float(fields['20'])),
                                     back(float(fields['11']), float(fields['21']))]
            i += 1
    else:
        for line in text:
            if line.startswith('L,'):
                parts = line.split(',')
                layer = {'1': 'CUT', '2': 'CREASE'}.get(parts[2])
                if layer:
                    found[layer] += [back(float(parts[4]), float(parts[5])), back(float(parts[6]), float(parts[7]))]
    rings = [coords.cut_polygon.exterior] + list(coords.cut_polygon.interiors)
    expected = {'CUT': [tuple(p) for r in rings for p in r.coords]
                + [p for x1, y1, x2, y2 in coords.slit_lines for p in ((x1, y1), (x2, y2))],
                'CREASE': [p for x1, y1, x2, y2 in coords.fold_lines for p in ((x1, y1), (x2, y2))]}
    out = {}
    for layer in found:
        e, f = expected[layer], found[layer]
        out[layer] = {'engine_to_file_max_mm': round(max(min(math.dist(a, b) for b in f) for a in e), 4) if f else None,
                      'file_to_engine_max_mm': round(max(min(math.dist(a, b) for b in e) for a in f), 4) if f else None,
                      'segments': len(f) // 2}
    return out


def main(label):
    out = REPO / 'docs/consolidation/quality/runs' / ('carton-' + label)
    w = writers()
    numbers = {key: measure(key, spec, out / key, w) for key, spec in INPUTS.items()}
    (out / 'numbers.json').write_text(json.dumps(numbers, indent=1, ensure_ascii=False) + '\n')
    for key, rec in numbers.items():
        rb = rec['readback']
        print(key, rec['writer'], 'plates', rec['spot_plates'], 'trim', rec['trimbox_vs_cut_mm'], 'bleed',
              rec['bleedbox_vs_bleed_mm'], 'cut', rb['CUT'], 'crease', rb['CREASE'], 'fonts embedded',
              rec['fonts_all_embedded'], 'dxf', bool(rec['dxf']), 'cf2', bool(rec['cf2']))


if __name__ == '__main__':
    main(sys.argv[1])
