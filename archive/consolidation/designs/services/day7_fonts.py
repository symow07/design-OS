"""Day 7 §4: the measured Arabic line re-run against the enlarged pool, reported beside the applied Cairo and NOT applied;
and a specimen page of the GRANTED pool (top twelve Latin display, top twelve Arabic) by a stated rule. Records under
docs/audit/day-7/fonts/. Nothing under materials/ is written.
"""
from pathlib import Path
import datetime, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import fidelity_assets as fa
from . import cairo_measured as cm

ROOT = fa.ROOT
OUT = ROOT / 'docs/audit/day-7/fonts'
CAIRO_APPLIED = ROOT / 'docs/audit/day-5/master/assets/Cairo-D5-Measured.ttf'
NASKH = fa.APP / 'static/fonts/NotoNaskhArabic-Regular.ttf'
TARGET_WIDTH_PX = 155.0; TOLERANCE_PERCENT = 3.0; RASTER_FACTOR = 4; LINE_PX = 25
LATIN_LINE = 'BBROSE Sun Repair Serum'; ARABIC_LINE = cm.COPY
DISPLAY_LEANING = ('didone', 'roman-capitals', 'script', 'slab', 'condensed', 'condensed-serif')


def pool_entries():
    from apps.ire import font_pool
    return [e for e in font_pool.catalogue_entries() if not e.get('already_in_brand_catalogue')]


def raster_width_at_25px(path, text, direction, language):
    """Ink width of the line at 25 px height, measured on a 4× raster (100 px) with the shaping engine (raqm): the ink
    box's width divided by its height, scaled to the 25 px convention — the Day 5 comparison's own convention."""
    font = ImageFont.truetype(str(path), LINE_PX * RASTER_FACTOR)
    im = Image.new('L', (LINE_PX * RASTER_FACTOR * 24, LINE_PX * RASTER_FACTOR * 3), 0); d = ImageDraw.Draw(im)
    d.text((LINE_PX * RASTER_FACTOR, LINE_PX * RASTER_FACTOR), text, font=font, fill=255, direction=direction, language=language)
    ink = np.asarray(im) > 64
    if not ink.any():
        raise ValueError('no ink')
    ys, xs = np.nonzero(ink); w = xs.max() - xs.min() + 1; h = ys.max() - ys.min() + 1
    return {'ink_px_4x': [int(w), int(h)], 'width_at_25px': round(w / h * LINE_PX, 3)}


def shape_any(path, weight=None):
    """cairo_measured.shape for a face whose glyphs carry no names: hb-shape is asked for glyph ids and each id is read
    through the font's glyph order; otherwise the Day 5 function unchanged."""
    try:
        return cm.shape(path, weight)
    except KeyError:                      # glyphs without names: shaped again by glyph id, below
        return _shape_by_ids(path, weight)


def _shape_by_ids(path, weight=None):
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    args = ['/opt/homebrew/bin/hb-shape', str(path), ARABIC_LINE, '--direction=rtl', '--language=ar', '--script=arab', '--output-format=json', '--no-glyph-names']
    if weight is not None:
        args.append('--variations=wght=%s,slnt=0' % weight)
    rows = json.loads(subprocess.check_output(args, text=True))
    with TTFont(path) as ft:
        order = ft.getGlyphOrder(); gs = ft.getGlyphSet(location={'wght': weight, 'slnt': 0} if weight is not None else None)
        cursor = 0; boxes = []
        for row in rows:
            name = order[int(row['g'])]; pen = BoundsPen(gs); gs[name].draw(pen); row['cursor'] = cursor; row['bounds'] = pen.bounds
            if pen.bounds:
                a, b, c, d = pen.bounds; boxes.append([a + cursor + row['dx'], b + row['dy'], c + cursor + row['dx'], d + row['dy']])
            cursor += row['ax']
        bounds = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
        width = (bounds[2] - bounds[0]) / (bounds[3] - bounds[1]) * LINE_PX
        return {'rows': rows, 'bounds': bounds, 'width_at_25px': width, 'height_px': LINE_PX, 'delta_width_percent': 100 * abs(width / TARGET_WIDTH_PX - 1), 'glyph_names': 'ids'}


def measure(path, label, weight=None):
    row = {'label': label, 'path': str(Path(path).relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path), 'weight': weight}
    try:
        shaped = shape_any(path, weight)
        row.update({'shaped_width_at_25px': round(shaped['width_at_25px'], 3), 'shaped_delta_percent': round(shaped['delta_width_percent'], 3),
                    'glyphs': len(shaped['rows']), 'fits': shaped['delta_width_percent'] <= TOLERANCE_PERCENT})
    except Exception as exc:    # noqa: BLE001 — a face the shaper cannot run is reported with its error, never dropped
        row.update({'shaping_error': type(exc).__name__ + ': ' + str(exc)[:120], 'fits': False})
    try:
        r = raster_width_at_25px(path, ARABIC_LINE, 'rtl', 'ar'); row.update(r)
        row['raster_delta_percent'] = round(100 * abs(r['width_at_25px'] / TARGET_WIDTH_PX - 1), 3)
    except Exception as exc:    # noqa: BLE001 — reported, never dropped
        row['raster_error'] = type(exc).__name__ + ': ' + str(exc)[:120]
    return row


def arabic_comparison():
    """Every GRANTED pool file with complete basic Arabic, shaped (hb-shape) and rasterised at 4× on the measured line,
    beside the applied Cairo 340.17 and Noto Naskh. Sorted by the shaped width's distance from the Day 5 target. Nothing
    is applied: the record says so and the bottle keeps Cairo."""
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [dict(measure(CAIRO_APPLIED, 'Cairo D5 340.17 (applied, Day 5)'), applied=True, origin='brand'),
            dict(measure(NASKH, 'Noto Naskh Arabic Regular'), applied=False, origin='STATIC_FONTS')]
    for e in pool_entries():
        if not e.get('complete_basic_arabic'):
            continue
        if e['path'].lower().endswith(('.ttc', '.otc')):
            rows.append({'label': e['catalogue_stem'], 'path': e['path'], 'skipped': 'collection: not shaped by this run', 'origin': e['origin']}); continue
        row = measure(ROOT / e['path'], e['catalogue_stem'], None)
        row.update({'origin': e['origin'], 'family': e.get('census_family'), 'licence': e.get('licence'), 'emitter_capable': bool(e.get('arabic')),
                    'forms_missing': e.get('arabic_forms_missing'), 'marks_missing': e.get('arabic_marks_missing'), 'variable': e.get('variable'), 'applied': False})
        rows.append(row)
    pool = [r for r in rows if r.get('origin') != 'brand' and 'shaped_delta_percent' in r]
    pool.sort(key=lambda r: r['shaped_delta_percent'])
    record = {'schema': 'day7_arabic_line_comparison/1', 'line': ARABIC_LINE, 'convention': 'ink width at 25 px height; target %.0f px, tolerance ±%.0f %% (Day 5)' % (TARGET_WIDTH_PX, TOLERANCE_PERCENT),
              'raster': '%d× (%d px) through raqm; ink box width/height × 25' % (RASTER_FACTOR, LINE_PX * RASTER_FACTOR), 'applied': False,
              'ruling': 'reported beside Cairo, not applied (the owner\'s Day 7 §4); the bottle keeps Cairo D5 340.17',
              'candidates': len(pool), 'fit_within_tolerance': sum(1 for r in pool if r.get('fits')), 'emitter_capable_fits': sum(1 for r in pool if r.get('fits') and r.get('emitter_capable')),
              'cairo_applied': rows[0], 'naskh': rows[1], 'pool': pool, 'skipped': [r for r in rows if r.get('skipped') or ('shaped_delta_percent' not in r and r.get('origin') != 'brand')],
              'measured_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (OUT / 'arabic-line-comparison.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    sheet(record); return {k: v for k, v in record.items() if k not in ('pool', 'skipped', 'cairo_applied', 'naskh')}


def sheet(record):
    """The 4× sheet: the applied Cairo first, then the twelve nearest pool faces, each with its measured width and verdict."""
    rows = [record['cairo_applied'], record['naskh']] + record['pool'][:12]
    W, H = 2200, 60 + 150 * len(rows); im = Image.new('RGB', (W, H), (250, 247, 243)); d = ImageDraw.Draw(im)
    small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 26)
    d.text((30, 14), 'Day 7 §4 — the measured Arabic line at 4× against the enlarged pool · target %.0f px at 25 px height · NOT applied' % TARGET_WIDTH_PX, font=small, fill=(60, 50, 40))
    y = 60
    for r in rows:
        path = ROOT / r['path'] if not Path(r['path']).is_absolute() else Path(r['path'])
        try:
            font = ImageFont.truetype(str(path), 100); d.text((30, y + 10), ARABIC_LINE, font=font, fill=(25, 20, 15), direction='rtl', language='ar')
        except Exception as exc:    # noqa: BLE001 — the row says the line was not drawn
            d.text((30, y + 50), 'not drawn: ' + str(exc)[:60], font=small, fill=(160, 40, 40))
        words = '%s · shaped %s px (Δ %s %%) · raster %s px · %s%s' % (r['label'][:40], r.get('shaped_width_at_25px', '—'), r.get('shaped_delta_percent', '—'),
                                                                        r.get('width_at_25px', '—'), 'fits' if r.get('fits') else 'outside tolerance',
                                                                        ' · APPLIED' if r.get('applied') else (' · emitter-capable' if r.get('emitter_capable') else ' · lacks presentation forms the emitter emits'))
        d.text((1150, y + 50), words, font=small, fill=(60, 50, 40)); y += 150
    im.save(OUT / 'arabic-line-comparison-4x.png', dpi=(300, 300))


def specimen():
    """Top twelve Latin display and top twelve Arabic faces of the pool, by a stated rule, drawn with the shaping engine.
    Rule — Latin: display-leaning class first (didone, roman capitals, script, slab, condensed), then heavier weight class,
    then family name; Arabic: complete basic letters, emitter-capable first, then nearest to the Day 5 width, then family."""
    OUT.mkdir(parents=True, exist_ok=True); entries = pool_entries()
    latin = sorted((e for e in entries if e.get('latin') and not e['path'].lower().endswith(('.ttc', '.otc'))),
                   key=lambda e: (0 if e.get('family_class') in DISPLAY_LEANING else 1, -(e.get('weight_class') or 400), str(e.get('census_family'))))[:12]
    comparison = json.loads((OUT / 'arabic-line-comparison.json').read_text()) if (OUT / 'arabic-line-comparison.json').exists() else {'pool': []}
    delta = {r['label']: r.get('shaped_delta_percent', 999) for r in comparison['pool']}
    arabic = sorted((e for e in entries if e.get('complete_basic_arabic') and not e['path'].lower().endswith(('.ttc', '.otc'))),
                    key=lambda e: (0 if e.get('arabic') else 1, delta.get(e['catalogue_stem'], 999), str(e.get('census_family'))))[:12]
    pages = []
    for title, rows, text, direction, language in (('Top twelve Latin display faces of the GRANTED pool', latin, LATIN_LINE, 'ltr', 'en'),
                                                    ('Top twelve Arabic faces of the GRANTED pool', arabic, ARABIC_LINE, 'rtl', 'ar')):
        W, H = 2480, 3508; im = Image.new('RGB', (W, H), (252, 250, 247)); d = ImageDraw.Draw(im)
        small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 30); tiny = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 24)
        d.text((100, 80), 'Day 7 §4 — ' + title + ' · D-D7-1 · licence wording embedded in each face', font=small, fill=(60, 50, 40)); y = 170
        for e in rows:
            try:
                font = ImageFont.truetype(str(ROOT / e['path']), 110); d.text((100, y), text, font=font, fill=(25, 20, 15), direction=direction, language=language)
            except Exception as exc:    # noqa: BLE001 — the row says the line was not drawn
                d.text((100, y + 40), 'not drawn: ' + str(exc)[:70], font=small, fill=(160, 40, 40))
            d.text((100, y + 190), '%s · %s · weight %s · %s%s · %s' % (e.get('census_family'), e['catalogue_stem'][:48], e.get('weight_class'), e.get('family_class') or 'unclassified',
                                                                       ', variable' if e.get('variable') else '', e.get('licence')), font=tiny, fill=(90, 80, 70)); y += 270
        pages.append(im)
    for n, page in enumerate(pages, 1):
        page.save(OUT / ('specimen-page-%d.png' % n), dpi=(300, 300))
    import fitz
    doc = fitz.open()
    for n in (1, 2):
        pg = doc.new_page(width=595.3, height=841.9); pg.insert_image(pg.rect, filename=str(OUT / ('specimen-page-%d.png' % n)))
    doc.save(str(OUT / 'specimen.pdf'), deflate=True, garbage=3); doc.close()
    record = {'schema': 'day7_specimen/1', 'rule': specimen.__doc__.split('Rule — ')[1].strip(), 'latin': [{'stem': e['catalogue_stem'], 'family': e.get('census_family'), 'class': e.get('family_class'),
                                                                                                         'weight_class': e.get('weight_class'), 'licence': e.get('licence'), 'sha256': e['sha256']} for e in latin],
              'arabic': [{'stem': e['catalogue_stem'], 'family': e.get('census_family'), 'emitter_capable': bool(e.get('arabic')), 'shaped_delta_percent': delta.get(e['catalogue_stem']),
                          'licence': e.get('licence'), 'sha256': e['sha256']} for e in arabic], 'pages': ['specimen-page-1.png', 'specimen-page-2.png', 'specimen.pdf']}
    (OUT / 'specimen.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n'); return {'latin': len(latin), 'arabic': len(arabic)}


if __name__ == '__main__':
    print(json.dumps(arabic_comparison(), ensure_ascii=False)); print(json.dumps(specimen(), ensure_ascii=False))
