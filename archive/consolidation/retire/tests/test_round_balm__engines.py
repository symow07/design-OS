"""Round 1 physical geometry and protected-pixel contracts (no providers)."""
import json
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import round_balm_sheet as sheet
from apps.pipeline.services import rank_round as rank
from apps.pipeline.services import whole_object_check as whole
from apps.pipeline.services import round_balm_page as page


@pytest.fixture
def built(tmp_path):
    sheet.build(tmp_path)
    return tmp_path


def test_sheet_scale_aspect_crop_and_mask(built):
    proof=sheet.verify(built)
    assert proof['passes'],proof
    assert proof['panel_count']==9
    rec=json.loads((built/'sheet.json').read_text())
    assert rec['px_per_mm']==pytest.approx(868/179.25)
    assert set(rec['panels'])==set(sheet.PANEL_IDS)
    for row in rec['panels'].values():
        crop=Image.open(built/'sheet.png').crop(row['box_px'])
        assert crop.width>0 and crop.height>0


def test_engine_back_is_taller_than_front(built):
    panels=json.loads((built/'sheet.json').read_text())['panels']
    assert panels['back']['mm']==pytest.approx([20.45,74.35])
    assert panels['front']['mm']==pytest.approx([20.45,73.45])
    assert panels['top_end']['mm']==pytest.approx([20,20.45])
    assert panels['label']['mm']==[18,18]
    assert panels['label']['trim_mm']==[16,16]
    assert panels['label']['bleed_tb_mm']==1


def test_existing_paid_contract_cannot_be_overwritten(built):
    with pytest.raises(ValueError,match='immutable'):sheet.build(built)


def test_marks_fallback_requires_sixty_real_minutes(tmp_path,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from apps.pipeline.services import round_balm_run as run
    monkeypatch.setattr(run,'OUT',tmp_path)
    notice=datetime(2026,10,25,8,0,tzinfo=timezone.utc)
    (tmp_path/'marks-checkpoint.json').write_text(json.dumps({'fallback_after':(notice+timedelta(minutes=60)).isoformat()}))
    assert not run.fallback_due(notice+timedelta(minutes=59,seconds=59))
    assert run.fallback_due(notice+timedelta(minutes=60))


def test_timeout_never_replaces_arrived_owner_marks(tmp_path,monkeypatch):
    from apps.pipeline.services import round_balm_run as run
    owner={'marks':[{'id':'A1','preserve':'the cap ring'}],'source':'owner'}
    monkeypatch.setattr(run,'poll_marks',lambda:(owner,{'fallback_due':True}))
    assert run.fallback_marks([{'id':'B1','preserve':'other'}]) is owner


def test_overlong_blind_reading_uses_remaining_allowance_and_no_seed(tmp_path,monkeypatch):
    monkeypatch.setattr(whole,'OUT',tmp_path)
    dest=tmp_path/'sketches/A1';dest.mkdir(parents=True)
    requests=[]
    def paid(operation,prompt,destination,**kwargs):
        requests.append((operation,prompt,kwargs))
        idea='one two three four five six seven eight nine ten eleven'
        if len(requests)==2:idea='A broken seal binds the remaining faces'
        return {'accounted_usd':.016,'payload':{'idea_in_ten_words':idea,'proof_panel':'label','proof':'A visible border repeats the cap rim.'}}
    monkeypatch.setattr(whole,'text_call',paid)
    result=whole.read_blind(dest)
    assert len(result['idea_in_ten_words'].split())<=10
    assert len(requests)==2 and requests[1][2]['ceiling']==pytest.approx(.044)
    assert 'one two three' not in requests[1][1]
    evidence=json.loads((dest/'blind-word-limit.json').read_text())
    assert evidence['total_accounted_usd']==pytest.approx(.032)
    assert evidence['seed_or_prior_reading_shown'] is False


def test_publication_refuses_duplicate_or_wrong_candidate_count(tmp_path):
    with pytest.raises(ValueError,match='distinct'):page.publish('marks',['A1']*8,out=tmp_path)
    with pytest.raises(ValueError,match='distinct'):page.publish('pick',['A1'],out=tmp_path)


def test_glue_and_tuck_tongue_never_editable(built):
    rec=json.loads((built/'sheet.json').read_text())
    mask=np.array(Image.open(built/'sheet-mask.png'))
    ox,oy=rec['die_origin_px'];s=rec['px_per_mm']
    for x,y in [(6,65),(22,3),(22,128),(42,23),(84,23)]:
        assert mask[round(oy+y*s),round(ox+x*s),3]==255


def test_front_third_is_cylinder_centre_not_wrap_midpoint(built):
    rec=json.loads((built/'sheet.json').read_text())
    assert rec['front_centre_mm']==pytest.approx(30.2256661)
    assert rec['front_third_mm']==pytest.approx([20.800888,39.650444],abs=1e-5)


def test_protected_fragment_is_byte_identical_even_if_model_changes_it(tmp_path):
    rng=np.random.default_rng(7)
    original=rng.integers(0,256,(20,20,4),dtype=np.uint8)
    original[:,:,3]=255
    changed=np.full_like(original,255)
    mask=np.full_like(original,255);mask[:,:,3]=0;mask[5:15,5:15,3]=255
    for name,data in [('parent',original),('raw',changed),('mask',mask)]:
        Image.fromarray(data).save(tmp_path/(name+'.png'))
    result=sheet.protected_edit(tmp_path/'parent.png',tmp_path/'raw.png',tmp_path/'mask.png',tmp_path/'out.png')
    out=np.array(Image.open(tmp_path/'out.png'))
    assert result['protected_byte_identical']
    assert result['raw_changed_protected_pixels']==100
    assert np.array_equal(out[5:15,5:15],original[5:15,5:15])
    assert np.array_equal(out[:5],changed[:5])


def test_dimension_change_is_never_stretched(tmp_path):
    for name,size in [('parent',(20,20)),('raw',(21,20)),('mask',(20,20))]:
        Image.new('RGBA',size,'white').save(tmp_path/(name+'.png'))
    with pytest.raises(ValueError,match='dimensions'):
        sheet.protected_edit(tmp_path/'parent.png',tmp_path/'raw.png',tmp_path/'mask.png',tmp_path/'out.png')


def inspection():
    return {'panels':{key:{'state':'present','evidence':'distinctive shared gesture','explained_by':''}
                       for key in sheet.PANEL_IDS},
            'copy_presence':{key:'present' for key in whole.COPY_KEYS},'banned_motifs':[]}


def test_blank_panel_disqualified():
    p=inspection();p['panels']['side_left']['state']='blank'
    assert not whole.decide(p,{'qualifies':True})['eligible']


def test_quiet_panel_requires_explanation_beyond_itself():
    p=inspection();p['panels']['back']['state']='quiet'
    assert not whole.decide(p,{'qualifies':True})['eligible']
    p['panels']['back']['explained_by']='The front cut continues in the margin around the regulated copy.'
    assert whole.decide(p,{'qualifies':True})['eligible']


@pytest.mark.parametrize('state',['generic','different design'])
def test_generic_or_foreign_panel_disqualified(state):
    p=inspection();p['panels']['cap']['state']=state
    assert not whole.decide(p,{'qualifies':True})['eligible']


def test_banned_motif_and_aspect_disqualify():
    p=inspection();p['banned_motifs']=['bees on the cap']
    assert not whole.decide(p,{'qualifies':True})['eligible']
    assert not whole.decide(inspection(),{'qualifies':False})['eligible']


def test_incomplete_vision_not_an_eligible_candidate():
    p=inspection();del p['panels']['label']
    with pytest.raises(ValueError):whole.decide(p,{'qualifies':True})


def test_one_complete_json_fence_allows_outside_notes_but_not_ambiguous_blocks():
    from apps.pipeline.services.round_calls import parse_response_text
    assert parse_response_text('```json\n{"eligible": false}\n```\nInspection notes.') == {'eligible':False}
    assert parse_response_text('Inspection notes.\n\n```json\n{"eligible": false}\n```') == {'eligible':False}
    for bad in ['```json\n{"eligible": false}', '```json\n{}\n```\n```json\n{}\n```', '{"a":1} trailing']:
        with pytest.raises(ValueError):parse_response_text(bad)


def test_coarse_disagreement_places_displace_rank_sum_tail():
    j1=list('ABCDEFGHIJKL');j2=list('LABCDEFGHIJK')
    result=rank.coarse_cut(j1,j2)
    assert result['reserved'][0]=='L'
    assert len(result['shortlist'])==10
    assert 'L' in result['shortlist']
    assert result['rank_sum']['L']==13
    assert result['spread']['L']==11


def test_coarse_no_disagreement_keeps_rank_sum_ten():
    order=list('ABCDEFGHIJKL')
    r=rank.coarse_cut(order,order)
    assert r['reserved']==[] and r['shortlist']==order[:10]


def test_coarse_rank_must_be_permutation():
    with pytest.raises(ValueError):rank.coarse_cut(['A','B'],['A','A'])


@pytest.mark.parametrize('count,total,batch_count',[(10,45,5),(9,36,4)])
def test_every_pair_once_and_at_most_nine_per_batch(count,total,batch_count):
    ids=[str(x) for x in range(count)];batches=rank.pair_batches(ids)
    pairs=[frozenset(p) for b in batches for p in b]
    assert len(pairs)==total and len(set(pairs))==total
    assert len(batches)==batch_count and max(map(len,batches))<=9


def pair(a,b,winner):return {'pair':[a,b],'winner':winner,'relationship':'The cap changes the bottom label reading.'}


def test_tie_uses_J1_head_to_head_before_rank_sum():
    j1=[pair('A','B','B')];j2=[pair('A','B','A')]
    r=rank.fine_order(['A','B'],j1,j2,{'A':1,'B':99})
    assert r['wins']=={'A':1,'B':1} and r['order']==['B','A']


def test_three_way_cycle_uses_rank_sum_after_tied_J1_head_to_heads():
    rows=[pair('A','B','A'),pair('A','C','C'),pair('B','C','B')]
    r=rank.fine_order(list('ABC'),rows,list(reversed(rows)),{'A':4,'B':2,'C':3})
    assert r['order']==list('BCA')
    assert r['wins']=={'A':2,'B':2,'C':2}


@pytest.mark.parametrize('rows',[[pair('A','B','A')]*2,[],[pair('A','B','C')]])
def test_invalid_pairs_refused(rows):
    with pytest.raises(ValueError):rank.validate_pairs(rows,[('A','B')])


def test_file_door_refuses_modified_and_escaping_paths(tmp_path):
    import hashlib
    data=b'original';(tmp_path/'a.png').write_bytes(data)
    publication={'schema':'r1_balm_publication/1','files':{
        'a':{'path':'a.png','sha256':hashlib.sha256(data).hexdigest()}}}
    (tmp_path/'publication.json').write_text(json.dumps(publication))
    assert page.checked_bytes('a',tmp_path)==(data,'image/png')
    (tmp_path/'a.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):page.checked_bytes('a',tmp_path)
    publication['files']['a']['path']='../escape.png'
    (tmp_path/'publication.json').write_text(json.dumps(publication))
    with pytest.raises(ValueError,match='Outside'):page.checked_bytes('a',tmp_path)
    with pytest.raises(KeyError):page.checked_bytes('unknown',tmp_path)


def test_file_door_refuses_symlink_escape(tmp_path):
    import hashlib
    outside=tmp_path.parent/(tmp_path.name+'-outside.png');outside.write_bytes(b'outside')
    (tmp_path/'alias.png').symlink_to(outside)
    (tmp_path/'publication.json').write_text(json.dumps({'schema':'r1_balm_publication/1','files':{
        'a':{'path':'alias.png','sha256':hashlib.sha256(b'outside').hexdigest()}}}))
    with pytest.raises(ValueError,match='Outside'):page.checked_bytes('a',tmp_path)


def test_raw_aspect_detects_shrunk_art_with_unchanged_template_guides(built):
    from PIL import ImageDraw
    rec=json.loads((built/'sheet.json').read_text());dest=built/'candidate';dest.mkdir()
    im=Image.new('RGB',(1536,1024),'white');d=ImageDraw.Draw(im)
    x0,y0,x1,y1=rec['panels']['body']['box_px']
    d.rectangle((x0,y0,x0+round((x1-x0)*.9),y1-1),fill=(70,50,40))
    im.save(dest/'raw.png')
    (dest/'crop.json').write_text(json.dumps({'panels':{p:{'qualifies':True} for p in sheet.PANEL_IDS},'qualifies':True}))
    result=sheet.raw_geometry(dest,built)
    assert 'body' in result['measured_over_limit']
    assert json.loads((dest/'crop.json').read_text())['qualifies'] is False
    assert result['panels']['front']['status']=='unmeasured'


def test_label_geometry_measures_thin_outer_border_not_inner_art(built):
    from PIL import ImageDraw
    rec=json.loads((built/'sheet.json').read_text());dest=built/'candidate';dest.mkdir()
    im=Image.new('RGB',(1536,1024),'white');d=ImageDraw.Draw(im)
    x0,y0,x1,y1=rec['panels']['label']['box_px']
    d.ellipse((x0,y0,x1-1,y1-1),outline=(30,20,10),width=1)
    d.ellipse((x0+6,y0+3,x1-5,y1-4),fill=(60,40,20))
    im.save(dest/'raw.png')
    (dest/'crop.json').write_text(json.dumps({'panels':{p:{'qualifies':True} for p in sheet.PANEL_IDS}}))
    result=sheet.raw_geometry(dest,built)
    assert result['panels']['label']['status']=='within_limit'


def test_verified_manual_carton_aspect_can_disqualify(built):
    dest=built/'candidate';dest.mkdir()
    Image.new('RGB',(1536,1024),'white').save(dest/'raw.png')
    (dest/'crop.json').write_text(json.dumps({'panels':{p:{'qualifies':True} for p in sheet.PANEL_IDS}}))
    (dest/'manual-geometry.json').write_text(json.dumps({'raw_sha256':sheet.sha(dest/'raw.png'),
        'observations':[{'panel':'front','box_px':[800,460,900,800],'evidence':'Visible rectangular panel perimeter'}]}))
    result=sheet.raw_geometry(dest,built)
    assert 'front' in result['measured_over_limit']
    assert json.loads((dest/'crop.json').read_text())['qualifies'] is False


def test_paid_caption_identity_and_malformed_reply_are_durable(tmp_path,settings,monkeypatch):
    from types import SimpleNamespace
    from apps.pipeline.services import round_balm_calls as calls
    settings.RESCUE_SPEND_ROOT=tmp_path/'spend'
    monkeypatch.setattr(calls,'REPO',tmp_path);monkeypatch.setattr(calls,'OUT',tmp_path/'round')
    picture=tmp_path/'picture.png';Image.new('RGB',(20,20),'white').save(picture)
    raw={'content':[{'type':'text','text':'{"ok": true}'}],'usage':{'input_tokens':10,'output_tokens':8},'stop_reason':'end_turn'}
    client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw:SimpleNamespace(model_dump=lambda **unused:raw)))
    dest=tmp_path/'round/first.json'
    calls.text_call('test','read',dest,images=[('first caption',picture)],client=client)
    with pytest.raises(ValueError,match='silently replaced'):
        calls.text_call('test','read',dest,images=[('changed caption',picture)],client=client)
    raw['content'][0]['text']='not json'
    bad=tmp_path/'round/bad.json'
    with pytest.raises(ValueError,match='Incomplete'):
        calls.text_call('bad','read',bad,client=client)
    record=json.loads(bad.read_text())
    assert record['status']=='incomplete' and record['parse_error']=='JSONDecodeError'
    assert record['billing_state']=='usage_recorded'
    assert (tmp_path/'round/bad.response.json').exists()


def test_unresolved_billing_is_a_hold_not_usage_price(tmp_path,settings,monkeypatch):
    from types import SimpleNamespace
    from apps.pipeline.services import round_balm_calls as calls
    settings.RESCUE_SPEND_ROOT=tmp_path/'spend'
    monkeypatch.setattr(calls,'REPO',tmp_path);monkeypatch.setattr(calls,'OUT',tmp_path/'round')
    raw={'content':[{'type':'text','text':'{"ok": true}'}],'stop_reason':'end_turn'}
    client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw:SimpleNamespace(model_dump=lambda **unused:raw)))
    record=calls.text_call('test','read',tmp_path/'round/a.json',client=client)
    assert record['cost_usd'] is None
    assert record['accounted_usd']==record['reserved_usd']>0
