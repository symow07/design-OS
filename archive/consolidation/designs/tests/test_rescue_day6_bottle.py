"""Day 6 bottle revision 4: the vector device replaces the raster planes. No DB, no Illustrator."""
import json
import fitz
import numpy as np
import pytest
from PIL import Image
from reportlab.lib.units import mm
from apps.pipeline.services import day6_bottle as db, day5_master as dm, day6_instrument as di
from apps.pipeline.services import fidelity_assets as fa, fidelity_master as fm

FOLDER = db.OUT


def test_spec_revision_and_parent_chain():
    spec = db.make_spec(); parent = dm.make_spec()
    assert spec['schema_version'] == 'design_spec/4.0' and spec['revision'] == 4
    assert spec['parent_hash'] == fm.digest(parent)
    assert spec['parent_hash'] == json.loads((db.REVISION3 / 'fidelity-check.json').read_text())['spec_hash']
    assert 'raster_assets' not in spec['graph']
    assert [r['role'] for r in spec['graph']['device_roles']] == ['SHADOW', 'CREAM']
    assert spec['graph']['layer_roles'] == ['SHADOW', 'CREAM', 'LIVE TYPE', 'LOGO', 'RULES']
    assert spec['named_deviation'] == 'vector edge replaces airbrush softness' and spec['production_ready'] is False
    assert spec['assets']['device']['sha256'] == fa.sha(db.DEVICE)
    # Everything else is revision 3: lines, elements, fonts, projection assets.
    for key in ('lines', 'elements'):
        assert spec['graph'][key] == parent['graph'][key]
    assert spec['fonts'] == parent['fonts'] and spec['projection_assets'] == parent['projection_assets']
    published = json.loads((FOLDER / 'design-spec.json').read_text())
    assert db.validate_spec(published) == spec
    assert json.loads((FOLDER / 'fidelity-check.json').read_text())['spec_hash'] == fm.digest(spec)


def test_altered_device_vertex_is_refused():
    spec = db.make_spec(); spec['graph']['device_roles'][1]['paths'][0]['points_mm'][0][0] += .5
    with pytest.raises(ValueError):
        db.validate_spec(spec)


def test_device_point_round_trips_to_pdf_coordinates(tmp_path):
    graph = db.make_spec()['graph']; role = next(r for r in graph['device_roles'] if r['role'] == 'CREAM')
    largest = max(role['paths'], key=lambda p: len(p['points_mm']))
    known = [role['paths'][0]['points_mm'][0], largest['points_mm'][0], largest['points_mm'][len(largest['points_mm']) // 2]]
    db.emit_pdf(graph, tmp_path / 'cream.pdf', fonts_map=db.fonts(), roles=('CREAM',), live_type=False, rules=False, logo=False)
    with fitz.open(tmp_path / 'cream.pdf') as doc:
        page = doc[0]; drawings = page.get_drawings(); stream = page.read_contents()
        assert len(page.get_images()) == 0 and len(drawings) >= 1
        assert abs(page.rect.width - fa.WIDTH * mm) < .01 and abs(page.rect.height - fa.HEIGHT * mm) < .01
        points = []
        for d in drawings:
            for item in d['items']:
                if item[0] == 'l':
                    points.extend([item[1], item[2]])
                elif item[0] == 're':  # MuPDF reports a one-pixel speck of the mask as a rectangle
                    points.extend([item[1].top_left, item[1].top_right, item[1].bottom_left, item[1].bottom_right])
                elif item[0] == 'qu':
                    points.extend([item[1].ul, item[1].ur, item[1].ll, item[1].lr])
                elif item[0] == 'c':
                    points.extend([item[1], item[4]])
        fills = {tuple(round(v, 3) for v in d['fill']) for d in drawings if d['fill']}
    # The device is top-left millimetres; the stream receives (x*mm, (HEIGHT-y)*mm) in the bottom-left PDF frame,
    # which MuPDF reports back in its top-left page frame as exactly (x*mm, y*mm) points.
    for x, y in known:
        expected = fitz.Point(x * mm, y * mm)
        assert min(abs(q - expected) for q in points) < .01
    import re
    moves = [(float(a), float(b)) for a, b in re.findall(rb'([-\d.]+) ([-\d.]+) m\b', stream)]
    x, y = largest['points_mm'][0]
    assert min(abs(a - x * mm) + abs(b - (fa.HEIGHT - y) * mm) for a, b in moves) < .001
    assert fills == {tuple(round(v / 255, 3) for v in (245, 219, 183))}


def test_coverage_planes_sum_to_at_most_one_and_carry_the_endmembers():
    f = np.array(Image.open(FOLDER / 'swoosh-cream.png')); s = np.array(Image.open(FOLDER / 'swoosh-shadow.png'))
    assert f.shape == s.shape == (2855, 1794, 4)
    assert int((f[:, :, 3].astype(int) + s[:, :, 3].astype(int)).max()) <= 255
    assert np.array_equal(np.unique(f[f[:, :, 3] > 0][:, :3], axis=0), [[245, 219, 183]])
    assert np.array_equal(np.unique(s[s[:, :, 3] > 0][:, :3], axis=0), [[130, 70, 17]])
    record = json.loads((FOLDER / 'fidelity-check.json').read_text())['coverage_planes']
    assert record['max_alpha_sum_8bit'] <= 255 and record['ppi'] == 1000


def test_negative_fails_and_emitted_planes_are_scored_by_the_same_code():
    pixels = np.array(Image.open(fa.CONCEPT).convert('RGB')); ground = np.array(Image.open(dm.INK / 'material-field.png').convert('RGB'))
    envelope = np.array(Image.open(dm.INK / 'stroke-support.png')) > 0
    cream = np.array(json.loads(db.INSTRUMENT6.read_text())['endmembers']['cream']['srgb'])
    day4 = np.array(Image.open(fa.ROOT / 'docs/audit/day-4/measurement-assets/swoosh-flat.png'))
    negative = di.corrected_proof(pixels, ground, day4, np.zeros_like(day4), envelope, cream)[0]
    assert not (negative['recomposition_passed'] and negative['fringe_passed'])
    f = np.array(Image.open(FOLDER / 'swoosh-cream.png')); s = np.array(Image.open(FOLDER / 'swoosh-shadow.png'))
    vector = di.corrected_proof(pixels, ground, f, s, envelope, cream)[0]
    recorded = json.loads((FOLDER / 'instrument.json').read_text())
    assert recorded['bar'] == {'recomposition_fraction_deltaE_le2': .99, 'fringe_flagged_pixels': 0, 'unchanged': True}
    assert recorded['negative_controls_fail'] is True
    assert recorded['rows']['day4']['recomposition_fraction_deltaE_le2'] == pytest.approx(negative['recomposition_fraction_deltaE_le2'], abs=1e-9)
    assert recorded['rows']['revision4_vector']['recomposition_fraction_deltaE_le2'] == pytest.approx(vector['recomposition_fraction_deltaE_le2'], abs=1e-9)
    assert recorded['rows']['revision4_vector']['recomposition_passed'] is vector['recomposition_passed']
    assert recorded['revision4_passed'] is bool(vector['recomposition_passed'] and vector['fringe_passed'])


def test_package_is_vector_only_with_live_type_and_prepared_critic_inputs():
    with fitz.open(FOLDER / 'artwork.pdf') as doc:
        page = doc[0]; contents = page.read_contents()
        assert len(doc) == 1 and len(page.get_images()) == 0
        assert b'/LayerRole (SHADOW)' in contents and b'/LayerRole (CREAM)' in contents
        assert {chr(ch[0]) for span in page.get_texttrace() for ch in span['chars']} >= set('SUNREPAIR')
    traced = json.loads((FOLDER / 'traced-text.json').read_text())
    assert traced['formats']['pdf']['live']['passed'] and traced['formats']['svg']['live']['passed']
    assert traced['formats']['native']['state'] == 'pending integrator' and traced['passed'] is False   # the readiness record before the native run
    if (FOLDER / 'TRACED_TEXT.json').exists():
        audited = json.loads((FOLDER / 'TRACED_TEXT.json').read_text())
        assert audited['passed'] and all(audited['formats'][k]['passed'] for k in ('pdf', 'svg', 'native'))
    brief = json.loads((FOLDER / 'critic-brief.json').read_text())
    assert brief['call_state'].startswith('prepared') and 'concept 147' in brief['instruction'] and brief['cost_usd_so_far'] == 0
    assert (FOLDER / 'critic-input-projected.png').exists() and (FOLDER / 'critic-input-grey.png').exists()
    assert (FOLDER / 'artwork-native.jsx').exists()
    if (FOLDER / 'artwork-native.ai').exists():          # built by the integrator's Illustrator run after this record was prepared
        validation = json.loads((FOLDER / 'artwork-native-validation.json').read_text())
        assert validation['passed'] and validation['device_paths_match'] and validation['raster_images'] == 0


def test_sheet_has_three_a4_pages_with_the_bar_and_the_approval_panel():
    with fitz.open(FOLDER / 'comparison-at-100-percent.pdf') as doc:
        assert len(doc) == 3
        texts = [page.get_text() for page in doc]
        assert all('50 mm' in t and 'disable Fit' in t for t in texts)
        assert all(abs(page.rect.width - 210 * mm) < .01 and abs(page.rect.height - 297 * mm) < .01 for page in doc)
    assert 'DEVICE BESIDE ORIGINAL' in texts[1] and 'vector edge replaces airbrush softness' in texts[1] and 'limit 0.3 mm' in texts[1]
    assert 'used unless objected' in texts[1]
    assert 'bar 99%' in texts[2] and 'Day 4 flat matte' in texts[2] and '4x raster export' in texts[2]
    for i in (1, 2, 3):
        assert (FOLDER / f'comparison-at-100-percent-page-{i}.png').exists()
