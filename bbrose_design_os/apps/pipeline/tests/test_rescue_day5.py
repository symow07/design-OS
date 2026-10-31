"""Day5 contracts: independent math/negative controls, roles and scoped spend."""
import json
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest
from PIL import Image
from apps.pipeline.services import two_ink_matte as matte
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


