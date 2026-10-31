"""Round-only publication. Every served artifact is contained and hash-checked."""
import hashlib
import json
from pathlib import Path

from .round_balm_calls import OUT, write, sha
from .round_balm_sheet import PANEL_IDS


def publish(state,order,*,out=OUT):
    required={'marks':8,'pick':6}
    if state not in required or len(order)!=required[state] or len(set(order))!=len(order):
        raise ValueError('Publication needs eight distinct marks candidates or six distinct picks')
    out=Path(out);files={};cards=[];history=[]
    contract=json.loads((out/'sheet.json').read_text())
    def add(path):
        path=Path(path).resolve()
        if not path.is_relative_to(out.resolve()):raise ValueError('Outside round')
        role=str(path.relative_to(out.resolve())).replace('/','--').replace('.','-')
        files[role]={'path':str(path.relative_to(out.resolve())),'sha256':sha(path)}
        return role
    def card(key,dest):
        check_path=dest/'whole-object.json';blind_path=dest/'blind.json'
        check=json.loads(check_path.read_text()) if check_path.exists() else {'eligible':False,'reasons':['Inspection pending']}
        reading=json.loads(blind_path.read_text()) if blind_path.exists() else {}
        result={'id':key,'sheet':add(dest/'picture.png'),'drawing':add(dest/'drawing.png'),
                'reading':reading,'inspection':check,'panels':[], 'parent':key.split('/')[0] if '/' in key else None,
                'intent':(dest/'intent.txt').read_text() if (dest/'intent.txt').exists() else ''}
        for panel in PANEL_IDS:
            p=contract['panels'][panel]
            result['panels'].append({'name':panel,'role':add(dest/(panel+'.png')),'mm':p['mm']})
        return result
    candidates={}
    for dest in sorted((out/'sketches').iterdir()):
        if dest.is_dir() and (dest/'drawing.png').exists():candidates[dest.name]=card(dest.name,dest)
    if (out/'developments').exists():
        for dest in sorted((out/'developments').glob('*/*')):
            if (dest/'drawing.png').exists():
                key='/'.join(dest.parts[-2:]);candidates[key]=card(key,dest)
    for key,result in candidates.items():
        family=key.split('/')[0]
        result['family']=[k for k in candidates if k.split('/')[0]==family and k!=key]
        result['selected']=key in order
    for key in order:
        if key not in candidates or not candidates[key]['inspection']['eligible']:
            raise ValueError('Only checked eligible candidates enter selection')
        cards.append(candidates[key])
    history=list(candidates.values())
    records=[]
    for path in sorted((out/'jury').rglob('*.json')):
        if not any(x in path.name for x in ('.request.','.response.')):
            records.append({'name':str(path.relative_to(out/'jury')),'role':add(path)})
    jury=[]
    for stage in ('coarse','shortlist','final'):
        path=out/'jury'/stage/'result.json'
        if not path.exists():continue
        result=json.loads(path.read_text());judges=[]
        for juror in ('J1','J2'):
            if stage=='coarse':
                judges.append({'name':juror,'order':result['jurors'][juror],
                    'pairs':[],'appeal':[result['appeal'][juror]]})
            else:
                judges.append({'name':juror,'order':result['juror_orders'][juror],
                    'pairs':result['pairs'][juror],'appeal':result['appeal'][juror]})
        jury.append({'stage':stage,'judges':judges})
    record={'schema':'r1_balm_publication/1','state':state,'order':order,'cards':cards,'history':history,'jury':jury,
            'files':files,'records':records,'all_candidates':list(candidates),
            'defects':json.loads((out/'defects.json').read_text()) if (out/'defects.json').exists() else [],
            'calibration':json.loads((out/'critic-calibration.json').read_text()) if (out/'critic-calibration.json').exists() else {}}
    write(out/'publication.json',record)
    return record


def load(out=OUT):
    out=Path(out)
    if not (out/'publication.json').exists():return {'state':'preparing','cards':[],'history':[]}
    record=json.loads((out/'publication.json').read_text())
    if record.get('schema')!='r1_balm_publication/1':raise ValueError('Unknown publication')
    return record


def checked_bytes(role,out=OUT):
    out=Path(out).resolve();record=load(out)
    row=record['files'][role];path=(out/row['path']).resolve()
    if not path.is_relative_to(out) or path.suffix not in {'.png','.json'}:raise ValueError('Outside round')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Published bytes changed')
    return data,'image/png' if path.suffix=='.png' else 'application/json'
