"""Measured failures are successful guard behavior, never creative acceptance."""
import copy,json
from pathlib import Path
import numpy as np
import pytest
from apps.pipeline.services import fidelity_master as fm
from apps.pipeline.services.identity_assembly import model_at,solve,legacy_negative
from apps.ire.identity_sightlines import evaluate,visibility,solid_relation,box,cylinder

ROOT=fm.fa.ROOT/'docs/audit/day-4'

@pytest.fixture(autouse=True)
def day4_environment(settings):
    settings.BRAND_MARK_APPROVAL_LOOKUP=True
    settings.HYBRID_BOTTLE_ENABLED=True


def test_published_revision_keeps_exact_parent_assets_and_empty_back():
    spec=json.loads((ROOT/'master/design-spec.json').read_text())
    assert fm.validate_spec(spec)
    assert spec['parent_hash']==fm.PARENT and spec['back']['copy']==[]
    for key in ('swoosh','logo'):
        a=spec['assets'][key];assert fm.fa.sha(ROOT/'master'/a['path'])==a['sha256']
    for path in ('concept-reference.png','projected-master.png'):
        assert (ROOT/'master'/path).is_file()
    bad=copy.deepcopy(spec);bad['graph']['lines'][0]['logical_text']='Replacement'
    with pytest.raises(ValueError):fm.validate_spec(bad)


def test_native_real_execution_record_and_copy_are_bound():
    r=json.loads((ROOT/'master/artwork-native-validation.json').read_text())
    assert r['executed'] and r['reopened'] and r['passed']
    assert all(c['ink_mean_absolute_error']<5 for c in r['visual']['critical_crops'])
    assert r['live_glyphs_match'] and r['fonts_matched'] and r['expected_glyph_count']==71
    assert r['visual']['dpi']==600 and r['visual']['ink_mean_absolute_error']<3
    record=json.loads((ROOT/'publication.json').read_text())
    assert fm.fa.sha(ROOT/'master/artwork-native.ai')==record['files']['master/artwork-native.ai']


def test_golden_legacy_wall_law_still_refuses_144():
    r=legacy_negative();assert r['passed_negative'] and r['required_height_mm']>300


@pytest.mark.parametrize('case,minimum,rise',[('family',322,54),('144',322,54),('146',278,37)])
def test_exact_briefs_minimum_certified_height_and_every_bottle(case,minimum,rise):
    result=solve(case)
    assert result['minimum_height_mm']==minimum and result['rise']==rise
    assert result['status']=='refused' and result['about_height_passed']
    assert not result['exact_requested_height']['identity_passed']
    point=result['sightlines']['pass_point'];assert point['passed'] and len(point['bottles'])==12
    assert all(b['identity_passed'] for b in point['bottles'])
    for r in point['rows']:assert 0<=r['decoration_fraction_lower']<=r['decoration_fraction_upper']<=1
    if case=='146':
        assert result['decoration']==[-8,0,8,86]
        assert 'Kiss' in result['original_brief'] and result['product_spec_hash'] is None
    if case=='144':assert 'Ginkgo' in result['original_brief']


def test_stagger_preserves_pitch_and_refuses_actual_hole_extent():
    r=solve('family',True)
    assert r['pitch']==42.2 and r['plan_checks']['literal_half_pitch_mm']==21.1
    assert r['status']=='refused' and not r['plan_checks']['passed']
    assert r['plan_checks']['rightmost_hole_edge_mm']==pytest.approx(189.9)


@pytest.mark.parametrize('mutation',[lambda m:m.update(identity=[]),lambda m:m['positions'].pop(),lambda m:m['positions'][0].update(id='r1-c2'),lambda m:m['identity'][0].update(flat_bbox_mm=[-2,70,2,80])])
def test_missing_or_corrupted_identity_never_vacuously_passes(mutation):
    model=model_at();mutation(model)
    with pytest.raises(ValueError):evaluate(model,decoration=False)


def test_actual_pitch_has_gaps_and_complete_ray_bundle_certification():
    # A narrow actual cylinder misses these rays; a full-width row wall does not.
    eye=(0,-50,50);target=((19,21),(50,51),(9,11))
    assert solid_relation(eye,target,cylinder('bottle',-20,0,0,100,5))==1
    assert solid_relation(eye,target,box('old wall',-100,-5,0,100,5,100))==-1
    model=model_at(rise=54)
    assert evaluate(model,decoration=False)['passed']
    # No rounded centre-ray substitute: partial occlusion stays a failure.
    assert not evaluate(model_at(rise=43),decoration=False)['passed']


def test_decoration_binding_keeps_source_region_and_surface_assets():
    model=model_at();spec=json.loads((ROOT/'master/design-spec.json').read_text())
    assert model['decoration']==spec['decoration_region_mm']
    bindings=json.loads((ROOT/'stand-family/surfaces/surface-bindings.json').read_text())
    assert bindings['product_spec_hash']==fm.digest(spec)
    ground=json.loads(fm.fa.MEASUREMENT.read_text())['ground']['samples'][0]
    colours={l['id']:l['colour'] for l in spec['graph']['lines']}
    assert bindings['header_copy_colours_srgb_255']==colours
    import fitz
    with fitz.open(ROOT/'stand-family/surfaces/header.front.pdf') as doc:
        spans=[span for block in doc[0].get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans']]
        ink=next(span['color'] for span in spans if span['text']=='SUN')
        assert all(abs(a-b)<=1 for a,b in zip([(ink>>16)&255,(ink>>8)&255,ink&255],colours['SUN']))
    for surface in bindings['surfaces']:
        assert surface['production_blockers']
        provenance=surface['colour_ground']
        assert provenance['measurement_sha256']==spec['measurement_sha256']
        assert provenance['sample_index']==0 and provenance['xy_px']==ground['xy_px']
        assert provenance['srgb_255']==ground['srgb_255']
        assert surface['output_colour_space'].startswith('RGB review proof')
        with fitz.open(ROOT/'stand-family/surfaces'/(surface['surface_id']+'.pdf')) as doc:
            # The upper-left clear ground is outside the logo, text and swoosh.
            pixel=doc[0].get_pixmap().pixel(3,3)
            assert all(abs(a-b)<=1 for a,b in zip(pixel,ground['srgb_255']))
        if surface['effective_ppi']:
            assert surface['effective_ppi']>=300 and surface['raster_source_sha256']==spec['assets']['swoosh']['sha256']
    header=next(s for s in bindings['surfaces'] if s['surface_id']=='header.front')
    assert header['languages']==['EN','AR'] and len(header['required_copy'])==6


def test_material_and_mask_cannot_drift_under_same_product_hash(tmp_path,monkeypatch):
    import shutil
    from PIL import Image
    spec=json.loads((ROOT/'master/design-spec.json').read_text());target=tmp_path/'assets';shutil.copytree(fm.PRESET,target);monkeypatch.setattr(fm,'PRESET',target)
    path=target/'swoosh-reference-support.png';im=Image.open(path);im.putpixel((0,0),255);im.save(path)
    with pytest.raises(ValueError):fm.validate_spec(spec)


