"""Day5 contracts: independent math/negative controls, roles and scoped spend."""
import json
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest
from PIL import Image
from apps.pipeline.services import two_ink_matte as matte
from apps.pipeline.services import display_concepts as concepts
from apps.pipeline.services import spend_reservation as spend
from apps.pipeline.services.cost_ledger import BudgetExceededError


def test_three_endmember_solve_recovers_mixtures_and_triangle_edges():
    b=np.array([.1,.03,.01]);f=np.array([.92,.72,.51]);s=np.array([.3,.15,.04])
    pairs=np.array([[0,0],[1,0],[0,1],[.3,.2],[.01,.98]])
    p=b*(1-pairs.sum(1))[:,None]+f*pairs[:,0,None]+s*pairs[:,1,None]
    ff,ss,_=matte.triangle_weights(p,np.broadcast_to(b,p.shape),f,s)
    assert np.allclose(ff,pairs[:,0]) and np.allclose(ss,pairs[:,1])
    ff,ss,_=matte.triangle_weights(np.array([[2.,-1.,.4]]),b[None,:],f,s)
    assert ff[0]>=0 and ss[0]>=0 and ff[0]+ss[0]<=1.0000001


def test_over_is_not_mislabelled_as_additive_proof():
    f,s=.3,.4;b=np.array([.2,.1,.03]);cream=np.array([.9,.8,.6]);shadow=np.array([.1,.03,.01])
    additive=f*cream+s*shadow+(1-f-s)*b
    over=f*cream+(1-f)*(s*shadow+(1-s)*b)
    assert not np.allclose(additive,over)


def test_poisson_heldout_rgb_cannot_influence_prediction():
    p=np.full((20,20,3),120,np.uint8);train=np.ones((20,20),bool);train[5:15,5:15]=False
    prior=np.full_like(p,110);first=matte.poisson_ground(p,train,prior)
    p[~train]=[255,0,255];second=matte.poisson_ground(p,train,prior)
    assert np.array_equal(first,second)
    assert np.max(np.abs(first.astype(int)-120))<=1


def test_scoped_allowance_refuses_before_provider(settings,tmp_path):
    settings.RESCUE_SPEND_ROOT=tmp_path/'spend'
    spend.reserve('openai','day5-continued/first','gpt-image-2',19,budget_prefix=concepts.BUDGET_PREFIX,prefix_cap=20)
    provider=Mock()
    with pytest.raises(BudgetExceededError):
        spend.paid_operation(provider,provider='openai',operation='day5-continued/next',reservation_prefix=concepts.BUDGET_PREFIX,reservation_cap=20,estimate_override=2,model='gpt-image-2')
    provider.assert_not_called()


def make_refs(tmp_path):
    rows=[]
    for i,(role,name) in enumerate([('product, exact','bottle-r3'),('geometry, exact','assembly-r2'),('house, style','house-069'),('house, style','house-043'),('house, style','house-048')]):
        p=tmp_path/f'{i}.png';Image.new('RGB',(2,2),(i*20,0,0)).save(p);rows.append(concepts.reference(p,role,name))
    return rows


def test_final_request_keeps_exact_and_style_roles_separate(tmp_path):
    refs=make_refs(tmp_path);prompt=concepts.request('Assembled countertop display, twelve bottles.',refs)
    assert 'product, exact' in prompt and 'geometry, exact' in prompt
    assert prompt.count('house, style')==3
    assert 'no display unit' not in prompt and 'COMPLETELY NEW' not in prompt
    Path(refs[0]['path']).write_bytes(b'changed')
    with pytest.raises(ValueError):concepts.request('stand',refs)


def test_unknown_or_missing_reference_role_refuses(tmp_path):
    refs=make_refs(tmp_path)
    with pytest.raises(ValueError):concepts.request('stand',refs[1:])
    refs[-1]['source_id']='another-brand'
    with pytest.raises(ValueError):concepts.request('stand',refs)


def test_retained_mattes_fail_new_print_instrument():
    p=matte.fa.ROOT/'docs/audit/day-5/two-ink/poisson-attempt/fidelity-instrument.json'
    report=json.loads(p.read_text())
    assert report['background']['passed'] and report['background']['heldout_excluded_from_fit']
    for name in ['day4_negative','single_ink_day5_negative']:
        result=report['results'][name]
        assert not (result['recomposition_passed'] and result['fringe_passed'])

def test_seventh_stand_attempt_and_second_isolation_refused(settings,tmp_path):
    from apps.pipeline.services.spend_reservation import reserve
    from apps.pipeline.services.cost_ledger import BudgetExceededError
    settings.RESCUE_SPEND_ROOT=tmp_path
    for i in range(6):
        reserve('openai',f'day5-continued/stand/{i}','gpt-image-2',.1,count_prefix='day5-continued/stand/',count_cap=6)
    with pytest.raises(BudgetExceededError):
        reserve('openai','day5-continued/stand/seventh','gpt-image-2',.1,count_prefix='day5-continued/stand/',count_cap=6)
    reserve('openai','day5-continued/swoosh-isolation','gpt-image-2',.1,count_prefix='day5-continued/swoosh-isolation',count_cap=1)
    with pytest.raises(BudgetExceededError):
        reserve('openai','day5-continued/swoosh-isolation','gpt-image-2',.1,count_prefix='day5-continued/swoosh-isolation',count_cap=1)

def test_traced_text_outline_and_hidden_raster_fail(tmp_path):
    import fitz
    from reportlab.pdfgen.canvas import Canvas
    from apps.pipeline.services.traced_text import pdf_live
    live=tmp_path/'live.pdf';c=Canvas(str(live),pagesize=(200,100));c.setFont('Helvetica',24);c.drawString(20,50,'SUN');c.save()
    lines=[{'id':'name','logical_text':'SUN','runs':[{'text':ch,'font':'Helvetica','origin':[20+offset,50]} for ch,offset in zip('SUN',[0,16.008,33.336])]}]
    assert pdf_live(live,lines)['passed']
    with fitz.open(live) as doc:
        svg=doc[0].get_svg_image(text_as_path=True)
        with fitz.open(stream=svg.encode(),filetype='svg') as vector:
            outlined=tmp_path/'outlined.pdf';outlined.write_bytes(vector.convert_to_pdf())
        pix=doc[0].get_pixmap(dpi=300)
    assert not pdf_live(outlined,lines)['passed']
    hidden=tmp_path/'hidden.pdf'
    with fitz.open(live) as doc:
        # Keep searchable live text, but cover it with a baked raster image.
        doc[0].insert_image(doc[0].rect,stream=pix.tobytes('png'),overlay=True);doc.save(hidden)
    result=pdf_live(hidden,lines)
    assert not result['passed'] and result['lines'][0]['live_font_and_position']
    assert result['lines'][0]['visible_text_contribution_pixels']==0


def test_baked_copy_detected_even_when_live_copy_exists(tmp_path):
    import shutil
    from PIL import ImageDraw,ImageFont
    from apps.pipeline.services.traced_text import ocr_layers
    if not shutil.which('tesseract'):pytest.skip('Tesseract is required for real OCR integration.')
    image=Image.new('RGBA',(600,200),(255,255,255,0));draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(matte.fa.APP/'static/fonts/brand2026/Barlow_Condensed/BarlowCondensed-Regular.ttf'),130)
    draw.text((20,10),'SUN',font=font,fill=(0,0,0,255))
    result=ocr_layers([image],['SUN'])
    assert not result['passed'] and result['hits']


def test_final_provider_receives_five_exact_role_files_and_assembled_prompt(settings,tmp_path):
    import base64,io
    from types import SimpleNamespace
    settings.RESCUE_SPEND_ROOT=tmp_path/'journal';refs=make_refs(tmp_path);seen={}
    b=io.BytesIO();Image.new('RGB',(8,8),'white').save(b,format='PNG')
    def edit(**kwargs):
        seen.update(kwargs);seen['opened_sha256']=[concepts.hashlib.sha256(f.read()).hexdigest() for f in kwargs['image']]
        payload={'data':[{'b64_json':base64.b64encode(b.getvalue()).decode()}],'usage':{'input_tokens':100,'output_tokens':100}}
        return SimpleNamespace(model_dump=lambda **_:payload)
    fake=SimpleNamespace(images=SimpleNamespace(edit=edit))
    result=concepts.generate('Exactly12bottles,3rows of4.',refs,tmp_path/'attempt',purpose='D1/attempt-1',client=fake)
    assert seen['opened_sha256']==[r['sha256'] for r in refs]
    assert 'ASSEMBLED COUNTERTOP DISPLAY STAND' in seen['prompt']
    assert 'product, exact' in seen['prompt'] and 'geometry, exact' in seen['prompt']
    assert 'no display unit' not in seen['prompt'] and 'COMPLETELY NEW' not in seen['prompt']
    assert result['reservation_id'] and (tmp_path/'attempt/image.png').exists()

def test_concurrent_last_attempt_only_one_reserves(settings,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    settings.RESCUE_SPEND_ROOT=tmp_path/'journal'
    prefix='day5-continued/stand/'
    for i in range(5):spend.reserve('openai',prefix+str(i),'gpt-image-2',.1,count_prefix=prefix,count_cap=6)
    def attempt(n):
        try:return spend.reserve('openai',prefix+str(n),'gpt-image-2',.1,count_prefix=prefix,count_cap=6)
        except BudgetExceededError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[6,7]))
    assert sum(x is not None for x in results)==1
    for i in range(3):spend.reserve('openai',f'direction/D1/{i}','gpt-image-2',.1,attempt_limits=[('direction/D1/',3)])
    with pytest.raises(BudgetExceededError):spend.reserve('openai','direction/D1/4','gpt-image-2',.1,attempt_limits=[('direction/D1/',3)])

def test_r3_export_cannot_change_historical_font_or_raster_defaults(tmp_path):
    import fitz
    from apps.pipeline.services import fidelity_master as fm,day5_master as dm
    old=json.loads((matte.fa.ROOT/'docs/audit/day-4/master/design-spec.json').read_text())
    new=json.loads((dm.ROOT/'master/design-spec.json').read_text());before=dict(fm.FONTS)
    fm.emit_pdf(new['graph'],tmp_path/'new.pdf',fonts=dm.fonts(),rasters=[])
    fm.emit_pdf(old['graph'],tmp_path/'old.pdf')
    assert fm.FONTS==before
    with fitz.open(tmp_path/'new.pdf') as doc:
        assert not doc[0].get_images()
        assert any('CairoD5' in f[3] for f in doc.get_page_fonts(0))
    with fitz.open(tmp_path/'old.pdf') as doc:
        assert len(doc[0].get_images())==1
        assert any('NotoNaskhArabic' in f[3] for f in doc.get_page_fonts(0))
        assert not any('Cairo' in f[3] for f in doc.get_page_fonts(0))

def test_actual_text_bundles_ocr_controls_and_historical_missing_formats():
    from apps.pipeline.services import traced_text as tt,day5_master as dm
    report=json.loads((dm.ROOT/'text-audit/TRACED_TEXT.json').read_text())
    assert report['positive_controls_passed']
    assert all(row['detected'] for row in report['positive_controls'])
    for name,day in [('revision2','day-4'),('revision3','day-5')]:
        folder=dm.ROOT.parent/day/'master';spec=json.loads((folder/'design-spec.json').read_text())
        expected=tt.expected_lines(spec,folder/'assets')
        for artifact in ['artwork.pdf','artwork-native.ai']:assert tt.pdf_live(folder/artifact,expected)['passed']
        assert tt.svg_live(folder/'artwork.svg',spec)['passed']
        assert report['bundles'][name]['passed']
    assert not report['historical_stand_passed']

def test_hidden_or_outlined_svg_is_not_live(tmp_path):
    from apps.pipeline.services import traced_text as tt,day5_master as dm
    spec=json.loads((dm.ROOT/'master/design-spec.json').read_text())
    source=(dm.ROOT/'master/artwork.svg').read_text()
    for name,text in [('hidden',source.replace('id="SUN"','id="SUN" opacity="0"')),
                      ('outlined',source.replace('<text ','<path ').replace('</text>','</path>'))]:
        path=tmp_path/(name+'.svg');path.write_text(text)
        assert not tt.svg_live(path,spec)['passed']

def test_cairo_frozen_instance_inside_continuous_width_bar():
    from apps.pipeline.services import cairo_measured as cm,day5_master as dm
    record=json.loads((dm.ROOT/'cairo-selected/measurement.json').read_text())
    actual=cm.shape(dm.ROOT/'cairo-selected/Cairo-D5-Measured.ttf')
    assert actual['delta_width_percent']<=3 and 330<=record['chosen_weight']<=360
    assert cm.shape(cm.FONT,record['next_failing_weight_upper_bound'])['delta_width_percent']>3
    assert matte.fa.sha(dm.ROOT/'cairo-selected/Cairo-D5-Measured.ttf')==record['static_sha256']

def test_house_index_has_every_supplied_ai_and_all_page_hashes():
    root=matte.fa.ROOT/'docs/brand/house_references';record=json.loads((root/'index.json').read_text())
    files={p.name for p in (root/'files').glob('*.ai')}
    assert len(files)==73 and {r['filename'] for r in record['files']}==files
    assert not record['failed_files'] and record['rasterised_count']==73
    for row in record['files']:
        assert matte.fa.sha(root/'files'/row['filename'])==row['sha256']
        for page in row['pages']:
            assert matte.fa.sha(root/page['png'])==page['sha256']
            assert page['pixels'][0]/(page['page_mm'][0]/25.4)==pytest.approx(150,abs=.2)


def test_actual_render_copy_deltas_stay_in_declared_regions():
    from apps.pipeline.services import day5_master as dm
    root=dm.ROOT/'render/checks';base=np.array(Image.open(root/'base/front.png').convert('RGB'))
    manifest=json.loads((root/'base/scene-manifest.json').read_text())
    for name,prefix in [('header-edit','header.front'),('bottle-edit','bottle/')]:
        other=np.array(Image.open(root/name/'front.png').convert('RGB'));changed=np.any(base!=other,axis=2);mask=np.zeros(changed.shape,bool)
        for key,box in manifest['diagnostic_regions'].items():
            if key.startswith(prefix):
                x0,y0,x1,y1=box;mask[max(0,int(y0)):min(mask.shape[0],int(y1)+1),max(0,int(x0)):min(mask.shape[1],int(x1)+1)]=True
        assert changed.any() and not (changed&~mask).any()
    positive=np.array(Image.open(root/'uv-positive/front.png').convert('RGB'))
    negative=np.array(Image.open(root/'uv-mirrored-negative/front.png').convert('RGB'))
    for point in manifest['uv_samples']:
        x,y=map(round,point['pixel']);a=np.median(positive[y-2:y+3,x-2:x+3],axis=(0,1));b=np.median(negative[y-2:y+3,x-2:x+3],axis=(0,1))
        assert np.max(abs(a.astype(float)-b))>200

@pytest.mark.django_db(transaction=True)
def test_day5_review_routes_keep_failed_candidates_out_of_choices(client,settings,monkeypatch):
    from django.contrib.auth.models import User
    from django.urls import reverse
    from apps.dashboard import day5_views as views
    settings.HYBRID_BOTTLE_ENABLED=True
    url=reverse('dashboard:day5_stand')   # Day 6 moved the Day 5 stand page to its historical route
    assert client.get(url).status_code==302
    user=User.objects.create_superuser('day5-owner',password='test');client.force_login(user)
    response=client.get(url);assert response.status_code==200
    assert b'No candidate meets the release bar yet' in response.content
    assert response.context['choices']==[] and len(response.context['history'])==3
    assert b'>Approve<' not in response.content and client.post(url,{}).status_code==405
    artifact=reverse('dashboard:day5_file',args=['package'])
    response=client.get(artifact);assert response.status_code==200;response.close()
    sha=views.fm.fa.sha
    monkeypatch.setattr(views.fm.fa,'sha',lambda p:'tampered' if Path(p).name=='day5-review-package.zip' else sha(p))
    assert client.get(artifact).status_code==404
    assert client.get(reverse('dashboard:day5_file',args=['unknown'])).status_code==404

def test_invalid_encoded_critic_is_pending_never_invented():
    from apps.pipeline.services.concept_quality import evaluate
    payload=concepts.normalize_payload({'dimensions':'{"beauty":', 'hard_failures':[], 'golden_facts':'invalid'})
    assert evaluate(payload)['review_status']=='review_pending'
    assert payload['normalization_errors']==[
        'dimensions: malformed JSON; original value retained',
        'golden_facts: malformed JSON; original value retained']

@pytest.mark.parametrize('failures,expected',[(None,'review_pending'),('not a list','review_pending'),([], 'accepted')])
def test_critic_must_explicitly_return_failure_list(settings,tmp_path,failures,expected):
    from types import SimpleNamespace
    from apps.pipeline.services.concept_quality import DIMENSIONS
    settings.RESCUE_SPEND_ROOT=tmp_path/'spend'
    path=tmp_path/'image.png';Image.new('RGB',(16,16),'white').save(path)
    payload={'dimensions':{name:{'score':8,'observation':'Visible controlled layout','location':'header','repair':''} for name in DIMENSIONS},
             'observations':'Fixture response','golden_facts':{'visible_bottle_count':12,'row_counts':[4,4,4],'cap_matches':True,'countertop':True,'required_header_copy_present':True,'product_identity_matches':True}}
    if failures is not None:payload['hard_failures']=failures
    block=SimpleNamespace(type='tool_use',name='record_review',input=payload)
    response=SimpleNamespace(content=[block],model_dump=lambda **_:{'usage':{'input_tokens':10,'output_tokens':10},'content':[]})
    fake=SimpleNamespace(messages=SimpleNamespace(create=lambda **_:response))
    record=concepts.critique(path,tmp_path/'critic.json',direction_id='D1',client=fake)
    assert record['verdict']['review_status']==expected

