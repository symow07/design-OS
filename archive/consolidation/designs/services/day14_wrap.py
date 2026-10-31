"""D-D14-3: mechanically join the live lid PDF to the adopted mirror-side pixels.

No app initialisation, network, secrets, design, rasterisation or rendered preview.
Run from the repository root with the project Python and PYTHONDONTWRITEBYTECODE=1.
The original PDF streams, fonts, colour profile and finish plates are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/audit/day-14/zilal/wrap'
LID = ROOT / 'docs/audit/day-12/zilal/lid/lid-master.pdf'
MIRROR = ROOT / 'docs/audit/day-11/zilal/sides/alternative-mirror/sides-unfolded-print.png'
MIRROR_PDF = MIRROR.with_name('sides-alternative-mirror.pdf')
MIRROR_RECORD = MIRROR.with_name('alternative.json')
MEDIA_MAP = LID.with_name('media-map.json')
PART_B = ROOT / 'docs/audit/day-13/verification-independent/print_fidelity.py'
MM = 25.4 / 72
BLEED_MM = 3.0
SIDE_MM = 12.0
LID_MM = (190.0, 120.0)
TRIM_MM = (214.0, 144.0)
MEDIA_MM = (220.0, 150.0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).resolve().relative_to(ROOT))


def rect_mm(coords):
    return fitz.Rect(*(v / MM for v in coords))


def box_mm(box):
    return [round(float(v) * MM, 6) for v in box]


def source_record(path):
    return {'path': rel(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def band_images(flat, band):
    """Crop only the four adopted bands; never embed the old raster lid's words.

    Each original band is placed at its specified 12 mm depth. Integer-pixel
    round-off in Day 11's flat is resolved independently per band dimension;
    the crop pixels are not resampled. Reflect padding follows the existing
    bleed method (BORDER_REFLECT_101 / numpy reflect), not generated artwork.
    All four band edges are extended, including the short edges at cutaways.
    """
    h, w = flat.shape[:2]
    crops = {
        'top': ((band, 0, w-band, band), (15., 3., 205., 15.)),
        'bottom': ((band, h-band, w-band, h), (15., 135., 205., 147.)),
        'left': ((0, band, band, h-band), (3., 15., 15., 135.)),
        'right': ((w-band, band, w, h-band), (205., 15., 217., 135.)),
    }
    for name, (crop, target) in crops.items():
        x0, y0, x1, y1 = crop
        pixels = flat[y0:y1, x0:x1]
        tw, th = target[2]-target[0], target[3]-target[1]
        kx, ky = pixels.shape[1]/tw, pixels.shape[0]/th
        bx, by = math.ceil(BLEED_MM*kx), math.ceil(BLEED_MM*ky)
        padded = np.pad(pixels, ((by, by), (bx, bx), (0, 0)), mode='reflect')
        assert np.array_equal(padded[by:-by, bx:-bx], pixels)
        placed = (target[0]-bx/kx, target[1]-by/ky,
                  target[2]+bx/kx, target[3]+by/ky)
        buffer = io.BytesIO()
        Image.fromarray(padded).save(buffer, format='PNG')
        yield name, buffer.getvalue(), {
            'source_crop_px': list(crop), 'source_pixels': [pixels.shape[1], pixels.shape[0]],
            'crop_rgb_sha256': hashlib.sha256(pixels.tobytes()).hexdigest(),
            'placed_trim_mm': list(target), 'placed_image_mm': list(placed),
            'padding_px_xy': [bx, by], 'extension_mm_xy': [bx/kx, by/ky],
            'padded_pixels': [padded.shape[1], padded.shape[0]],
            'padded_rgb_sha256': hashlib.sha256(padded.tobytes()).hexdigest(),
            'source_crop_unchanged': True, 'padding_method': 'reflect, edge row not repeated',
            'nominal_ppi_xy': [kx*25.4, ky*25.4],
        }


def stream(doc, data):
    xref = doc.get_new_xref()
    doc.update_object(xref, '<<>>')
    doc.update_stream(xref, data)
    return xref


def translate_original_page(doc, page, clip_to_lid):
    """Add only a 12 mm translation and clip, leaving original streams intact."""
    original = page.get_contents()
    offset = SIDE_MM / MM
    prefix = 'q\n1 0 0 1 %.12f %.12f cm\n' % (offset, offset)
    if clip_to_lid:
        prefix += '%.12f %.12f %.12f %.12f re W n\n' % (
            BLEED_MM/MM, BLEED_MM/MM, LID_MM[0]/MM, LID_MM[1]/MM)
    refs = [stream(doc, prefix.encode('ascii')), *original, stream(doc, b'\nQ\n')]
    doc.xref_set_key(page.xref, 'Contents', '[%s]' % ' '.join('%d 0 R' % x for x in refs))
    page.set_mediabox(rect_mm((0, 0, *MEDIA_MM)))
    page.set_bleedbox(page.rect)
    page.set_trimbox(rect_mm((3, 3, 217, 147)))


def text_rows(page):
    return [{'text': ''.join(chr(c[0]) for c in t['chars']), 'font': t['font'],
             'size_pt': t['size'], 'bbox': list(t['bbox']), 'render_mode': t['type']}
            for t in page.get_texttrace()]


def compare_text(source, target):
    before, after = text_rows(source), text_rows(target)
    rows = []
    for a, b in zip(before, after):
        drift = np.array(b['bbox'])-np.array(a['bbox'])-SIDE_MM/MM
        rows.append({'text': a['text'], 'font': a['font'], 'size_pt': a['size_pt'],
                     'text_font_size_mode_equal': all(a[k] == b[k] for k in
                                                     ('text', 'font', 'size_pt', 'render_mode')),
                     'translation_error_mm_max': float(abs(drift).max()*MM)})
    return {'source_objects': len(before), 'output_objects': len(after), 'rows': rows,
            'all_live_copy_preserved': len(before) == len(after) and bool(rows)
            and all(r['text_font_size_mode_equal'] and r['translation_error_mm_max'] < .001 for r in rows)}


def read_back(pdf_path, bands):
    """Builder regression only. Reuses Part B's pdf_info unchanged, without main()."""
    spec = importlib.util.spec_from_file_location('day14_original_part_b_print_fidelity', PART_B)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    structural = audit.pdf_info(rel(pdf_path))
    with fitz.open(LID) as source, fitz.open(pdf_path) as output:
        pages = []
        for n, (a, b) in enumerate(zip(source, output)):
            source_streams = [hashlib.sha256(source.xref_stream(x)).hexdigest() for x in a.get_contents()]
            output_streams = [hashlib.sha256(output.xref_stream(x)).hexdigest() for x in b.get_contents()]
            before_paths, after_paths = a.get_drawings(), b.get_drawings()
            # Page 4 adds the wrap cut outline and fold rectangle after source guides.
            source_path_rows = []
            for old, new in zip(before_paths, after_paths):
                drift = np.array(list(new['rect']))-np.array(list(old['rect']))-SIDE_MM/MM
                source_path_rows.append({'source_items': len(old['items']), 'output_items': len(new['items']),
                                         'translation_error_mm_max': float(abs(drift).max()*MM),
                                         'style_equal': all(old.get(k) == new.get(k) for k in
                                                            ('type', 'fill', 'color', 'width', 'even_odd'))})
            pages.append({'page': n+1, 'source_content_stream_count': len(source_streams),
                          'source_content_streams_preserved': all(s in output_streams for s in source_streams),
                          'source_vector_paths': len(before_paths), 'output_vector_paths': len(after_paths),
                          'source_path_translation': source_path_rows})
        images = output[0].get_images(full=True)
        bands_read = []
        for name, row in bands.items():
            matches = []
            for image in images:
                if [image[2], image[3]] != row['padded_pixels']:
                    continue
                extracted = output.extract_image(image[0])
                pixels = np.array(Image.open(io.BytesIO(extracted['image'])).convert('RGB'))
                if hashlib.sha256(pixels.tobytes()).hexdigest() == row['padded_rgb_sha256']:
                    matches.append(image[0])
            bands_read.append({'band': name, 'exact_rgb_match_xrefs': matches,
                               'crop_and_reflected_bleed_preserved': bool(matches)})
        actual_text = []
        for xref in range(1, output.xref_length()):
            if output.xref_is_stream(xref):
                content = output.xref_stream(xref)
                import re
                actual_text.extend(bytes.fromhex(t.decode()).decode('utf-16-be').lstrip('\ufeff')
                                   for t in re.findall(rb'/ActualText\s*<([0-9A-Fa-f]+)>', content))
        live = compare_text(source[0], output[0])
        fonts = structural['page_details'][0]['fonts']
        checks = {
            'four_pages': len(output) == 4,
            'all_live_small_copy_preserved': live['all_live_copy_preserved'],
            'all_used_artwork_fonts_embedded': all(f['embedded_bytes'] > 0 for f in fonts),
            'live_artwork_type_at_least_5pt': all(t['size_pt'] >= 5 for t in live['rows']),
            'all_source_streams_preserved': all(p['source_content_streams_preserved'] for p in pages),
            'source_vector_paths_preserved_at_translation': all(r['source_items'] == r['output_items']
                 and r['style_equal'] and r['translation_error_mm_max'] < .001
                 for p in pages for r in p['source_path_translation']),
            'mirror_band_pixels_and_padding_preserved': all(r['crop_and_reflected_bleed_preserved'] for r in bands_read),
            'bleed_at_least_3mm_numeric_tolerance_0_001': all(min(p['bleed_margin_mm']) >= 2.999
                                                          for p in structural['page_details']),
            'foil_and_relief_vector_pages_retained': [len(output[n].get_drawings()) for n in (1, 2)] == [2, 1],
        }
    return {'kind': 'builder structural regression; not independent Part B2',
            'part_b_script': source_record(PART_B), 'part_b_function': 'pdf_info (unchanged; no rendering)',
            'pdf_info': structural, 'live_copy': live, 'actual_text': actual_text,
            'page_preservation': pages, 'band_pixels': bands_read, 'checks': checks}


def build(out_dir=OUT):
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / 'lid-and-sides.pdf'
    if target == LID or target == MIRROR_PDF:
        raise ValueError('prior-day sources are immutable')
    paths = (LID, MIRROR, MIRROR_PDF, MIRROR_RECORD, MEDIA_MAP)
    sources = [source_record(p) for p in paths]
    flat = np.array(Image.open(MIRROR).convert('RGB'))
    band = json.loads(MIRROR_RECORD.read_text())['band_px']
    if flat.shape != (1702, 2529, 3) or band != 142:
        raise ValueError('adopted mirror geometry changed; do not silently refit it')
    bands = {}
    with fitz.open(LID) as doc:
        if len(doc) != 4:
            raise ValueError('expected artwork, foil, relief and guides in live master')
        # Opening the original PDF retains its complete OCG/font/colour resources.
        source_colour_space = doc.xref_get_key(doc[0].get_images()[0][0], 'ColorSpace')[1]
        # ReportLab's initial /F1 selection is unused; do not carry its unembedded
        # Helvetica declaration into this new deliverable. Keep every source
        # stream intact and point that unused dictionary at the existing face.
        if any(t['font'].startswith('Helvetica') for p in doc for t in p.get_texttrace()):
            raise ValueError('Helvetica became visible in the source; replacement is no longer a no-op')
        replacement = next(f[0] for f in doc[0].get_fonts(full=True) if f[3].endswith('Tajawal-Medium'))
        unused = sorted({f[0] for p in doc for f in p.get_fonts(full=True)
                         if f[3] == 'Helvetica' and not doc.extract_font(f[0])[3]})
        for xref in unused:
            doc.update_object(xref, doc.xref_object(replacement))
        for page in doc:
            translate_original_page(doc, page, clip_to_lid=page.number < 3)
        mirror_ocg = doc.add_ocg('adopted mirror sides and edge-extension bleed', on=True)
        for name, png, row in band_images(flat, band):
            xref = doc[0].insert_image(rect_mm(row['placed_image_mm']), stream=png,
                                       keep_proportion=False, overlay=False, oc=mirror_ocg)
            doc.xref_set_key(xref, 'ColorSpace', source_colour_space)
            bands[name] = row
        # Construction-only page: cross-shaped trim and existing lid/fold rectangle.
        guide = doc[3]
        outline = [(15, 3), (205, 3), (205, 15), (217, 15), (217, 135), (205, 135),
                   (205, 147), (15, 147), (15, 135), (3, 135), (3, 15), (15, 15), (15, 3)]
        guide.draw_polyline([fitz.Point(x/MM, y/MM) for x, y in outline], color=(.85, 0, .55), width=.25)
        guide.draw_rect(rect_mm((15, 15, 205, 135)), color=(0, .6, .9), width=.25, dashes='[2 2]')
        doc.set_page_labels([{'startpage': i, 'prefix': label, 'style': ''} for i, label in enumerate((
            '1 wrap artwork: live lid and adopted mirror sides ', '2 wrap rose-gold foil plate ',
            '3 wrap relief plate ', '4 wrap cut outline and lid guides '))])
        metadata = dict(doc.metadata)
        metadata.update(title='Zilal live lid and mirror sides - Day 14 wrap',
                        subject='D-D14-3; source artwork and finishes preserved; 3 mm mirrored edge bleed',
                        creator='apps/pipeline/services/day14_wrap.py')
        doc.set_metadata(metadata)
        doc.save(target, garbage=3, deflate=True, no_new_id=True)
    after = [source_record(p) for p in paths]
    if sources != after:
        raise AssertionError('a source changed during the build')
    readback = read_back(target, bands)
    record = {
        'schema': 'day14_live_wrap/1', 'authority': 'D-D14-3',
        'builder': 'Codex (GPT-6); builder regression only, fresh Claude Code Part B2 follows',
        'script': source_record(Path(__file__)), 'sources': sources, 'sources_unchanged': sources == after,
        'output': source_record(target), 'spend_usd': 0, 'rendered': False,
        'unused_font_resources': {'replaced_unembedded_helvetica_dictionaries': len(unused),
                                  'replacement': 'already-embedded Tajawal-Medium dictionary',
                                  'visible_helvetica_objects_before': 0,
                                  'why': 'unused emitter default only; source streams and visible copy unchanged'},
        'geometry': {'media_mm': list(MEDIA_MM), 'trim_mm': list(TRIM_MM), 'outer_bleed_mm': BLEED_MM,
                     'lid_trim_on_page_mm': [15, 15, 205, 135], 'side_depth_mm': SIDE_MM,
                     'source_page_translation_mm': [12, 12],
                     'cutaway_corners': 'four 12 x 12 mm corners; the guide page shows the cross-shaped trim',
                     'all_cut_edges': 'each mirror band reflected at every edge, including short cutaway edges; '
                                      'at least 3 mm extension, excess clipped by the page. The lid overwrites inner padding.'},
        'bands': bands,
        'lettering': {
            'small_copy': 'all 10 live text objects from lid artwork retained verbatim, including both Arabic words',
            'brand_logo': 'approved BBROSE vector ink paths retained on artwork page',
            'listed_logotypes': 'Enchanted Rose and ظلال remain the listed raster ink fallbacks from the live master; '
                                 'their original vector foil paths remain on page 2, and ظلال vector relief on page 3',
            'limitation': 'The listed name and hero ink fallbacks on page 1 are not asserted to be vectors. '
                          'No vector repainting or redesign was performed; existing media-map exceptions are preserved.',
            'estimated_sign': 'existing vector estimated sign retained'},
        'page_roles': ['artwork', 'rose-gold foil', 'relief', 'construction guides'],
        'readback': readback,
    }
    (out_dir / 'wrap-build.json').write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    if not all(readback['checks'].values()):
        raise AssertionError(readback['checks'])
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    result = build(args.out)
    print(json.dumps({'output': result['output'], 'checks': result['readback']['checks']}, indent=2))
