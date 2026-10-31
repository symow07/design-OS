"""Printed-board stand: 1:1 cut layout with named layers, provisional joints, BOM and the artwork-in-place sheet.

Every part derives from the validated assembly revision 3 and the part boxes the deterministic
render builds (blender_scripts/day5_display.py). Construction is PROVISIONAL pending fabricator:
no load, joint or fastener claim. Printed skins carry the Day 6 surface ids (revision 2).
"""
from pathlib import Path
import csv, json, math
import fitz
from . import fidelity_assets as fa

ROOT = fa.ROOT / 'docs/audit/day-6'
ASSEMBLY = ROOT / 'stand/assembly-spec.json'
SURFACES = ROOT / 'stand/surfaces-r2'
OUT = ROOT / 'cut-layout'
LAYERS = ('CUT', 'CREASE', 'GLUE', 'ARTWORK', 'DIMENSIONS')
MM = 72 / 25.4
SHEET_MM = (1200, 900)
GAP = 20
FLAP = 6            # wrap flap = board thickness, PROVISIONAL
PROVISIONAL = '[PROVISIONAL] pending fabricator'
SKIN_MATERIAL = 'printed board skin ' + PROVISIONAL
BOARD_MATERIAL = 'board 6 mm ' + PROVISIONAL


def sha(path):
    return fa.sha(path)


def parts(assembly=ASSEMBLY, surfaces=SURFACES):
    a = json.loads(Path(assembly).read_text()); bindings = json.loads((Path(surfaces) / 'surface-bindings.json').read_text())
    t = a['thickness']; tread = a['tread']; seats = a['seats']; w, d, h = a['realised_envelope_mm']
    header = a['header_height']; hole = a['hole']; positions = a['positions']
    rows = []
    def part(pid, name, qty, width, height, material, carried=None, holes=(), creases=(), flaps=(), derivation=''):
        rows.append({'id': pid, 'name': name, 'qty': qty, 'width_mm': round(width, 3), 'height_mm': round(height, 3), 'thickness_mm': t,
                     'material': material, 'print_surface_ids': list(carried or []), 'holes_mm': list(holes), 'creases_mm': list(creases),
                     'glue_flaps_mm': list(flaps), 'grain': 'along the longer edge ' + PROVISIONAL, 'derivation': derivation})
    part('P01', 'base board', 1, w, d, BOARD_MATERIAL, derivation='box base (0,0,0)-(180,150,6)')
    part('P02', 'rear panel (header board)', 1, w, h, BOARD_MATERIAL, derivation='box rear_panel (0,144,0)-(180,150,322); header.front skin glued on its front face z %d-%d' % (h - header, h))
    for i, seat in enumerate(seats):
        z0 = 0 if i == 0 else seats[i - 1]
        part('P%02d' % (3 + i), 'seat deck row %d' % (i + 1), 1, w, tread, BOARD_MATERIAL, derivation='box seat-%d (0,%.3f,%d)-(180,%.3f,%d)' % (i, i * tread, seat - t, (i + 1) * tread, seat))
        centres = [(p['xyz'][0], p['xyz'][1] - i * tread) for p in positions if p['row'] == i + 1]
        part('P%02d' % (6 + i), 'collar ring row %d (4 x dia %d openings)' % (i + 1, hole), 1, w, tread, BOARD_MATERIAL,
             holes=[{'cx': round(cx, 3), 'cy': round(cy, 3), 'diameter': hole} for cx, cy in centres],
             derivation='box collar-%d above seat %d; circular retention openings at the assembly positions' % (i, seat))
        part('P%02d' % (9 + i), 'riser row %d' % (i + 1), 1, w, seat - z0, BOARD_MATERIAL, derivation='box riser-%d (0,%.3f,%d)-(180,%.3f,%d)' % (i, i * tread, z0, i * tread + t, seat))
        if i > 0:
            part('P%02d' % (12 + i), 'longitudinal web row %d' % (i + 1), 3, tread, seat - 2 * t, BOARD_MATERIAL, derivation='box web-%d at x 6/87/168, z %d-%d' % (i, t, seat - t))
    part('P15', 'front lip board', 1, w, t, BOARD_MATERIAL, derivation='box front_lip (0,0,6)-(180,6,12)')
    part('P16', 'side support', 2, d, seats[-1], BOARD_MATERIAL, derivation='box side-support x 0-6 and 174-180, y 0-150, z 0-114')
    sizes = {s['surface_id']: s['size_mm'] for s in bindings['surfaces']}
    skins = [('S01', 'header.front', 'header skin'), ('S02', 'riser.3.front', 'riser 3 fascia skin'), ('S03', 'riser.2.front', 'riser 2 fascia skin'),
             ('S04', 'riser.1.front', 'riser 1 fascia skin'), ('S05', 'lip.front', 'lip fascia skin'), ('S06', 'side.left', 'left side skin'), ('S07', 'side.right', 'right side skin')]
    for pid, sid, name in skins:
        sw, sh = sizes[sid]
        creases = [{'from': [FLAP, FLAP], 'to': [FLAP + sw, FLAP]}, {'from': [FLAP, FLAP + sh], 'to': [FLAP + sw, FLAP + sh]},
                   {'from': [FLAP, FLAP], 'to': [FLAP, FLAP + sh]}, {'from': [FLAP + sw, FLAP], 'to': [FLAP + sw, FLAP + sh]}]
        flaps = [{'x': 0, 'y': 0, 'w': sw + 2 * FLAP, 'h': FLAP, 'edge': 'top'}, {'x': 0, 'y': FLAP + sh, 'w': sw + 2 * FLAP, 'h': FLAP, 'edge': 'bottom'},
                 {'x': 0, 'y': FLAP, 'w': FLAP, 'h': sh, 'edge': 'left'}, {'x': FLAP + sw, 'y': FLAP, 'w': FLAP, 'h': sh, 'edge': 'right'}]
        part(pid, name, 1, sw + 2 * FLAP, sh + 2 * FLAP, SKIN_MATERIAL, carried=[sid], creases=creases, flaps=flaps,
             derivation='surface %s %s x %s mm plus %d mm wrap flaps on four edges (flap = board thickness, fold allowance %d mm per fold, %s)' % (sid, sw, sh, FLAP, t, PROVISIONAL))
        rows[-1]['panel_mm'] = {'x': FLAP, 'y': FLAP, 'w': sw, 'h': sh}
    return {'schema': 'day6_cut_layout_parts/1', 'assembly_sha256': sha(assembly), 'assembly_revision': a['revision'],
            'surface_bindings_sha256': sha(Path(surfaces) / 'surface-bindings.json'), 'surfaces_revision': bindings['revision'],
            'board_thickness_mm': t, 'fold_allowance_rule': 'wrap flap = board thickness (6 mm) marked CREASE at the panel edge; glue flaps hatched on GLUE; %s' % PROVISIONAL,
            'load_claim': 'none; construction provisional pending fabricator', 'parts': rows}


def place(record):
    """Shelf packing of every physical piece on 1200 x 900 mm sheets, 1:1."""
    pages = []; x = GAP; y = GAP; row_h = 0; page = []
    for p in record['parts']:
        for k in range(p['qty']):
            w, h = p['width_mm'], p['height_mm']
            if x + w + GAP > SHEET_MM[0]:
                x = GAP; y += row_h + GAP; row_h = 0
            if y + h + GAP > SHEET_MM[1] - 40:
                pages.append(page); page = []; x = GAP; y = GAP; row_h = 0
            page.append({'id': p['id'], 'instance': k + 1, 'x': x, 'y': y, 'part': p}); x += w + GAP; row_h = max(row_h, h)
    pages.append(page); return pages


def _ocgs(doc):
    return {name: doc.add_ocg(name, on=True) for name in LAYERS}


def _bar(page, oc):
    y = SHEET_MM[1] - 20
    page.draw_line(fitz.Point(GAP * MM, y * MM), fitz.Point((GAP + 50) * MM, y * MM), color=(0, 0, 0), width=1.5, oc=oc)
    page.insert_text(fitz.Point(GAP * MM, (y - 3) * MM), '50 mm calibration bar: print at 100 %, disable Fit', fontsize=9, fontname='helv', oc=oc)


def _draw(page, oc, placed, artwork=None):
    for item in placed:
        p = item['part']; ox, oy = item['x'], item['y']; w, h = p['width_mm'], p['height_mm']
        page.draw_rect(fitz.Rect(ox * MM, oy * MM, (ox + w) * MM, (oy + h) * MM), color=(0, 0, 0), width=0.6, oc=oc['CUT'])
        for hole in p['holes_mm']:
            r = hole['diameter'] / 2; page.draw_circle(fitz.Point((ox + hole['cx']) * MM, (oy + hole['cy']) * MM), r * MM, color=(0, 0, 0), width=0.6, oc=oc['CUT'])
        for c in p['creases_mm']:
            page.draw_line(fitz.Point((ox + c['from'][0]) * MM, (oy + c['from'][1]) * MM), fitz.Point((ox + c['to'][0]) * MM, (oy + c['to'][1]) * MM),
                           color=(0, 0, 1), width=0.5, dashes='[4 3] 0', oc=oc['CREASE'])
        for f in p['glue_flaps_mm']:
            x0, y0, x1, y1 = ox + f['x'], oy + f['y'], ox + f['x'] + f['w'], oy + f['y'] + f['h']
            step = 3; s = x0 - (y1 - y0)
            while s < x1:                                   # 45-degree hatch clipped to the flap rectangle
                xa, xb = max(s, x0), min(s + (y1 - y0), x1)
                pa = fitz.Point(xa * MM, (y1 - (xa - s)) * MM); pb = fitz.Point(xb * MM, (y1 - (xb - s)) * MM)
                page.draw_line(pa, pb, color=(0, .5, 0), width=0.3, oc=oc['GLUE']); s += step
        label = '%s-%d/%d %s  %.1f x %.1f mm  t %d  %s' % (p['id'], item['instance'], p['qty'], p['name'], w, h, p['thickness_mm'], ','.join(p['print_surface_ids']) or 'no print')
        page.insert_text(fitz.Point(ox * MM, (oy - 2) * MM), label, fontsize=7, fontname='helv', oc=oc['DIMENSIONS'])
        page.draw_line(fitz.Point(ox * MM, (oy + h + 4) * MM), fitz.Point((ox + w) * MM, (oy + h + 4) * MM), color=(.3, .3, .3), width=0.3, oc=oc['DIMENSIONS'])
        page.insert_text(fitz.Point((ox + w / 2 - 6) * MM, (oy + h + 8) * MM), '%.1f' % w, fontsize=6, fontname='helv', oc=oc['DIMENSIONS'])
        page.draw_line(fitz.Point((ox + 4) * MM, (oy + h - 4) * MM), fitz.Point((ox + 14) * MM, (oy + h - 4) * MM), color=(.5, 0, .5), width=0.5, oc=oc['DIMENSIONS'])
        page.insert_text(fitz.Point((ox + 15) * MM, (oy + h - 3) * MM), 'grain ' + PROVISIONAL, fontsize=5, fontname='helv', oc=oc['DIMENSIONS'])
        if artwork is not None and p['print_surface_ids']:
            sid = p['print_surface_ids'][0]; panel = p['panel_mm']
            rect = fitz.Rect((ox + panel['x']) * MM, (oy + panel['y']) * MM, (ox + panel['x'] + panel['w']) * MM, (oy + panel['y'] + panel['h']) * MM)
            with fitz.open(artwork[sid]) as src:
                page.show_pdf_page(rect, src, 0, oc=oc['ARTWORK'])


def _index(page, oc, record, pages_count):
    y = 25
    def line(text, size, dy):
        nonlocal y; page.insert_text(fitz.Point(GAP * MM, y * MM), text, fontsize=size, fontname='helv', oc=oc['DIMENSIONS']); y += dy
    line('BBROSE Sun Repair twelve-bottle countertop stand - CUT LAYOUT + BOM, 1:1, Day 6 (revision 2 surfaces)', 13, 8)
    line('Construction PROVISIONAL pending fabricator: no load, joint or fastener claim. Board 6 mm provisional. Layers: CUT (solid), CREASE (dashed, folds), GLUE (hatched flaps), ARTWORK (printed surface in place), DIMENSIONS.', 8, 6)
    line('Assembly revision %d sha256 %s...  surfaces revision %d bindings %s...  sheets: %d of %d x %d mm' % (record['assembly_revision'], record['assembly_sha256'][:16], record['surfaces_revision'], record['surface_bindings_sha256'][:16], pages_count, *SHEET_MM), 8, 7)
    line('Fold allowance: ' + record['fold_allowance_rule'], 8, 8)
    line('BOM  id | part | qty | nominal flat size mm | material | thickness | print surface id', 9, 6)
    for p in record['parts']:
        line('%s | %s | %d | %.1f x %.1f | %s | %d mm | %s' % (p['id'], p['name'], p['qty'], p['width_mm'], p['height_mm'], p['material'], p['thickness_mm'], ','.join(p['print_surface_ids']) or '-'), 7, 4.6)
    line('Every quantity in the BOM appears once per piece on the sheets. Printed skins wrap 6 mm flaps over the board edge (CREASE at the panel edge, GLUE on the flaps). Tread tops and the rear panel below the header stay unprinted (the Day 6 surfaces are the seven mapped faces).', 7, 5)


def build(destination=OUT, assembly=ASSEMBLY, surfaces=SURFACES):
    dst = Path(destination); dst.mkdir(parents=True, exist_ok=True)
    record = parts(assembly, surfaces); pages = place(record)
    for p_index, pg in enumerate(pages):
        for item in pg: item['page'] = p_index + 2
    record['pages'] = [[{k: v for k, v in item.items() if k != 'part'} for item in pg] for pg in pages]
    (dst / 'parts.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    artwork = {s: Path(surfaces) / s / 'artwork.pdf' for s in [p['print_surface_ids'][0] for p in record['parts'] if p['print_surface_ids']]}
    for name, art in (('cut-layout.pdf', None), ('cut-layout-with-artwork.pdf', artwork)):
        doc = fitz.open(); oc = _ocgs(doc)
        page = doc.new_page(width=SHEET_MM[0] * MM, height=SHEET_MM[1] * MM); _index(page, oc, record, len(pages)); _bar(page, oc['DIMENSIONS'])
        for pg in pages:
            page = doc.new_page(width=SHEET_MM[0] * MM, height=SHEET_MM[1] * MM); _draw(page, oc, pg, art); _bar(page, oc['DIMENSIONS'])
        doc.set_metadata({'title': 'BBROSE stand cut layout 1:1 ' + ('with artwork' if art else 'cut only') + ' - PROVISIONAL'}); doc.save(dst / name); doc.close()
    with fitz.open(dst / 'cut-layout-with-artwork.pdf') as doc:
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=40).save(dst / ('cut-layout-with-artwork-page-%d.png' % (i + 1)))
    svg(record, pages, dst / 'cut-layout.svg')
    bom = [{k: p[k] for k in ('id', 'name', 'qty', 'width_mm', 'height_mm', 'material', 'thickness_mm')} | {'print_surface_ids': ','.join(p['print_surface_ids'])} for p in record['parts']]
    (dst / 'bom.json').write_text(json.dumps({'schema': 'day6_bom/1', 'load_claim': record['load_claim'], 'rows': bom}, indent=2, ensure_ascii=False) + '\n')
    with (dst / 'bom.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(bom[0].keys())); w.writeheader(); w.writerows(bom)
    (dst / 'bom-and-parts.md').write_text('| id | part | qty | nominal flat size (mm) | material | t (mm) | print surface |\n|---|---|---:|---|---|---:|---|\n' +
                                          ''.join('| %s | %s | %d | %.1f x %.1f | %s | %d | %s |\n' % (p['id'], p['name'], p['qty'], p['width_mm'], p['height_mm'], p['material'], p['thickness_mm'], p['print_surface_ids'] or '-') for p in bom) +
                                          '\nAll construction PROVISIONAL pending fabricator; no load, joint or fastener claim. Fold allowance: %s\n' % record['fold_allowance_rule'])
    illustrator_compare(dst)
    record['outputs'] = {n: sha(dst / n) for n in ('cut-layout.pdf', 'cut-layout-with-artwork.pdf', 'cut-layout.svg', 'bom.json', 'bom.csv', 'parts.json', 'native-compare.jsx')}
    (dst / 'parts.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    return record


def svg(record, pages, path):
    chunks = ['<svg xmlns="http://www.w3.org/2000/svg" width="%dmm" height="%dmm" viewBox="0 0 %d %d">' % (SHEET_MM[0], SHEET_MM[1] * len(pages), SHEET_MM[0], SHEET_MM[1] * len(pages))]
    layers = {name: [] for name in LAYERS}
    for p_index, pg in enumerate(pages):
        dy = p_index * SHEET_MM[1]
        for item in pg:
            p = item['part']; ox, oy = item['x'], item['y'] + dy
            layers['CUT'].append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="#000" stroke-width="0.3"/>' % (ox, oy, p['width_mm'], p['height_mm']))
            for hole in p['holes_mm']:
                layers['CUT'].append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="#000" stroke-width="0.3"/>' % (ox + hole['cx'], oy + hole['cy'], hole['diameter'] / 2))
            for c in p['creases_mm']:
                layers['CREASE'].append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#00f" stroke-width="0.25" stroke-dasharray="4 3"/>' % (ox + c['from'][0], oy + c['from'][1], ox + c['to'][0], oy + c['to'][1]))
            for f in p['glue_flaps_mm']:
                layers['GLUE'].append('<rect x="%g" y="%g" width="%g" height="%g" fill="#9c9" fill-opacity="0.4" stroke="none"/>' % (ox + f['x'], oy + f['y'], f['w'], f['h']))
            layers['DIMENSIONS'].append('<text x="%g" y="%g" font-size="3">%s %d/%d %.1f x %.1f mm %s</text>' % (ox, oy - 1.5, p['id'], item['instance'], p['qty'], p['width_mm'], p['height_mm'], ','.join(p['print_surface_ids'])))
    for name in LAYERS:
        chunks.append('<g id="%s">%s</g>' % (name, ''.join(layers[name])))
    chunks.append('</svg>'); Path(path).write_text('\n'.join(chunks))


def expected_counts(record):
    pieces = [(p, k) for p in record['parts'] for k in range(p['qty'])]
    return {'CUT': len(pieces) + sum(len(p['holes_mm']) for p, _ in pieces), 'CREASE': sum(len(p['creases_mm']) for p, _ in pieces),
            'GLUE': sum(len(p['glue_flaps_mm']) for p, _ in pieces), 'DIMENSIONS': len(pieces), 'ARTWORK': 0}


def illustrator_compare(folder=OUT):
    """Write the Illustrator element-compare script (NOT executed here): native layers from parts.json, then a census per layer."""
    folder = Path(folder); record = json.loads((folder / 'parts.json').read_text()); pages = place(record)
    items = []
    for p_index, pg in enumerate(pages):
        for item in pg:
            p = item['part']; items.append({'id': p['id'], 'x': item['x'], 'y': item['y'] + p_index * SHEET_MM[1], 'w': p['width_mm'], 'h': p['height_mm'], 'holes': p['holes_mm'],
                                            'creases': p['creases_mm'], 'flaps': p['glue_flaps_mm'], 'label': '%s %.1fx%.1f' % (p['id'], p['width_mm'], p['height_mm'])})
    data = {'items': items, 'mm': MM, 'sheet': [SHEET_MM[0], SHEET_MM[1] * len(pages)], 'out': str(folder / 'cut-layout-native.ai'), 'census': str(folder / 'native-compare-census.json'), 'layers': list(LAYERS)}
    js = r'''(function(){var D=__DATA__,doc=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,R={layers:{}};
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"';}
function js(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(js(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+js(v[k]));return '{'+a.join(',')+'}';}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;var W=D.sheet[0]*D.mm,H=D.sheet[1]*D.mm;doc=app.documents.add(DocumentColorSpace.RGB,W,H);doc.artboards[0].artboardRect=[0,H,W,0];
var L={};for(var i=0;i<D.layers.length;i++){var layer=(i===0)?doc.layers[0]:doc.layers.add();layer.name=D.layers[i];L[D.layers[i]]=layer;}
function Y(y){return H-y*D.mm;}
for(var i=0;i<D.items.length;i++){var it=D.items[i];var r=L['CUT'].pathItems.rectangle(Y(it.y),it.x*D.mm,it.w*D.mm,it.h*D.mm);r.filled=false;r.stroked=true;r.name=it.id;
for(var k=0;k<it.holes.length;k++){var hh=it.holes[k];var c=L['CUT'].pathItems.ellipse(Y(it.y+hh.cy-hh.diameter/2),(it.x+hh.cx-hh.diameter/2)*D.mm,hh.diameter*D.mm,hh.diameter*D.mm);c.filled=false;c.stroked=true;}
for(var k=0;k<it.creases.length;k++){var cr=it.creases[k];var p=L['CREASE'].pathItems.add();p.setEntirePath([[(it.x+cr.from[0])*D.mm,Y(it.y+cr.from[1])],[(it.x+cr.to[0])*D.mm,Y(it.y+cr.to[1])]]);p.filled=false;p.stroked=true;p.strokeDashes=[4,3];}
for(var k=0;k<it.flaps.length;k++){var f=it.flaps[k];var g=L['GLUE'].pathItems.rectangle(Y(it.y+f.y),(it.x+f.x)*D.mm,f.w*D.mm,f.h*D.mm);g.stroked=false;g.filled=true;}
var t=L['DIMENSIONS'].textFrames.pointText([it.x*D.mm,Y(it.y-2)]);t.contents=it.label;}
for(var i=0;i<doc.layers.length;i++){var ly=doc.layers[i];R.layers[ly.name]={paths:ly.pathItems.length,texts:ly.textFrames.length};}
var o=new IllustratorSaveOptions();o.pdfCompatible=true;doc.saveAs(new File(D.out),o);R.saved=true;}
catch(e){R.saved=false;R.error=String(e);}finally{if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);if(prior)prior.activate();app.userInteractionLevel=old;}
var f=new File(D.census);f.encoding='UTF-8';f.open('w');f.write(js(R));f.close();return js({saved:R.saved});})();'''
    (folder / 'native-compare.jsx').write_text(js.replace('__DATA__', json.dumps(data)))
    (folder / 'native-compare-expected.json').write_text(json.dumps({'expected_counts_per_layer': expected_counts(record), 'executed': False,
                                                                     'note': 'Integrator runs native-compare.jsx in Illustrator, then compare_census(census, parts)'}, indent=2) + '\n')
    return data


def compare_census(census, record):
    expected = expected_counts(record); found = census['layers'] if isinstance(census['layers'], dict) else {}
    rows = {}
    for layer in LAYERS:
        got = found[layer] if layer in found and isinstance(found[layer], dict) else {}
        key = 'texts' if layer == 'DIMENSIONS' else 'paths'
        count = got[key] if key in got else None
        rows[layer] = {'expected': expected[layer], 'found': count, 'passed': count == expected[layer]}
    return {'passed': bool(census['saved']) and all(r['passed'] for r in rows.values()), 'layers': rows}


if __name__ == '__main__':
    import sys
    r = build(); print(json.dumps({'parts': len(r['parts']), 'pieces': sum(p['qty'] for p in r['parts']), 'pages': len(r['pages']), 'outputs': r['outputs']}, indent=2))
