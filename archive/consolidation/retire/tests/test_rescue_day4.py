"""Measured failures are successful guard behavior, never creative acceptance."""
import copy,json
from pathlib import Path
import numpy as np
import pytest
from apps.pipeline.services import fidelity_master as fm
from apps.pipeline.services import fidelity_checks as fc
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


def test_golden_day2_fails_actual_same_fidelity_instrument(tmp_path):
    result=fc.negative_control(tmp_path)
    assert not result['placement_passed'] and not result['colour_passed'] and not result['swoosh_passed']


def test_current_master_cannot_claim_creative_pass():
    measured=fc.inspect_bundle(ROOT/'master')
    assert measured['all_elements_present'] and measured['live_copy_logical_actualtext']
    assert not measured['placement_passed'] and not measured['measured_fidelity_passed']
    assert measured['colour_passed'] and measured['swoosh_passed']
    arabic=next(r for r in measured['placement'] if r['id']=='arabic')
    assert arabic['delta_scale_percent'][1]>3
    critic=json.loads((ROOT/'master/critic.json').read_text())
    assert critic['mean']>=8 and critic['critical_min']==6 and not critic['passed']
    assert critic['repairs_used']==critic['repair_limit']==2


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


@pytest.mark.django_db(transaction=True)
def test_review_pages_download_integrity_no_mutation_or_approve(client):
    from django.contrib.auth.models import User
    from django.urls import reverse
    user=User.objects.create_superuser('fidelity-owner',password='test');client.force_login(user)
    for name in ('day4_serum','day4_stand'):
        url=reverse('dashboard:'+name);response=client.get(url)
        assert response.status_code==200 and b'Designer review needed' in response.content
        assert b'>Approve<' not in response.content and client.post(url,{}).status_code==405
    response=client.get(reverse('dashboard:fidelity_file',args=['package']));assert response.status_code==200;response.close()
    assert client.get(reverse('dashboard:fidelity_file',args=['unknown'])).status_code==404


def test_colour_difference_reference_pairs_and_masked_ssim():
    assert fc.delta_e_2000([50,2.6772,-79.7751],[50,0,-82.7485])==pytest.approx(2.0425,abs=.0001)
    assert fc.delta_e_2000([50,0,0],[50,-1,2])==pytest.approx(2.3669,abs=.0001)
    im=np.full((50,50,3),120,np.uint8);mask=np.zeros((50,50),np.uint8);mask[20:30,20:30]=255
    assert fm.fa.ssim(im,im,mask)==pytest.approx(1)
    bad=im.copy();bad[20:30,20:30]=250
    assert fm.fa.ssim(im,bad,mask)<.85


def test_changed_pdf_cannot_borrow_stale_projection(tmp_path):
    import shutil,fitz
    for name in ('design-spec.json','projected-master.png','artwork.pdf'):shutil.copyfile(ROOT/'master'/name,tmp_path/name)
    with fitz.open(tmp_path/'artwork.pdf') as doc:
        doc[0].draw_rect(doc[0].rect,fill=(.1,.2,.9),color=None,overlay=True);doc.save(tmp_path/'changed.pdf')
    (tmp_path/'changed.pdf').replace(tmp_path/'artwork.pdf')
    result=fc.inspect_bundle(tmp_path)
    assert not result['cached_projection_matches_pdf'] and not result['colour_passed'] and not result['swoosh_passed']


def test_actualtext_metadata_does_not_make_a_flattened_picture_live(tmp_path):
    import shutil,fitz
    for name in ('design-spec.json','projected-master.png'):shutil.copyfile(ROOT/'master'/name,tmp_path/name)
    source=fitz.open(ROOT/'master/artwork.pdf');doc=fitz.open();page=doc.new_page(width=source[0].rect.width,height=source[0].rect.height)
    page.insert_image(page.rect,filename=str(ROOT/'master/artwork.png'))
    stream=page.get_contents()[0];metadata='\n'.join('/Span << /ActualText <FEFF'+line['logical_text'].encode('utf-16-be').hex().upper()+'> >> BDC EMC' for line in json.loads((ROOT/'master/design-spec.json').read_text())['graph']['lines'])
    doc.update_stream(stream,doc.xref_stream(stream)+metadata.encode());doc.save(tmp_path/'artwork.pdf');doc.close();source.close()
    result=fc.inspect_bundle(tmp_path)
    assert not result['actual_live_glyphs_and_fonts_match'] and not result['live_copy_logical_actualtext']


def test_material_and_mask_cannot_drift_under_same_product_hash(tmp_path,monkeypatch):
    import shutil
    from PIL import Image
    spec=json.loads((ROOT/'master/design-spec.json').read_text());target=tmp_path/'assets';shutil.copytree(fm.PRESET,target);monkeypatch.setattr(fm,'PRESET',target)
    path=target/'swoosh-reference-support.png';im=Image.open(path);im.putpixel((0,0),255);im.save(path)
    with pytest.raises(ValueError):fm.validate_spec(spec)


@pytest.mark.django_db
def test_review_download_rejects_mutated_bytes_and_nonmember(client,tmp_path,monkeypatch):
    from django.contrib.auth.models import User
    from django.urls import reverse
    from apps.dashboard import fidelity_views as views
    user=User.objects.create_superuser('download-reviewer',password='test');client.force_login(user)
    record=views.checked_record();monkeypatch.setattr(views,'checked_record',lambda:record);monkeypatch.setattr(views,'root',lambda:tmp_path)
    (tmp_path/'master').mkdir();(tmp_path/'master/artwork.png').write_bytes(b'changed')
    assert client.get(reverse('dashboard:fidelity_file',args=['flat'])).status_code==404
    denied=User.objects.create_user('not-design-team',password='test');client.force_login(denied)
    assert client.get(reverse('dashboard:fidelity_file',args=['flat'])).status_code==403
