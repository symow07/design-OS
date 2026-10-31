"""Role-bound display concept requests; exact product/geometry, house style only.

The existing rescue reservation journal remains the sole paid boundary. Saved
responses are immutable; retries are separate explicit calls, never SDK retries.
"""
from pathlib import Path
from contextlib import ExitStack
import hashlib
import json
import shutil
import re
from django.conf import settings
from .spend_reservation import paid_operation

BUDGET_PREFIX='day5-continued/'
BUDGET_CAP=20
ROLES={'product, exact','geometry, exact','geometry drawing, exact','house, style','edit target, exact','repair target, appearance'}

def normalize_payload(payload):
    """Decode JSON-encoded tool fields without supplying any missing judgment."""
    if not isinstance(payload,dict):return {}
    payload=dict(payload);errors=[]
    for key in ('dimensions','hard_failures','golden_facts'):
        if isinstance(payload.get(key),str):
            try:payload[key]=json.loads(payload[key])
            except ValueError:
                errors.append(f'{key}: malformed JSON; original value retained')
    if errors:payload['normalization_errors']=errors
    return payload


def reference(path,role,source_id):
    path=Path(path).resolve()
    if role not in ROLES:raise ValueError('Unknown image reference role.')
    return {'path':str(path),'role':role,'source_id':source_id,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def request(prompt,references,*,display=True):
    if display:
        roles=[r['role'] for r in references]
        if roles.count('product, exact')!=1 or roles.count('geometry, exact')!=1 or roles.count('house, style')!=3:
            raise ValueError('Display concepts require one exact product, one exact geometry and three house style references.')
        if {r['source_id'] for r in references if r['role']=='house, style'}!={'house-069','house-043','house-048'}:
            raise ValueError('The owner-pinned house shortlist changed.')
    lines=['INPUT ROLES: exact inputs govern the object; house/style inputs supply principles only.']
    for i,r in enumerate(references,1):
        if r['role'] not in ROLES or hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError('Image reference changed or has an invalid role.')
        note=('Preserve its object, shape, layout and count exactly.' if 'exact' in r['role'] else 'Preserve this visual direction; replace its incorrect count/structure from the exact geometry inputs.' if r['role']=='repair target, appearance' else 'Use consumer-artwork style principles only; ignore shipping cartons and do not copy its product or wording.')
        lines.append(f"Image {i}: {r['role']} — {r['source_id']}. "+note)
    if display:
        from apps.pipeline.targets.artwork import DisplayStandTarget
        prompt=DisplayStandTarget.concept_directive+'\n\n'+prompt
    return '\n'.join(lines)+'\n\n'+prompt


def generate(prompt,references,destination,*,purpose,display=True,client=None):
    if display and not re.fullmatch(r'D[123]/(?:attempt-[123]|hero)',purpose):
        raise ValueError('A display attempt needs its fixed direction and bounded attempt identity.')
    if not display and purpose!='swoosh-isolation':raise ValueError('Only the one authorized isolation uses this non-display route.')
    destination=Path(destination)
    if destination.exists():raise ValueError('Each paid attempt needs a new immutable directory.')
    final=request(prompt,references,display=display)
    destination.mkdir(parents=True)
    identity={'model':'gpt-image-2','size':'1024x1536','quality':'high','n':1,'purpose':purpose,'references':references,'full_prompt':final,'status':'request_prepared','reserved_max_accounted_usd':2,'budget_prefix':BUDGET_PREFIX,'budget_cap_usd':BUDGET_CAP}
    (destination/'request.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
    if client is None:
        from openai import OpenAI
        client=OpenAI(api_key=settings.OPENAI_API_KEY,max_retries=0,timeout=240)
    elif hasattr(client,'with_options'):
        client=client.with_options(max_retries=0,timeout=240)
    with ExitStack() as stack:
        # Validate bytes immediately before opening and reserving, including the exact roles.
        request(prompt,references,display=display)
        files=[stack.enter_context(Path(r['path']).open('rb')) for r in references]
        operation=BUDGET_PREFIX+('stand/' if display else '')+purpose
        response=paid_operation(client.images.edit,provider='openai',operation=operation,
            reservation_prefix=BUDGET_PREFIX,reservation_cap=BUDGET_CAP,estimate_override=2,
            count_prefix=BUDGET_PREFIX+('stand/' if display else 'swoosh-isolation'),count_cap=6 if display else 1,
            attempt_limits=[(BUDGET_PREFIX+'stand/'+purpose.split('/')[0]+'/',3)] if display else [],
            model='gpt-image-2',image=files,prompt=final,n=1,size='1024x1536',quality='high')
    saved=getattr(response,'_rescue_paid_images',[])
    if len(saved)!=1:raise ValueError('Paid response retained but exactly one image was not recovered.')
    shutil.copyfile(saved[0],destination/'image.png')
    identity.update(status='response_persisted',reservation_id=getattr(response,'_rescue_reservation_id',None),
                    response_artifact=getattr(response,'_rescue_response_artifact',None),
                    usage=response.model_dump(mode='json').get('usage'),output_sha256=hashlib.sha256((destination/'image.png').read_bytes()).hexdigest(),
                    invoice_usd=None,accounting='Reservation retained pending tariff/invoice reconciliation; actual provider usage retained.')
    (destination/'result.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
    return identity

def critique(image_path,destination,*,direction_id,client=None):
    """Independent actual-image critique; code, not the critic, decides acceptance."""
    import base64
    from .concept_quality import DIMENSIONS,evaluate
    path=Path(image_path);destination=Path(destination)
    if destination.exists():raise ValueError('Critic observations are immutable per attempt.')
    prompt='''Judge the attached assembled countertop display itself. Return JSON only with dimensions,hard_failures,observations,golden_facts. For each dimension provide score1..10, observation, location, and repair (nonempty if score<8). Dimensions: '''+', '.join(DIMENSIONS)+'''. Required facts: exactly12 bottles,3stepped rows of4, identical clear-glass amber-filled Sun Repair bottles with chrome spray caps; assembled countertop display, not booth/floor. Header must contain BBROSE,SUN REPAIR,SERUM,Arabic and Revive+Smooth; concept lettering may be approximate but cannot be absent. Geometry reference requirement180x150x322mm, seats6/60/114 and100mmheader. Do not claim millimetre verification from an image. Count visible bottles explicitly row-by-row in golden_facts (top/middle/front), note missing rows. If count/rows/cap/productform/target/requiredheadercopy fails, add a specific hard_failure. Assess creative merit independently: professional hierarchy, legibility, quiet space, material depth, ownable coherent design. Do not reward a persuasive brief; inspect pixels. golden_facts must include visible_bottle_count, row_counts, cap_matches, countertop, required_header_copy_present, product_identity_matches. No automatic pass field.'''
    if client is None:
        import anthropic
        client=anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY,max_retries=0,timeout=120)
    elif hasattr(client,'with_options'):client=client.with_options(max_retries=0,timeout=120)
    content=[{'type':'image','source':{'type':'base64','media_type':'image/png','data':base64.b64encode(path.read_bytes()).decode()}},{'type':'text','text':prompt}]
    dimension={'type':'object','properties':{'score':{'type':'number','minimum':1,'maximum':10},**{k:{'type':'string'} for k in ['observation','location','repair']}},'required':['score','observation','location','repair']}
    schema={'type':'object','properties':{'dimensions':{'type':'object','properties':{k:dimension for k in DIMENSIONS},'required':list(DIMENSIONS)},'hard_failures':{'type':'array','items':{'type':'string'}},'observations':{'type':'string'},'golden_facts':{'type':'object','properties':{'visible_bottle_count':{'type':'integer'},'row_counts':{'type':'array','items':{'type':'integer'},'minItems':3,'maxItems':3},**{k:{'type':'boolean'} for k in ['cap_matches','countertop','required_header_copy_present','product_identity_matches']}},'required':['visible_bottle_count','row_counts','cap_matches','countertop','required_header_copy_present','product_identity_matches']}},'required':['dimensions','hard_failures','observations','golden_facts']}
    content[-1]['text']+=' Use the record_review tool with the exact typed schema. Do not invent regulations. Hard failures are observable brief violations; density/legibility judgments belong in the scored dimensions unless required copy is absent. The exact12positions are fixed; assess the designed header and material hierarchy, not an imagined lower stock count.'
    response=paid_operation(client.messages.create,provider='anthropic',operation=BUDGET_PREFIX+'critic/'+direction_id,
        reservation_prefix=BUDGET_PREFIX,reservation_cap=BUDGET_CAP,model=settings.CLAUDE_MODEL_FAST,max_tokens=3000,messages=[{'role':'user','content':content}],tools=[{'name':'record_review','description':'Record independent image observations and literal counts.','input_schema':schema}],tool_choice={'type':'tool','name':'record_review'})
    raw='\n'.join(b.text for b in response.content if getattr(b,'type','')=='text');clean=raw.strip()
    if clean.startswith('```'):clean=clean.split('\n',1)[1].rsplit('```',1)[0]
    structured=next((b.input for b in response.content if getattr(b,'type','')=='tool_use' and getattr(b,'name','')=='record_review'),None)
    try:payload=structured if isinstance(structured,dict) else json.loads(clean)
    except ValueError:payload={}
    payload=normalize_payload(payload)
    facts=payload.get('golden_facts',{});hard=payload.get('hard_failures')
    if not isinstance(facts,dict):facts={}
    if isinstance(hard,list):
        for good,reason in [(facts.get('visible_bottle_count')==12,'Visible bottle count must be12'),(facts.get('row_counts')==[4,4,4],'Three rows of four required'),(facts.get('cap_matches') is True,'Chrome spray cap unresolved or changed'),(facts.get('countertop') is True,'Countertop target unresolved or changed'),(facts.get('required_header_copy_present') is True,'Required header copy unresolved or missing'),(facts.get('product_identity_matches') is True,'Product identity unresolved or changed')]:
            if not good:hard.append(reason)
    verdict=evaluate(payload);record={'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'direction_id':direction_id,'payload':payload,'verdict':verdict,'raw_response':raw,'reservation_id':getattr(response,'_rescue_reservation_id',None),'usage':response.model_dump(mode='json').get('usage'),'golden_checks_are_visual':'Image counts/copy need human confirmation; exact mm geometry remains deterministic scene authority.'}
    destination.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record

def normalize_saved_review(path):
    """Lossless shape normalization of saved observations, never score repair."""
    from .concept_quality import evaluate
    path=Path(path);record=json.loads(path.read_text());raw=record['raw_response'].strip()
    if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0]
    payload=json.loads(raw);facts=payload['golden_facts'];normalized={}
    unwrap=lambda v:v.get('value') if isinstance(v,dict) else v
    for key in ['visible_bottle_count','cap_matches','countertop','product_identity_matches']:normalized[key]=unwrap(facts.get(key))
    rows=facts.get('row_counts')
    if isinstance(rows,list):normalized['row_counts']=rows
    elif isinstance(rows,dict) and all(k in rows for k in ['top_rear_row','middle_row','front_row']):normalized['row_counts']=[rows[k] for k in ['top_rear_row','middle_row','front_row']]
    elif isinstance(facts.get('visible_bottle_count'),dict) and all(k in facts['visible_bottle_count'] for k in ['top_row','middle_row','front_row']):normalized['row_counts']=[facts['visible_bottle_count'][k] for k in ['top_row','middle_row','front_row']]
    else:normalized['row_counts']=None
    copy=facts.get('required_header_copy_present')
    normalized['required_header_copy_present']=all(copy.get(k) is True for k in ['BBROSE','SUN_REPAIR','SERUM','Arabic','Revive_plus_Smooth']) if isinstance(copy,dict) else copy
    payload['hard_failures']=[x if isinstance(x,str) else str(x.get('finding') or x.get('description') or json.dumps(x)) for x in payload['hard_failures']]
    payload['golden_facts']=normalized
    if normalized.get('visible_bottle_count')!=12:payload['hard_failures'].append('Visible count is not12.')
    if normalized.get('row_counts')!=[4,4,4]:payload['hard_failures'].append('Three rows of four not confirmed.')
    for key in ['cap_matches','countertop','required_header_copy_present','product_identity_matches']:
        if normalized.get(key) is not True:payload['hard_failures'].append(key+' not confirmed.')
    record.update(payload=payload,verdict=evaluate(payload),normalization='Saved raw response retained. Structured factual values/row counts and hard-failure descriptions normalized; no scores or observations changed. Unsupported regulatory commentary is not adopted as a factual production rule.')
    original=path.with_name('critic-before-normalization.json')
    if not original.exists():original.write_bytes(path.read_bytes())
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record
