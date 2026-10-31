"""Day 6 render contracts: assembly revision 3, the per-glyph SUN locator on the real
header, the scene config's seven pinned surfaces, locality/UV verdict logic on
synthetic masks and the D-D4-1 instrument values. No database, no Blender."""
import json
from pathlib import Path
import numpy as np
import pytest
from apps.pipeline.services import fidelity_assets as fa,fidelity_master as fm,identity_assembly as ia
from apps.pipeline.services import day6_assembly as asm,day6_scene as scene,day6_render_checks as checks

BOTTLE_R3='feffc3e67cd56f88fe7a46e9d10e85dcea662d74c097bc7e4fed7fa1ffeb67dc'


def test_assembly_revision_3_fields_and_parent_hash():
    m=asm.revision3();parent=json.loads(asm.DAY4_ASSEMBLY.read_text());bottle=json.loads(asm.BOTTLE_SPEC.read_text());bindings=json.loads(asm.BINDINGS.read_text())
    assert m['revision']==3 and m['product_revision']==3 and m['case_id']=='family' and m['rise']==54 and m['seats']==[6,60,114] and m['required_height']==322
    assert parent['revision']==2 and m['parent_hash']==fm.digest(parent)=='2b8db8dc26dffb2a4ef368325c605d1c9727bff9d5167d61f4812a59e3b6cc6a'
    assert m['product_spec_hash']==fm.digest(bottle)==BOTTLE_R3 and m['product_review_state']=='designer_review'
    assert len(m['artwork_binding']['surfaces'])==7 and m['artwork_binding']['review_state']=='designer_review'
    assert [s['spec_hash'] for s in m['artwork_binding']['surfaces']]==[s['spec_hash'] for s in bindings['surfaces']]
    assert [s['pdf_sha256'] for s in m['artwork_binding']['surfaces']]==[s['pdf_sha256'] for s in bindings['surfaces']]
    assert m['identity']==bottle['identity_zones'] and m['identity_source']['differs_from_revision_2'] is False and m['production_ready'] is False
    base=ia.model_at('family',54)
    assert all(m[k]==base[k] for k in ('positions','profile','identity','decoration','seats','tread','pitch','hole','thickness','header_height','envelope'))
    assert m['realised_envelope_mm']==[180,150,322] and m['requested_height_shortfall_mm']==22


def test_sun_glyph_locator_finds_exactly_three_glyphs_in_the_real_header():
    import fitz
    box=checks.measured_sun_box();assert box['copy']=='SUN'
    header=checks.header_folder(1);assert header==checks.HEADER;title=checks.title_postscript(header)
    with fitz.open(header/'artwork.pdf') as doc:
        page=doc[0];glyphs=checks.locate_sun_glyphs(page,box,title);trace=page.get_texttrace()
    assert [g['char'] for g in glyphs]==['S','U','N'] and len({g['font'] for g in glyphs})==1
    xs=[g['origin_mm'][0] for g in glyphs];assert xs==sorted(xs) and len({round(g['origin_mm'][1],3) for g in glyphs})==1
    x0,y0,x1,y1=box['bbox_mm']
    assert all(x0-3<=g['bbox_mm'][0] and g['bbox_mm'][2]<=x1+3 and y0<=g['origin_mm'][1]<=y1+3 for g in glyphs)
    rects=checks.redaction_rects(glyphs,box)
    repair_top=min(c[3][1]/checks.MM for span in trace for c in span['chars'] if span['font']==glyphs[0]['font'] and chr(c[0]) in 'REPAIR' and c[2][1]/checks.MM>50)
    assert len(rects)==3 and all(r.y1/checks.MM<repair_top and r.y0/checks.MM<y0 for r in rects)
    moved=dict(box,bbox_mm=[x0,y0+40,x1,y1+40])
    with fitz.open(header/'artwork.pdf') as doc:
        with pytest.raises(ValueError,match='S,U,N'):checks.locate_sun_glyphs(doc[0],moved,title)
    two=checks.header_folder(2)
    with fitz.open(two/'artwork.pdf') as doc:
        assert [g['char'] for g in checks.locate_sun_glyphs(doc[0],box,checks.title_postscript(two))]==['S','U','N']


def test_assembly_revision_4_pins_surfaces_revision_2_without_moving_geometry():
    three=asm.revision3();four=asm.revision4();parent=json.loads(asm.ASSEMBLY_R1.read_text());bindings=json.loads(asm.BINDINGS_R2.read_text())
    assert four['revision']==4 and parent['revision']==3 and four['parent_hash']==fm.digest(parent) and four['parent_file_sha256']==fa.sha(asm.ASSEMBLY_R1)
    assert asm.geometry_digest(four)==asm.geometry_digest(three) and four['product_spec_hash']==BOTTLE_R3 and four['identity']==three['identity']
    assert four['artwork_binding']['revision']==2 and four['artwork_binding']['bindings_sha256']==fa.sha(asm.BINDINGS_R2) and four['artwork_binding']['parent_bindings_sha256']==fa.sha(asm.BINDINGS)
    assert [s['spec_hash'] for s in four['artwork_binding']['surfaces']]==[s['spec_hash'] for s in bindings['surfaces']] and [s['pdf_sha256'] for s in four['artwork_binding']['surfaces']]==[s['pdf_sha256'] for s in bindings['surfaces']]
    assert four['artwork_binding']['surfaces'][0]['spec_hash']!=three['artwork_binding']['surfaces'][0]['spec_hash']


def test_prepare_config_carries_seven_surfaces_with_matching_hashes(tmp_path):
    cfg=scene.prepare(tmp_path/'render',1);bindings=json.loads(scene.BINDINGS.read_text());measurement=json.loads(scene.MEASUREMENT.read_text())
    assert cfg['schema']=='day6_scene/1' and cfg['stand_artwork_revision']==3 and cfg['bottle_revision']==3 and cfg['samples']==32 and cfg['seed']==0
    assert cfg['resolution']==[2126,2835] and cfg['ppi']==300 and cfg['views']==['front','median','three-quarter','plan-front'] and cfg['threads']==6
    assert cfg['label']=='deterministic material approximation' and cfg['construction_status']=='provisional, not fabrication approval'
    assert [s['surface_id'] for s in cfg['surfaces']]==[s['surface_id'] for s in bindings['surfaces']] and len(cfg['surfaces'])==7
    for s,b in zip(cfg['surfaces'],bindings['surfaces']):
        assert s['spec_hash']==b['spec_hash'] and s['pdf_sha256']==b['pdf_sha256']==fa.sha(Path(s['pdf'])) and s['source_status']==b['source_status']
        assert fa.sha(Path(s['texture']))==s['texture_sha256'] and abs(s['texture_px'][0]-b['size_mm'][0]/25.4*300)<=1 and abs(s['texture_px'][1]-b['size_mm'][1]/25.4*300)<=1
    header=next(s for s in cfg['surfaces'] if s['surface_id']=='header.front')
    assert header['required_copy']==measurement['required_header_copy'] and 'SUN' in header['required_copy'] and header['languages']==['EN','AR']
    assert all(s['required_copy']==[] for s in cfg['surfaces'] if s['surface_id']!='header.front')
    assert cfg['bottle_spec_hash']==fm.digest(cfg['bottle_spec'])==cfg['assembly']['product_spec_hash']==BOTTLE_R3 and cfg['assembly']['revision']==3
    assert cfg['script_sha256']==fa.sha(scene.SCRIPT) and cfg['assembly_sha256']==fa.sha(scene.ASSEMBLY)
    changed=json.loads(json.dumps(cfg));Path(changed['surfaces'][0]['texture']).write_bytes(b'x')
    with pytest.raises(ValueError,match='texture changed'):scene.ds.source_preflight(changed)
    two=scene.prepare(tmp_path/'render-r2',2);r2=json.loads((scene.profile(2)['surfaces']/'surface-bindings.json').read_text())
    assert two['surfaces_revision']==2 and two['assembly']['revision']==4 and two['stand_artwork_revision']==4 and two['bindings_sha256']==fa.sha(scene.profile(2)['surfaces']/'surface-bindings.json')
    assert [(s['surface_id'],s['spec_hash'],s['pdf_sha256']) for s in two['surfaces']]==[(s['surface_id'],s['spec_hash'],s['pdf_sha256']) for s in r2['surfaces']] and two['bottle_spec_hash']==BOTTLE_R3
    with pytest.raises(ValueError):scene.prepare(tmp_path/'render-x',3)


def test_locality_logic_on_synthetic_masks():
    base=np.zeros((20,30,3),np.uint8);regions={'header.front':[5,5,12,10],'bottle/r1-c1/body.front':[20,12,26,18],'other':[0,0,2,2]}
    inside=base.copy();inside[6:9,6:10]=255
    r,changed=checks.locality(base,inside,regions,'header.front')
    assert r['passed'] and r['changed_pixels']==12 and r['outside_surface_pixels']==0 and r['inside_region_pixels']==12 and r['regions_used']==1 and changed.sum()==12
    outside=inside.copy();outside[15,2]=7
    r,_=checks.locality(base,outside,regions,'header.front');assert not r['passed'] and r['outside_surface_pixels']==1 and r['changed_pixels']==13
    r,_=checks.locality(base,base,regions,'header.front');assert not r['passed'] and r['changed_pixels']==0
    bottle=base.copy();bottle[13:15,21:24]=9
    r,_=checks.locality(base,bottle,regions,'bottle/');assert r['passed'] and r['regions_used']==1
    r,_=checks.locality(base,bottle,regions,'header.front');assert not r['passed'] and r['outside_surface_pixels']==6
    r,_=checks.locality(base,inside,regions,'nothing.');assert not r['passed'] and r['regions_used']==0


def test_uv_verdict_and_overall_verdict_require_the_negative_to_fail():
    im=np.zeros((40,40,3),np.uint8);im[:20,:20]=[255,0,0];im[:20,20:]=[0,255,0];im[20:,:20]=[0,0,255];im[20:,20:]=[255,255,0]
    samples=[{'expected':'red','pixel':[10,10]},{'expected':'green','pixel':[30,10]},{'expected':'blue','pixel':[10,30]},{'expected':'yellow','pixel':[30,30]}]
    positive=checks.uv_verdict(im,samples);negative=checks.uv_verdict(im[:,::-1],samples)
    assert positive['passed'] and len(positive['samples'])==4 and not negative['passed'] and not any(s['passed'] for s in negative['samples'])
    assert not checks.uv_verdict(im,[])['passed']
    edits={'header-edit':{'passed':True},'bottle-edit':{'passed':True}}
    assert checks.verdict(edits,{'uv-positive':positive,'uv-mirrored-negative':negative})
    assert not checks.verdict(edits,{'uv-positive':positive,'uv-mirrored-negative':positive})
    assert not checks.verdict(edits,{'uv-positive':negative,'uv-mirrored-negative':negative})
    assert not checks.verdict({'header-edit':{'passed':True},'bottle-edit':{'passed':False}},{'uv-positive':positive,'uv-mirrored-negative':negative})
    assert not checks.verdict({},{'uv-positive':positive,'uv-mirrored-negative':negative})


def test_sightline_instrument_values_equal_INSTRUMENT():
    m=asm.revision3();assert m['instrument']==ia.INSTRUMENT and m['instrument'] is not ia.INSTRUMENT
    assert dict(asm.POINTS)=={'pass_point':(550,500),'median':(650,650),'secondary':(350,500),'far_advisory':(550,800)}
    assert all(tuple(ia.INSTRUMENT[name])==point for name,point in asm.POINTS)
    assert ia.INSTRUMENT['identity_cell_mm']==.05 and ia.INSTRUMENT['ray_margin_mm']==.25 and ia.INSTRUMENT['eye_above_base_band_mm']==[550,750] and ia.INSTRUMENT['front_distance_band_mm']==[500,800]
    record=json.loads((asm.ROOT/'sightlines.json').read_text())
    assert record['instrument']==ia.INSTRUMENT and record['assembly_revision']==3 and record['geometry_digest']==asm.geometry_digest(m)
    for name,(eye_z,distance) in asm.POINTS:
        point=record['points'][name];assert (point['eye_above_base_mm'],point['front_distance_mm'])==(eye_z,distance)
        assert point['result']['eye_above_base_mm']==eye_z and point['result']['front_distance_mm']==distance and len(point['result']['bottles'])==12
        assert record['day4_comparison']['points'][name]['passed_day6']==point['result']['passed']
    assert record['certification']['pass_point']==record['points']['pass_point']['result']['passed']
