"""Deterministic HAYAT drawing, blind inputs and derivative difference evidence."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw

from . import product_drawing as pd
from . import round_balm_master as m
from .round_files_export import set_layers
from . import round_balm_review as review

OUT=m.OUT
PANELS=review.PANELS


def drawing(out=OUT,tint='Rosewater'):
    out=Path(out)
    rec=pd.draw('HAYAT / '+tint,
                [('body',out/'body-flat.png',(58.5,42),1,40),
                 ('cap',out/'cap-flat.png',(58.5,32),1,30)],
                18,29.25,58.5-np.pi*18,'#38242A',out/'drawing.png')
    m.dump(out/'drawing.json',rec)
    return rec


def blind_sheet(folder,destination):
    """Identical nine-panel reading layout, names only; no version labels."""
    crop=json.loads((m.PICK/'crop.json').read_text())['panels']
    k=5
    rows=[('body','cap','label'),('back','side_left','front','side_right'),('top_end','bottom_end')]
    sizes={p:tuple(round(v*k) for v in crop[p]['mm']) for p in PANELS}
    heights=[max(sizes[p][1] for p in row)+25 for row in rows]
    widths=[sum(sizes[p][0]+20 for p in row)+20 for row in rows]
    sheet=Image.new('RGB',(max(widths),sum(heights)+60),'white');d=ImageDraw.Draw(sheet)
    y=20
    for row,h in zip(rows,heights):
        x=20
        for panel in row:
            path=Path(folder)/(panel+'.png') if Path(folder)==m.PICK else Path(folder)/'panels'/(panel+'-flat.png')
            with Image.open(path) as im:sheet.paste(im.convert('RGB').resize(sizes[panel],Image.Resampling.LANCZOS),(x,y+20))
            d.text((x,y),panel,fill='black');x+=sizes[panel][0]+20
        y+=h+10
    sheet.save(destination)


def prepare_readings():
    folder=OUT/'reading-inputs';folder.mkdir(exist_ok=True)
    for name,path in [('source',m.PICK),('master',OUT)]:blind_sheet(path,folder/(name+'.png'))
    rows=[{'kind':name,'path':m.rel(folder/(name+'.png')),'sha256':m.sha(folder/(name+'.png'))} for name in ('source','master')]
    seed=hashlib.sha256(''.join(r['sha256'] for r in rows).encode()).hexdigest()
    # Deterministic hash order prevents editorial assignment of version labels.
    rows.sort(key=lambda r:hashlib.sha256((seed+r['sha256']).encode()).hexdigest())
    record={'schema':'hayat_blind_reading_map/1','seed':seed,'question':'The packaging idea a stranger sees, in ten words.',
            'labels':{f'K{i+1}':row for i,row in enumerate(rows)},
            'withheld_from_calls':['kind','path','sha256','seed'],'must_be_committed_before_calls':True}
    m.dump(OUT/'reading-map.json',record)
    return record


def _canonical(value):
    """Stable saved-file geometry, independent of xrefs, subset IDs and compression."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if hasattr(value, '__iter__'):
        return [_canonical(v) for v in value]
    return str(value)


def _font_family(name):
    return re.sub(r'^[A-Z]{6}\+', '', str(name)).lstrip('/')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _replace_tint(copy, tint):
    return str(copy).replace('ROSEWATER', tint).replace('Rosewater', tint.title())


def _all_layers_document(path):
    # A fresh parse is essential: MuPDF caches optional-content visibility. This
    # temporary in-memory stream never changes the real file or its print flags.
    with fitz.open(path) as original:
        set_layers(original, set(m.LAYERS))
        for x in original.get_ocgs():
            original.xref_set_key(x, 'Usage', '<</View <</ViewState /ON>> /Print <</PrintState /ON>>>>')
        return fitz.open(stream=original.tobytes(), filetype='pdf')


def _raster_placements(doc):
    masks = {row[0]: row[1] for row in doc[0].get_images(full=True)}
    decoded = {}
    result = []
    for info in doc[0].get_image_info(xrefs=True):
        xref = info['xref']
        if xref not in decoded:
            pix = fitz.Pixmap(doc, xref)
            if masks.get(xref):
                pix = fitz.Pixmap(pix, fitz.Pixmap(doc, masks[xref]))
            if pix.colorspace and pix.colorspace.n != 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            decoded[xref] = {'pixel_sha256': hashlib.sha256(pix.samples).hexdigest(),
                             'width': pix.width, 'height': pix.height,
                             'channels': pix.n, 'alpha': pix.alpha}
        result.append(dict(decoded[xref], transform=_canonical(info['transform']),
                           bbox=_canonical(info['bbox'])))
    return sorted(result, key=lambda row: json.dumps(row, sort_keys=True))


def _vector_layers(doc):
    by_layer = {name: [] for name in m.LAYERS}
    # Every path and clipping path is read, including hidden die/guides. Text is
    # evaluated separately; image resources and their placements are above.
    for row in doc[0].get_drawings(extended=True):
        layer = row.get('layer', '')
        if row['type'] == 'group':
            fields = ('type', 'level', 'isolated', 'knockout', 'blendmode', 'opacity')
        else:
            fields = ('type', 'items', 'even_odd', 'closePath', 'scissor', 'level',
                      'fill', 'fill_opacity', 'color', 'stroke_opacity', 'width',
                      'lineCap', 'lineJoin', 'dashes')
        by_layer.setdefault(layer, []).append(_canonical({k: row[k] for k in fields if k in row}))
    return by_layer


def _text_evidence(doc, allowances):
    outside = []
    inside = {box['name']: {'chars': [], 'styles': [], 'glyph_styles': []} for box in allowances}
    for span in doc[0].get_texttrace():
        style = _canonical({k: span.get(k) for k in ('size', 'color', 'opacity', 'type', 'dir', 'wmode', 'linewidth', 'layer')})
        style['font'] = _font_family(span['font'])
        for char in span['chars']:
            unicode_number, _subset_glyph_id, origin, bounds = char
            x = (bounds[0] + bounds[2]) / (2 * m.PT)
            y = (bounds[1] + bounds[3]) / (2 * m.PT)
            hits = [a for a in allowances if a['box_mm'][0] - .01 <= x <= a['box_mm'][2] + .01 and
                    a['box_mm'][1] - .01 <= y <= a['box_mm'][3] + .01]
            if not hits and chr(unicode_number).isspace():
                # LTR trailing space can start inside the frame and extend out;
                # RTL trailing space can end exactly on its left boundary while
                # its origin and centre are outside. Neither has painted ink.
                ox, oy = origin[0] / m.PT, origin[1] / m.PT
                hits = [a for a in allowances if a['kind'] == 'area-reflow' and
                        a['box_mm'][1] - .01 <= oy <= a['box_mm'][3] + .01 and
                        (a['box_mm'][0] - .01 <= ox <= a['box_mm'][2] + .01 or
                         any(abs(edge / m.PT - boundary) <= .01
                             for edge in (bounds[0], bounds[2])
                             for boundary in (a['box_mm'][0], a['box_mm'][2])))]
            if len(hits) > 1:
                raise ValueError('overlapping derivative text allowances')
            if hits:
                item = inside[hits[0]['name']]
                item['chars'].append(chr(unicode_number))
                item['glyph_styles'].append(dict(style, character=unicode_number))
                if style not in item['styles']:
                    item['styles'].append(style)
            else:
                outside.append(dict(style, character=unicode_number,
                                    origin=_canonical(origin), bounds=_canonical(bounds)))
    # PDF text object fragmentation and subset glyph numbers are immaterial; each
    # Unicode glyph, font, colour, size and actual placement outside tint/area
    # regions must remain identical.
    outside.sort(key=lambda row: json.dumps(row, sort_keys=True))
    for value in inside.values():
        value['text'] = ''.join(value.pop('chars'))
        value['styles'].sort(key=lambda row: json.dumps(row, sort_keys=True))
    return {'fixed_glyphs': outside, 'allowed_regions': inside}


def _fixed_area_styles(region, source_copy, tint=None):
    """Compare fixed characters' fonts/colours/sizes even when area text reflows.

    A unique set of styles cannot detect one Latin letter accidentally using
    the Arabic face when both faces already occur elsewhere in the same frame.
    Normalize contextual Arabic forms and remove only the declared tint words;
    retain a multiset of every remaining visible character and its full style.
    """
    glyphs = []
    for row in region['glyph_styles']:
        style = {key: value for key, value in row.items() if key != 'character'}
        glyphs.extend(dict(style, character=ord(char)) for char in unicodedata.normalize('NFKC', chr(row['character']))
                      if not char.isspace())
    text = ''.join(chr(row['character']) for row in glyphs)
    removed = set()
    all_tints_found = True
    for source in ('ROSEWATER', 'Rosewater'):
        expected = source_copy.count(source)
        target = source if tint is None else _replace_tint(source, tint)
        token = ''.join(target.split())
        start = 0
        for _ in range(expected):
            at = text.find(token, start)
            if at < 0:
                all_tints_found = False
                break
            removed.update(range(at, at + len(token)))
            start = at + len(token)
    counts = Counter(json.dumps(row, sort_keys=True) for i, row in enumerate(glyphs) if i not in removed)
    return {'sha256': _digest(sorted(counts.items())), 'fixed_characters': sum(counts.values()),
            'declared_tint_sequences_found': all_tints_found}


def _layer_state(path):
    with fitz.open(path) as doc:
        locked = doc.xref_get_key(doc.pdf_catalog(), 'OCProperties/D/Locked')[1]
        layer_config = doc.get_layer()
        return [{'name': ocg['name'], 'locked': bool(re.search(r'\b' + str(xref) + r' 0 R\b', locked)),
                 'on': xref in layer_config.get('on', []),
                 'usage': doc.xref_get_key(xref, 'Usage')[1]}
                for xref, ocg in doc.get_ocgs().items()]


def _render_outside_allowances(a, b, allowances):
    """Catch font-program or colour-profile changes invisible to object names."""
    dpi = 300
    pa, pb = a[0].get_pixmap(dpi=dpi, alpha=False), b[0].get_pixmap(dpi=dpi, alpha=False)
    if (pa.width, pa.height, pa.n) != (pb.width, pb.height, pb.n):
        return {'holds': False, 'reason': 'render dimensions differ', 'dpi': dpi}
    aa = np.frombuffer(pa.samples, np.uint8).reshape(pa.height, pa.width, pa.n)
    bb = np.frombuffer(pb.samples, np.uint8).reshape(pb.height, pb.width, pb.n)
    permitted = np.zeros(aa.shape[:2], bool)
    for box in allowances:
        # One pixel only for anti-alias coverage exactly on the physical zone edge.
        x0, y0, x1, y1 = box['box_mm']
        ix0, iy0 = max(0, int(np.floor(x0 * dpi / 25.4)) - 1), max(0, int(np.floor(y0 * dpi / 25.4)) - 1)
        ix1, iy1 = min(pa.width, int(np.ceil(x1 * dpi / 25.4)) + 1), min(pa.height, int(np.ceil(y1 * dpi / 25.4)) + 1)
        permitted[iy0:iy1, ix0:ix1] = True
    changed = np.any(aa != bb, axis=2)
    outside = changed & ~permitted
    return {'holds': not bool(outside.any()), 'dpi': dpi, 'changed_pixels_outside_allowances': int(outside.sum()),
            'changed_pixels_inside_allowances': int((changed & permitted).sum()),
            'all_layers_including_hidden_die_guides': True,
            'master_outside_pixel_sha256': hashlib.sha256(aa[~permitted].tobytes()).hexdigest(),
            'derivative_outside_pixel_sha256': hashlib.sha256(bb[~permitted].tobytes()).hexdigest()}


def compare_saved_surfaces(master, derivative, allowances=(), tint='ROSEWATER'):
    """Independent saved-file diff, including currently hidden vector content."""
    master, derivative = Path(master), Path(derivative)
    with fitz.open(master) as a, fitz.open(derivative) as b:
        page_geometry = _canonical([a[0].rect, a[0].trimbox, a[0].bleedbox]) == _canonical([b[0].rect, b[0].trimbox, b[0].bleedbox])
    with _all_layers_document(master) as a, _all_layers_document(derivative) as b:
        a_rasters, b_rasters = _raster_placements(a), _raster_placements(b)
        a_vectors, b_vectors = _vector_layers(a), _vector_layers(b)
        a_text, b_text = _text_evidence(a, allowances), _text_evidence(b, allowances)
        rendered = _render_outside_allowances(a, b, allowances)
        a_fonts = sorted({_font_family(row[3]) for row in a[0].get_fonts(full=True)})
        b_fonts = sorted({_font_family(row[3]) for row in b[0].get_fonts(full=True)})
    region_checks = []
    compact = lambda text: ''.join(unicodedata.normalize('NFKC', text).split())
    for box in allowances:
        x = a_text['allowed_regions'][box['name']]
        y = b_text['allowed_regions'][box['name']]
        style_same = x['styles'] == y['styles'] and bool(x['styles'])
        fixed_x = _fixed_area_styles(x, box['copy'])
        fixed_y = _fixed_area_styles(y, box['copy'], tint)
        fixed_same = fixed_x['sha256'] == fixed_y['sha256'] and fixed_x['fixed_characters'] == fixed_y['fixed_characters']
        copy_ok = True
        if box['kind'] == 'tint':
            copy_ok = compact(x['text']) == compact(box['copy']) and compact(y['text']) == compact(_replace_tint(box['copy'], tint))
        region_checks.append({'name': box['name'], 'kind': box['kind'], 'box_mm': box['box_mm'],
                              'same_font_size_colour': style_same, 'actual_tint_copy_matches': copy_ok,
                              'fixed_character_styles_identical': fixed_same,
                              'declared_tint_sequences_found': fixed_x['declared_tint_sequences_found'] and fixed_y['declared_tint_sequences_found'],
                              'fixed_character_styles': {'master': fixed_x, 'derivative': fixed_y},
                              'master_visible_text': x['text'], 'derivative_visible_text': y['text'],
                              'master_styles': x['styles'], 'derivative_styles': y['styles']})
    layer_checks = {name: a_vectors.get(name, []) == b_vectors.get(name, [])
                    for name in sorted(set(a_vectors) | set(b_vectors))}
    checks = {'page_trim_bleed_geometry_identical': page_geometry,
              'decoded_painting_pixels_and_placement_identical': a_rasters == b_rasters,
              'all_vector_paths_strokes_clips_identical': all(layer_checks.values()),
              'fixed_live_glyphs_font_colour_size_position_identical': a_text['fixed_glyphs'] == b_text['fixed_glyphs'],
              'tint_and_area_fonts_sizes_colours_identical': all(x['same_font_size_colour'] for x in region_checks),
              'fixed_area_character_styles_identical': all(x['fixed_character_styles_identical'] for x in region_checks),
              'declared_tint_sequences_found': all(x['declared_tint_sequences_found'] for x in region_checks),
              'actual_tint_words_match': all(x['actual_tint_copy_matches'] for x in region_checks),
              'font_families_identical': a_fonts == b_fonts,
              'layer_visibility_lock_print_identical': _layer_state(master) == _layer_state(derivative),
              'rendered_pixels_outside_tint_and_area_regions_identical': rendered['holds']}
    return {'master_sha256': m.sha(master), 'derivative_sha256': m.sha(derivative),
            'checks': checks, 'holds': all(checks.values()), 'vector_layer_checks': layer_checks,
            'rendered_pixel_proof': rendered,
            'decoded_raster_placements': {'master': a_rasters, 'derivative': b_rasters},
            'vector_layer_sha256': {name: {'master': _digest(a_vectors.get(name, [])), 'derivative': _digest(b_vectors.get(name, []))} for name in layer_checks},
            'fixed_glyphs': {'master_count': len(a_text['fixed_glyphs']), 'derivative_count': len(b_text['fixed_glyphs']),
                             'master_sha256': _digest(a_text['fixed_glyphs']), 'derivative_sha256': _digest(b_text['fixed_glyphs'])},
            'text_allowances': region_checks, 'font_families': {'master': a_fonts, 'derivative': b_fonts},
            'normalization': 'Ignore PDF xrefs, compressed-image bytes, six-letter font subset tags and glyph IDs. Geometry rounded to0.0001pt; decoded raster pixels exact. Preserve vector drawing order within each layer.'}


def _type_specs(master_rows, derivative_rows, tint, area_preview_names=()):
    a = [r for r in master_rows if r['name'] not in area_preview_names]
    b = [r for r in derivative_rows if r['name'] not in area_preview_names]
    same_names = len(a) == len(b) and len({r['name'] for r in a}) == len(a) and {r['name'] for r in a} == {r['name'] for r in b}
    other = {r['name']: r for r in b}
    rows = []
    allowances = []
    for x in a:
        y = other.get(x['name'])
        if y is None:
            rows.append({'name': x['name'], 'holds': False, 'reason': 'missing type element'})
            continue
        is_tint = 'ROSEWATER' in x['copy'] or 'Rosewater' in x['copy']
        checks = {'copy': y['copy'] == _replace_tint(x['copy'], tint)}
        for key in ('face', 'font_path', 'size_pt', 'color', 'zone_mm'):
            checks[key] = _canonical(x.get(key)) == _canonical(y.get(key))
        if not is_tint:
            for key in ('ink_box_mm', 'baseline_mm', 'display', 'logical_actual_text'):
                checks[key] = _canonical(x.get(key)) == _canonical(y.get(key))
        else:
            allowances.append({'name': x['name'], 'kind': 'tint', 'copy': x['copy'], 'box_mm': x['zone_mm']})
        rows.append({'name': x['name'], 'from': x['copy'], 'to': y['copy'], 'tint_change': is_tint,
                     'requested_pre_fit_size_pt': {'master': x.get('requested_size_pt'), 'derivative': y.get('requested_size_pt'),
                                                   'scope': 'Builder input only; actual saved font size is checked exactly.'},
                     'checks': checks, 'holds': all(checks.values())})
    return {'same_element_count_and_names': same_names, 'rows': rows,
            'holds': same_names and all(row['holds'] for row in rows)}, allowances


def _area_specs(folder, tint, surface='carton'):
    expected_count = {'carton': 3, 'leaflet': 6}[surface]
    base = json.loads((OUT / f'{surface}-native-frames.json').read_text())['frames']
    other = json.loads((folder / f'{surface}-native-frames.json').read_text())['frames']
    rows = []
    same_names = (len(base) == len(other) == expected_count and
                  {r['name'] for r in base} == {r['name'] for r in other} and
                  len({r['name'] for r in base}) == expected_count)
    by_name = {r['name']: r for r in other}
    for x in base:
        y = by_name.get(x['name'])
        checks = {'present': y is not None}
        if y:
            checks['full_logical_copy'] = y['copy'] == _replace_tint(x['copy'], tint)
            for key in ('face', 'size_pt', 'leading_pt', 'box_mm', 'language', 'color', 'ltr_paragraph_indices'):
                checks[key] = _canonical(x.get(key)) == _canonical(y.get(key))
        rows.append({'name': x['name'], 'checks': checks, 'holds': all(checks.values())})
    return {'surface': surface, 'expected_count': expected_count, 'exact_same_named_frames': same_names, 'rows': rows,
            'holds': same_names and all(row['holds'] for row in rows)}, base, other


def _native_evidence(folder, filename, expected_frames=()):
    path = folder / 'native-checks' / (Path(filename).stem + '.json')
    if not path.exists():
        return {'holds': False, 'reason': 'native Illustrator census absent'}
    census = json.loads(path.read_text())
    frames = census['areaFrames']
    reopened = census['saved_file_reopen']
    checks = {'native_census_passes': census.get('holds') is True,
              'exact_final_file_hash': census.get('final_sha256') == m.sha(folder / filename),
              'saved_file_reopened': reopened['reopened'] is True and reopened['holds'] is True,
              'reopened_exact_final_file_hash': reopened['final_sha256'] == m.sha(folder / filename)}
    if expected_frames:
        checks['exact_full_native_frames'] = (len(frames) == len(expected_frames) and
            {row['name'] for row in frames} == {row['name'] for row in expected_frames} and
            len({row['name'] for row in frames}) == len(expected_frames))
        actual = {row['name']: row for row in frames}
        checks['full_copy_read_back_from_native_area_text'] = all(
            f['name'] in actual and actual[f['name']]['fullContents'] == f['copy'] for f in expected_frames)
        checks['all_area_copy_visible_on_type'] = all(row['layer'] == 'type' and row['kind'] == 'TextType.AREATEXT'
            and row['overflow'] is False for row in frames)
    return {'path': m.rel(path), 'checks': checks, 'holds': all(checks.values())}


def derivative_negative_controls():
    """Prove the saved-file comparator notices changes to native hidden content."""
    import tempfile
    master = OUT / 'body-wrap.ai'
    positive = compare_saved_surfaces(master, master)
    controls = []
    with tempfile.TemporaryDirectory(prefix='hayat-diff-control-') as temporary:
        for layer in ('die', 'mark'):
            path = Path(temporary) / (layer + '-mutation.ai')
            with fitz.open(master) as doc:
                ocg = next(x for x, row in doc.get_ocgs().items() if row['name'] == layer)
                doc[0].draw_line(fitz.Point(2, 2), fitz.Point(11, 9), color=(1, 0, 0), width=.37, oc=ocg)
                doc.save(path)
            proof = compare_saved_surfaces(master, path)
            controls.append({'layer': layer, 'mutation': 'Insert a red .37pt vector path from (2,2) to (11,9)pt on this actual OCG in a temporary copy; production file untouched.',
                             'rejected': not proof['holds'], 'target_layer_difference_detected': not proof['vector_layer_checks'][layer],
                             'unchanged_raster_confirmed': proof['checks']['decoded_painting_pixels_and_placement_identical'],
                             'unchanged_fixed_glyphs_confirmed': proof['checks']['fixed_live_glyphs_font_colour_size_position_identical']})
    report = {'schema': 'hayat_derivative_negative_controls/1', 'master_sha256': m.sha(master),
              'self_comparison_passes': positive['holds'], 'controls': controls,
              'holds': positive['holds'] and all(all(row[k] for k in ('rejected', 'target_layer_difference_detected', 'unchanged_raster_confirmed', 'unchanged_fixed_glyphs_confirmed')) for row in controls)}
    m.dump(OUT / 'evidence/derivative-negative-controls.json', report)
    return report


def derivatives():
    controls = derivative_negative_controls()
    rows = []
    base_build = json.loads((OUT / 'surface-builds.json').read_text())
    base_build['carton'] = json.loads((OUT / 'carton.json').read_text())['files']
    base_build['leaflet'] = json.loads((OUT / 'leaflet.json').read_text())['files']
    for slug, tint in [('fig-milk', 'FIG MILK'), ('ember', 'EMBER')]:
        folder = OUT / 'tints' / slug
        variant_build = json.loads((folder / 'surface-builds.json').read_text())
        variant_build['carton'] = json.loads((folder / 'carton.json').read_text())['files']
        variant_build['leaflet'] = json.loads((folder / 'leaflet.json').read_text())['files']
        area_records = {panel: _area_specs(folder, tint, panel) for panel in ('carton', 'leaflet')}
        areas = {panel: result[0] for panel, result in area_records.items()}
        surfaces = []
        changes = []
        for panel, filename in [('body', 'body-wrap.ai'), ('cap', 'cap-wrap.ai'), ('label', 'label.ai'),
                                ('carton', 'carton-artwork.ai'), ('leaflet', 'leaflet.ai')]:
            a, b = base_build[panel], variant_build[panel]
            master_frames, variant_frames = [], []
            if panel in area_records:
                _, master_frames, variant_frames = area_records[panel]
            preview_names = [frame['name'] for frame in master_frames]
            preview_names.extend(name for frame in master_frames if 'preview_row_names' in frame
                                 for name in frame['preview_row_names'])
            spec, allowances = _type_specs(a['type'], b['type'], tint, preview_names)
            if master_frames:
                # Native refresh replaces preview rows with full frame rows in
                # the type census. Check those specs above, then classify their
                # geometry once as area reflow rather than also as tint labels.
                frame_names = {f['name'] for f in master_frames}
                allowances = [box for box in allowances if box['name'] not in frame_names]
                allowances.extend({'name': f['name'], 'kind': 'area-reflow', 'copy': f['copy'], 'box_mm': f['box_mm']} for f in master_frames)
            actual = compare_saved_surfaces(OUT / filename, folder / filename, allowances, tint)
            native_master = _native_evidence(OUT, filename, master_frames)
            native_variant = _native_evidence(folder, filename, variant_frames)
            actual.update({'file': filename, 'type_spec': spec, 'native_master': native_master, 'native_derivative': native_variant,
                           'holds': actual['holds'] and spec['holds'] and native_master['holds'] and native_variant['holds']})
            # Retain clear older report names for the page; their evidence is now stronger.
            actual['embedded_painting_identical'] = actual['checks']['decoded_painting_pixels_and_placement_identical']
            actual['page_geometry_identical'] = actual['checks']['page_trim_bleed_geometry_identical']
            actual['font_families_identical'] = actual['checks']['font_families_identical']
            surfaces.append(actual)
            changes.extend({'surface': panel, 'element': row['name'], 'from': row['from'], 'to': row['to']}
                           for row in spec['rows'] if row.get('tint_change') and row['from'] != row['to'])
        for panel, (_, frame_specs, _) in area_records.items():
            changes.extend({'surface': panel, 'element': f['name'], 'from': f['copy'], 'to': _replace_tint(f['copy'], tint),
                            'permitted_consequence': 'same-size area text may reflow; full native contents and fixed character styles checked'}
                           for f in frame_specs if f['copy'] != _replace_tint(f['copy'], tint))
        all_areas_hold = all(proof['holds'] for proof in areas.values())
        row = {'schema': 'hayat_derivative_diff/3', 'tint': tint, 'path': m.rel(folder), 'cost_usd': 0,
               'surfaces': surfaces, 'area_frames': areas, 'diff': changes,
               'only_tint_copy_changes_in_build_spec': all_areas_hold and all(s['type_spec']['holds'] for s in surfaces),
               'unchanged': ['decoded painting pixels and placement', 'all actual vector paths and clipping', 'BBROSE paths and colours',
                             'die geometry', 'font sizes and colours', 'all fixed glyph positions', 'layer states', 'page trim and bleed boxes'],
               'label_change': 'Tint word only; fragment painting preserved. Tint width/centering and native regulated-area reflow are the only layout allowances.',
               'same_master_holds': controls['holds'] and all_areas_hold and all(s['holds'] for s in surfaces)}
        rows.append(row)
        m.dump(folder / 'diff.json', row)
    result = {'schema': 'hayat_tints/3', 'master': 'Rosewater', 'derivatives': rows, 'cost_usd': 0,
              'negative_controls': controls,
              'proof': 'Saved-file pixel, vector, glyph and native-area-text comparison; no claimed invariance is inferred merely from shared builder code.'}
    m.dump(OUT / 'derivatives.json', result)
    return result


def consolidate():
    base=json.loads((OUT/'surface-builds.json').read_text())
    carton=json.loads((OUT/'carton.json').read_text())['files']
    all_surfaces=dict(base,carton=carton)
    if (OUT/'leaflet.json').is_file():
        all_surfaces['leaflet']=json.loads((OUT/'leaflet.json').read_text())['files']
    m.dump(OUT/'ai-check.json',{name:row['ai_check'] for name,row in all_surfaces.items()})
    m.dump(OUT/'contrast.json',{name:row['contrast'] for name,row in all_surfaces.items()})
    m.dump(OUT/'type-checks.json',{name:row['type'] for name,row in all_surfaces.items()})
    # The completion eye must receive the original allowed-difference bytes.
    # Consolidating new surface checks does not rewrite that historical record.
    if (OUT/'allowed-differences.json').is_file():
        return all_surfaces
    differences={'rule':'D-R1B-1 / D-R1B-5','process_colour_only':True,
      'allowed':[
       'Nine source crops enlarged exactly 2× Lanczos; source pixels preserved outside the recorded allowed changes.',
       'Cap حياة clean vector trace; spurious 1 removed and measured.',
       'Small copy replaced with live DM Sans and Almarai from the GRANTED pool, approved BBROSE vector in ink.',
       'Full EN/ES/AR draft copy retained in back live area text at 5pt; visible overflow precisely listed.',
       'Black fork rectangles and construction/mask edges locally cleaned with before/after masks.',
       'D-R1B-7: owner-directed repair of two side-fragment mistakes, recovering continuous original paint from the retained D1/A raw image in those local rectangles only.',
       'D-R1B-8: owner-identified cap construction/mask remnants cleaned locally; only two guide-contaminated contour notches are bridged in the vector word, with fresh saved-SVG IoU proof and all other coordinates retained.',
       'Wraps receive 1mm top/bottom edge extension and a 2mm feathered seam; carton cut edges receive3mm bleed.',
       'Net figures2mm, ℮3mm, minimum5pt; cap-height, contrast and fit failures remain reports.'
      ],'mandatory_owner_copy_D_R1B_3':{
       'precedence':'These explicit owner requirements apply even when the pinned sketch has no such text. Required copy must not be removed as an unauthorized addition.',
       'body':'Approved BBROSE mark; HAYAT / حياة; LIP BALM / بلسم شفاه; ROSEWATER; 4.5 g ℮ 0.15 oz.',
       'cap':'The traced logotype, approved BBROSE mark, and the tint ROSEWATER are explicitly required.',
       'label':'The fragment painting and tint ROSEWATER are explicitly required on the 16mm label.',
       'carton':'Front mark, HAYAT / حياة, LIP BALM / بلسم شفاه, ROSEWATER and net; back complete live drafts, EAN frame and batch field; bottom ROSEWATER; top HAYAT / حياة.'
      },'design_findings_retained':[
       'Other repeated/interrupted and clipped fragment strokes remain the sketch, unchanged outside the two D-R1B-7 repairs.',
       'Two pointed-out side breaks repaired with existing raw-image paint under D-R1B-7; other interrupted strokes remain.',
       'Source resolution and exact2× fidelity bars have reported failures.'
      ],'not_applied':'Flagged blind cap emboss proposal only; no foil or varnish.'}
    m.dump(OUT/'allowed-differences.json',differences)
    return all_surfaces
