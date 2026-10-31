"""Day 6 per-surface fidelity instrument (owner §2.2) — positive and negative controls.

Pure unittest, no database. A tiny reportlab PDF with a live text line, two vector marks,
a flat field and a cream band at known millimetre positions must pass; the same PDF with
the text shifted 1.5 mm, the text recoloured, the band moved 1.5 mm or the band missing
must fail the matching category and no other. The Day 4 flats must fail the instrument
against D1, and the instrument must refuse to overwrite existing evidence.
"""
import json
import tempfile
import unittest
from pathlib import Path

import fitz
from fontTools.ttLib import TTFont as FTFont
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from apps.pipeline.services import day6_surface_fidelity as F
from apps.pipeline.services.fidelity_master import FONTS

FONT = FONTS['title']
WIDTH_MM, HEIGHT_MM = 60, 40
TEXT_X_MM, BASELINE_MM, SIZE_PT = 10.0, 25.0, 24
FIELD = (120, 60, 10)
TEXT = (245, 223, 195)
LOGO_BOX = [5.0, 5.0, 20.0, 10.0]
RULE_BOX = [10.0, 30.0, 30.0, 30.5]
BAND_X0, BAND_X1 = 40.0, 46.0


def expected_ink_box(x_mm, baseline_mm, size_pt):
    """Independent truth: the glyph outline bounds of the pinned face, scaled to size."""
    font = FTFont(FONT)
    cmap, glyf, hmtx = font.getBestCmap(), font['glyf'], font['hmtx']
    k = size_pt / font['head'].unitsPerEm * 25.4 / 72
    cursor, xs, ys = 0, [], []
    for ch in 'SUN':
        name = cmap[ord(ch)]
        glyph = glyf[name]
        xs += [cursor + glyph.xMin, cursor + glyph.xMax]
        ys += [glyph.yMin, glyph.yMax]
        cursor += hmtx[name][0]
    return [x_mm + min(xs) * k, baseline_mm - max(ys) * k, x_mm + max(xs) * k, baseline_mm - min(ys) * k]


def emit(folder, *, text_dx_mm=0.0, text_srgb=TEXT, band_dx_mm=0.0, band=True, png=True):
    folder = Path(folder)
    pdf = folder / 'artwork.pdf'
    c = Canvas(str(pdf), pagesize=(WIDTH_MM * mm, HEIGHT_MM * mm))
    c.setFillColorRGB(*[v / 255 for v in FIELD])
    c.rect(0, 0, WIDTH_MM * mm, HEIGHT_MM * mm, fill=1, stroke=0)
    if band:
        c.setFillColorRGB(*[v / 255 for v in F.CREAM_SRGB])
        path = c.beginPath()
        x0, x1 = (BAND_X0 + band_dx_mm) * mm, (BAND_X1 + band_dx_mm) * mm
        path.moveTo(x0, 0)
        path.lineTo(x1, 0)
        path.lineTo(x1, HEIGHT_MM * mm)
        path.lineTo(x0, HEIGHT_MM * mm)
        path.close()
        c.drawPath(path, fill=1, stroke=0, fillMode=0)
    c.setFillColorRGB(246 / 255, 228 / 255, 204 / 255)
    c.rect(LOGO_BOX[0] * mm, (HEIGHT_MM - LOGO_BOX[3]) * mm, (LOGO_BOX[2] - LOGO_BOX[0]) * mm, (LOGO_BOX[3] - LOGO_BOX[1]) * mm, fill=1, stroke=0)
    c.setFillColorRGB(244 / 255, 221 / 255, 185 / 255)
    c.rect(RULE_BOX[0] * mm, (HEIGHT_MM - RULE_BOX[3]) * mm, (RULE_BOX[2] - RULE_BOX[0]) * mm, (RULE_BOX[3] - RULE_BOX[1]) * mm, fill=1, stroke=0)
    pdfmetrics.registerFont(TTFont('Day6SyntheticTitle', str(FONT)))
    c.setFont('Day6SyntheticTitle', SIZE_PT)
    c.setFillColorRGB(*[v / 255 for v in text_srgb])
    c.drawString((TEXT_X_MM + text_dx_mm) * mm, (HEIGHT_MM - BASELINE_MM) * mm, 'SUN')
    c.save()
    if png:
        with fitz.open(pdf) as doc:
            doc[0].get_pixmap(dpi=F.RENDER_PPI, alpha=False).save(folder / 'artwork.png')
    return pdf


def face():
    return {'surface_id': 'synthetic.front', 'size_mm': [WIDTH_MM, HEIGHT_MM], 'status': 'measured (synthetic control)',
            'source_box_px': [0, 0, WIDTH_MM, HEIGHT_MM],
            'field_samples': [{'xy_px': [30, 20], 'window_px': 11, 'srgb': list(FIELD)},
                              {'xy_px': [55, 35], 'window_px': 11, 'srgb': list(FIELD)},
                              {'xy_px': [3, 38], 'window_px': 11, 'srgb': list(FIELD)}],
            'elements': [{'id': 'SUN', 'copy': 'SUN', 'bbox_mm': expected_ink_box(TEXT_X_MM, BASELINE_MM, SIZE_PT),
                          'baseline_y_mm': BASELINE_MM, 'colour_srgb': list(TEXT)},
                         {'id': 'logo', 'copy': None, 'bbox_mm': LOGO_BOX, 'baseline_y_mm': None, 'colour_srgb': [246, 228, 204]},
                         {'id': 'name_rule', 'copy': None, 'bbox_mm': RULE_BOX, 'baseline_y_mm': None, 'colour_srgb': [244, 221, 185]}],
            'gesture_centreline_mm': [[(BAND_X0 + BAND_X1) / 2, 8.0], [(BAND_X0 + BAND_X1) / 2, 20.0], [(BAND_X0 + BAND_X1) / 2, 32.0]],
            'deviations': []}


def inspect(**kwargs):
    with tempfile.TemporaryDirectory() as folder:
        emit(folder, **kwargs)
        return F.inspect_surface(folder, face(), addendum=None, graph_name=None,
                                 png_name='artwork.png' if kwargs.get('png', True) else None)


class ThresholdTests(unittest.TestCase):
    def test_thresholds_are_the_owners_numbers(self):
        self.assertEqual(F.PLACEMENT_OFFSET_MM, 1.0)
        self.assertEqual(F.PLACEMENT_SIZE_PERCENT, 3.0)
        self.assertEqual(F.INK_DELTA_E, 4.0)
        self.assertEqual(F.FIELD_DELTA_E, 6.0)
        self.assertEqual(F.GESTURE_CENTRELINE_MM, 1.0)
        self.assertIn('placement ≤ 1.0 mm / 3 %', F.THRESHOLDS['wording'])
        self.assertIn('ΔE2000 ≤ 4 (ink) / ≤ 6 (field)', F.THRESHOLDS['wording'])


class SyntheticControlTests(unittest.TestCase):
    def test_positive_control_passes_every_category(self):
        result = inspect()
        rows = {r['id']: r for r in result['placement']['rows']}
        truth = expected_ink_box(TEXT_X_MM, BASELINE_MM, SIZE_PT)
        for edge, expected in zip(rows['SUN']['emitted_bbox_mm'], truth):
            self.assertLess(abs(edge - expected), .15, (rows['SUN']['emitted_bbox_mm'], truth))
        for identifier in ('SUN', 'logo', 'name_rule'):
            self.assertTrue(rows[identifier]['present'], identifier)
            self.assertLess(abs(rows[identifier]['centre_dx_mm']), .15, identifier)
            self.assertLess(abs(rows[identifier]['centre_dy_mm']), .15, identifier)
            self.assertTrue(rows[identifier]['passed'], rows[identifier])
        self.assertLess(abs(rows['SUN']['baseline_dy_mm']), .05)
        self.assertEqual(rows['SUN']['glyphs'], 'SUN')
        self.assertTrue(result['placement']['passed'])
        self.assertTrue(result['ink_colour']['passed'])
        self.assertLess(result['ink_colour']['max_delta_e_2000'], 1.0)
        self.assertTrue(result['field']['passed'])
        self.assertLess(result['field']['max_delta_e_2000'], 1.0)
        self.assertTrue(result['gesture']['passed'])
        self.assertLess(result['gesture']['max_abs_dx_mm'], .1)
        self.assertTrue(result['grammar']['passed'])
        self.assertTrue(result['png']['pixels_match_fresh_render'])
        self.assertTrue(result['measured_fidelity_passed'])
        self.assertEqual(result['placement']['line_assignment'], 'measured element centres (no design graph shipped)')

    def test_text_shifted_1_5_mm_fails_placement_only(self):
        result = inspect(text_dx_mm=1.5, png=False)
        row = next(r for r in result['placement']['rows'] if r['id'] == 'SUN')
        self.assertTrue(1.3 < row['centre_dx_mm'] < 1.7, row['centre_dx_mm'])
        self.assertFalse(row['passed'])
        self.assertFalse(result['placement']['passed'])
        self.assertFalse(result['measured_fidelity_passed'])
        self.assertTrue(result['gesture']['passed'])
        self.assertTrue(result['field']['passed'])

    def test_recoloured_text_fails_ink_colour_only(self):
        result = inspect(text_srgb=(255, 255, 255), png=False)
        row = next(r for r in result['ink_colour']['rows'] if r['id'] == 'SUN')
        self.assertGreater(row['delta_e_2000'], F.INK_DELTA_E)
        self.assertFalse(row['passed'])
        self.assertFalse(result['ink_colour']['passed'])
        self.assertFalse(result['measured_fidelity_passed'])
        self.assertTrue(result['placement']['passed'])
        self.assertTrue(result['gesture']['passed'])

    def test_cream_band_offset_1_5_mm_fails_gesture(self):
        result = inspect(band_dx_mm=1.5, png=False)
        gesture = result['gesture']
        self.assertEqual(gesture['missing'], 0)
        self.assertTrue(1.3 < gesture['max_abs_dx_mm'] < 1.7, gesture['max_abs_dx_mm'])
        self.assertFalse(gesture['passed'])
        self.assertFalse(result['measured_fidelity_passed'])
        self.assertTrue(result['placement']['passed'])

    def test_missing_cream_fails_gesture_and_says_so(self):
        result = inspect(band=False, png=False)
        gesture = result['gesture']
        self.assertEqual(gesture['missing'], 3)
        self.assertFalse(gesture['passed'])
        self.assertTrue(all(r['reason'] == 'no cream device fill on this horizontal' for r in gesture['rows']))
        self.assertFalse(result['grammar']['device_present'])
        self.assertFalse(result['measured_fidelity_passed'])


class NegativeControlTests(unittest.TestCase):
    def test_day4_flats_fail_against_d1(self):
        with tempfile.TemporaryDirectory() as folder:
            report = F.negative_control(folder)
            written = json.loads((Path(folder) / 'negative-control-day4.json').read_text())
        self.assertTrue(report['instrument_distinguishes'])
        self.assertTrue(report['header_fails_placement_or_colour'])
        self.assertEqual(len(report['rows']), 7)
        for row in report['rows']:
            self.assertTrue(row['failing_categories'], row['surface_id'])
            self.assertFalse(row['all_categories_passed'], row['surface_id'])
        header = next(r for r in report['rows'] if r['surface_id'] == 'header.front')
        self.assertTrue({'placement', 'ink_colour'} & set(header['failing_categories']))
        self.assertEqual(written['rows'][0]['surface_id'], 'header.front')
        self.assertEqual(written['surfaces']['header.front']['gesture']['missing'], 10)

    def test_existing_evidence_is_never_overwritten(self):
        if not (F.SURFACES / 'fidelity-summary.json').exists():
            self.skipTest('Day 6 fidelity evidence not present in this checkout')
        with self.assertRaises(FileExistsError):
            F.run(F.SURFACES)
        with self.assertRaises(FileExistsError):
            F.negative_control(F.SURFACES)


if __name__ == '__main__':
    unittest.main()
