"""Round 1 evidence audit: permitted inputs, preserved pixels, usage and pair coverage."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from . import round_calls as image_guard, spend_reservation, rank_round, round_balm_page
from .round_balm_calls import OUT, REPO, PREFIX, sha, write


def run(out=OUT):
    out=Path(out);errors=[];warnings=[]
    sheet=json.loads((out/'sheet.json').read_text())
    pins={str((out/name).resolve()):digest for name,digest in sheet['sha256'].items()}
    logo,logo_sha=image_guard.APPROVED_LOGO;pins[str(logo.resolve())]=logo_sha
    log=out/'image-calls.jsonl'
    calls=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    if len(calls)>26:errors.append('More than 26 image edits')
    ids=[r['reservation_id'] for r in calls]
    if len(ids)!=len(set(ids)):errors.append('Duplicate image reservation in log')
    base=np.array(Image.open(out/'sheet-mask.png').convert('RGBA'))[...,3]
    for row in calls:
        key=row['key'];allowed=dict(pins)
        if '/' in key:
            parent=out/'sketches'/key.split('/')[0]/'picture.png'
            allowed[str(parent.resolve())]=sha(parent)
        if row['model']!='gpt-image-2' or row['quality']!='high' or row['size']!='1536x1024':errors.append(key+': wrong image configuration')
        if hashlib.sha256(row['prompt'].encode()).hexdigest()!=row['prompt_sha256']:errors.append(key+': prompt digest mismatch')
        if image_guard.competitor_in(row['prompt']):errors.append(key+': competitor prompt')
        for item in row['inputs']:
            path=(REPO/item['path']).resolve()
            if str(path) not in allowed or allowed[str(path)]!=item['sha256'] or sha(path)!=item['sha256']:
                errors.append(key+': forbidden or changed input '+item['path'])
        mask_path=(REPO/row['mask']['path']).resolve()
        if not mask_path.is_relative_to(out.resolve()) or sha(mask_path)!=row['mask']['sha256']:
            errors.append(key+': mask outside round or changed')
            continue
        mask=np.array(Image.open(mask_path).convert('RGBA'))[...,3]
        if np.any((mask==0)&(base!=0)):errors.append(key+': mask exposes construction')
        destination=out/('developments' if '/' in key else 'sketches')/key
        source=(REPO/row['inputs'][0]['path']).resolve()
        before=np.array(Image.open(source).convert('RGBA'));after=np.array(Image.open(destination/'picture.png').convert('RGBA'))
        if not np.array_equal(before[mask!=0],after[mask!=0]):errors.append(key+': protected pixels changed')
        if sha(destination/'picture.png')!=row['output_sha256']:errors.append(key+': output digest mismatch')
    with spend_reservation._connect() as db:
        paid=[dict(r) for r in db.execute('SELECT id,operation,model,reserved,accounted,state,usage FROM calls WHERE substr(operation,1,?)=?',(len(PREFIX),PREFIX))]
    total=sum(r['accounted'] for r in paid)/1e6
    if total>20:errors.append('Round spend exceeds $20')
    image_paid=[r for r in paid if r['operation'].startswith(PREFIX+'image/')]
    if len(image_paid)>26:errors.append('Ledger exceeds 26 image attempts')
    if {r['id'] for r in image_paid}!=set(ids):errors.append('Image log and paid ledger do not cover identical attempts')
    unresolved=[r['id'] for r in paid if r['state'] in ('reserved','billing_unresolved')]
    if unresolved:warnings.append('Unresolved billing held at reservation for '+','.join(unresolved))
    stages={}
    for stage in ('shortlist','final'):
        path=out/'jury'/stage/'result.json'
        if not path.exists():continue
        result=json.loads(path.read_text());ids_=result['order']
        expected=[p for batch in rank_round.pair_batches(ids_) for p in batch]
        for juror in ('J1','J2'):
            try:rank_round.validate_pairs(result['pairs'][juror],expected)
            except ValueError as exc:errors.append(stage+' '+juror+': '+str(exc))
        if any(len(batch)>9 for batch in result['batches']):errors.append(stage+': over nine pairs in a batch')
        stages[stage]={'candidates':len(ids_),'pairs_each_juror':len(expected),'batches_each_juror':len(result['batches'])}
    if (out/'publication.json').exists():
        publication=round_balm_page.load(out)
        for role in publication['files']:
            try:round_balm_page.checked_bytes(role,out)
            except (ValueError,KeyError,OSError):errors.append('Published artifact changed: '+role)
    result={'schema':'r1_audit/1','passes':not errors,'errors':errors,'warnings':warnings,
            'image_edits':len(calls),'sketches':sum('/' not in r['key'] for r in calls),
            'developments':sum('/' in r['key'] for r in calls),'accounted_usd':total,
            'usage_priced_usd':sum(r['accounted'] for r in paid if r['state']=='usage_recorded')/1e6,
            'unresolved':unresolved,'paid_call_count':len(paid),'pairwise':stages,
            'billing':'usage-priced estimates using configured tariffs; unknown billing retains its hold',
            'sheet_defects':'defects.json remains separate; audit pass does not certify the sketch sheet as production artwork'}
    write(out/'audit.json',result)
    write(out/'spend.json',{'totals':{k:result[k] for k in ('accounted_usd','usage_priced_usd','unresolved','paid_call_count')},
            'calls':[dict(r,usage=json.loads(r['usage']) if r['usage'] else None) for r in paid]})
    return result
