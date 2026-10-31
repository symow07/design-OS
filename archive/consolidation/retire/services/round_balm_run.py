"""Resumable sections of the owner's Round 1; never runs at import."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

from PIL import Image, ImageDraw

from .round_balm_calls import OUT, REPO, write, sha, append
from . import rank_round, whole_object_check, round_balm_page


def commit(message,paths):
    subprocess.run(['git','add',*[str(p) for p in paths]],cwd=REPO,check=True)
    dirty=subprocess.run(['git','diff','--cached','--quiet'],cwd=REPO)
    if dirty.returncode:
        subprocess.run(['git','commit','-m',message],cwd=REPO,check=True)


def inspect_sketches():
    seeds=json.loads((OUT/'seeds.json').read_text())['seeds']
    results={};eligible={}
    for i,seed in enumerate(seeds,1):
        key=seed['id'];dest=OUT/'sketches'/key
        from .round_balm_sheet import raw_geometry
        raw_geometry(dest)
        checked=whole_object_check.check(dest)
        results[key]=checked
        if checked['eligible']:
            whole_object_check.read_blind(dest)
            eligible[key]={'directory':str(dest)}
        print('INSPECTED',key,'eligible' if checked['eligible'] else 'disqualified',flush=True)
        if i%5==0:
            commit(f'Round 1 section 4: inspect and read sketches {i-4}–{i}',[OUT/'sketches',OUT/'calls.jsonl'])
    write(OUT/'eligibility.json',{'eligible':list(eligible),'results':results})
    return eligible


def eligible_sketches():
    rec=json.loads((OUT/'eligibility.json').read_text())
    return {k:{'directory':str(OUT/'sketches'/k)} for k in rec['eligible']}


def cut():
    candidates=eligible_sketches()
    if len(candidates)<8:raise ValueError(f'Only {len(candidates)} eligible objects; eight cannot be fabricated')
    coarse=rank_round.coarse(candidates)
    commit('Round 1 section 4: coarse ordinal jury round',[OUT/'jury/coarse',OUT/'calls.jsonl',OUT/'eligibility.json'])
    subset={k:candidates[k] for k in coarse['shortlist']}
    fine=rank_round.fine(subset,'shortlist',{k:coarse['rank_sum'][k] for k in subset})
    order=fine['order'][:8]
    rank_round.calibration(coarse=coarse,shortlist_pairwise=fine,cut_to_eight=order)
    write(OUT/'cut.json',{'order':order})
    commit('Round 1 section 4: whole-object cut and pairwise eight',[OUT/'jury',OUT/'calls.jsonl',
            OUT/'critic-calibration.json',OUT/'cut.json',OUT/'eligibility.json'])
    round_balm_page.publish('marks',order)
    commit('Round 1 section 5: publish the eight for owner marks',[OUT/'publication.json'])
    return order


def notice():
    """Call only when the owner has actually been told the eight-page exists."""
    path=OUT/'marks-checkpoint.json'
    if path.exists():return json.loads(path.read_text())
    now=datetime.now(ZoneInfo('Asia/Shanghai'))
    rec={'notice_at':now.isoformat(),'poll_at':[(now+timedelta(minutes=n)).isoformat() for n in (20,40,60)],
         'fallback_after':(now+timedelta(minutes=60)).isoformat(),'marks_path':'docs/rounds/r1-balm/MARKS',
         'state':'awaiting owner marks'}
    write(path,rec);return rec


def record_marks(rows,source):
    order=json.loads((OUT/'cut.json').read_text())['order']
    if not isinstance(rows,list) or not 1<=len(rows)<=3:raise ValueError('One to three owner marks')
    ids=[r['id'] for r in rows]
    if len(set(ids))!=len(ids) or any(k not in order for k in ids):raise ValueError('Marks must name distinct displayed sketches')
    if any(not isinstance(r.get('preserve'),str) or not r['preserve'].strip() for r in rows):raise ValueError('Each mark needs the line to preserve')
    rec={'marks':rows,'source':source,'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    if (OUT/'marks.json').exists():
        previous=json.loads((OUT/'marks.json').read_text())
        if previous['marks']==rows and previous['source']==source:return previous
        append(OUT/'marks-history.jsonl',previous)
    write(OUT/'marks.json',rec)
    rank_round.calibration(marks=rec)
    return rec


def check_marks():
    if (OUT/'marks.json').exists():return json.loads((OUT/'marks.json').read_text())
    path=OUT/'MARKS'
    if not path.exists():return None
    text=path.read_text().strip()
    try:
        parsed=json.loads(text)
        rows=parsed['marks'] if isinstance(parsed,dict) else parsed
    except ValueError:
        rows=[]
        for line in text.splitlines():
            key,sep,reason=line.partition('|')
            if not sep:key,sep,reason=line.partition(':')
            if not sep:raise ValueError('MARKS: one ID | preservation line per line, or JSON')
            rows.append({'id':key.strip(),'preserve':reason.strip()})
    return record_marks(rows,{'kind':'owner MARKS file','sha256':sha(path)})


def fallback_due(now=None):
    rec=json.loads((OUT/'marks-checkpoint.json').read_text())
    now=now or datetime.now(ZoneInfo('Asia/Shanghai'))
    return now>=datetime.fromisoformat(rec['fallback_after'])


def poll_marks():
    marks=check_marks()
    event={'checked_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
           'marks_found':marks is not None,'fallback_due':fallback_due()}
    append(OUT/'marks-polls.jsonl',event)
    return marks,event


def fallback_marks(rows):
    """The owner authorized this departure only after sixty real minutes."""
    marks,event=poll_marks()
    if marks is not None:return marks
    if not event['fallback_due']:raise ValueError('Owner marking window is still open')
    top=json.loads((OUT/'cut.json').read_text())['order'][:3]
    if [r['id'] for r in rows]!=top:raise ValueError('Timeout must use the jury top three')
    source={'kind':'jury timeout fallback','notice':json.loads((OUT/'marks-checkpoint.json').read_text()),
            'preservation_lines':'Agent names visible fragments; these are not owner marks.'}
    result=record_marks(rows,source)
    calibration=rank_round.calibration()
    calibration['departures'].append({'kind':'owner-marks-timeout','recorded_at':result['recorded_at'],
        'reason':'No marks received by sixty minutes after the page notice; owner D-R1-5 fallback.',
        'selected':top,'preservation_source':'agent visual inspection'})
    rank_round.calibration(departures=calibration['departures'])
    return result


def record_pick(key,reason,source,merge=None):
    page=round_balm_page.load()
    if page['state']!='pick' or key not in page['order']:raise ValueError('Pick must name one final-six candidate')
    if not isinstance(reason,str) or not reason.strip():raise ValueError('Pick needs the owner’s short reason')
    if merge is not None:
        if not isinstance(merge,dict) or set(merge)!={'candidate','element'} or merge['candidate']==key or merge['candidate'] not in page['all_candidates'] or not isinstance(merge['element'],str) or not merge['element'].strip():
            raise ValueError('One merge names another candidate and one element for day two')
    result={'id':key,'reason':reason,'source':source,'merge':merge,
            'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    calibration=rank_round.calibration()
    calibration['picks'].append(result)
    rank_round.calibration(picks=calibration['picks'],pick_status='recorded')
    write(OUT/'pick.json',result)
    round_balm_page.publish('pick',page['order'])
    return result


def check_pick():
    path=OUT/'PICK'
    if not path.exists():return None
    source={'kind':'owner PICK file','sha256':sha(path)}
    if (OUT/'pick.json').exists():
        existing=json.loads((OUT/'pick.json').read_text())
        if existing['source']==source:return existing
    text=path.read_text().strip()
    if text.startswith('{'):
        row=json.loads(text)
        return record_pick(row['id'],row['reason'],source,row.get('merge'))
    key,sep,reason=text.partition('|')
    if not sep:key,sep,reason=text.partition(':')
    if not sep:raise ValueError('PICK: ID | reason, or JSON with id, reason and optional merge')
    return record_pick(key.strip(),reason.strip(),source)


def prepare_developments(sketch,polygons,intents):
    """Author prepares explicit pixel polygons and two incompatible intents before edits."""
    mark_record=json.loads((OUT/'marks.json').read_text())
    marks=mark_record['marks']
    mark=next((r for r in marks if r['id']==sketch),None)
    if mark is None:raise ValueError('Only marked sketches may be developed')
    if set(intents)!={'A','B'} or intents['A']==intents['B']:raise ValueError('Two distinct fork intents required')
    if not polygons or any(len(poly)<3 for poly in polygons):raise ValueError('Explicit fragment polygons required')
    base=Image.open(OUT/'sheet-mask.png').convert('RGBA')
    d=ImageDraw.Draw(base)
    for polygon in polygons:
        if any(not (0<=x<1536 and 0<=y<1024) for x,y in polygon):raise ValueError('Fragment outside sheet')
        d.polygon([tuple(p) for p in polygon],fill=(255,255,255,255))
    original_mask=np.asarray(Image.open(OUT/'sheet-mask.png').convert('RGBA'))[...,3]
    fragment_pixels=(original_mask==0)&(np.asarray(base)[...,3]!=0)
    if not np.any(fragment_pixels):raise ValueError('Polygons protect no editable artwork pixels')
    parent_pixels=np.asarray(Image.open(OUT/'sketches'/sketch/'picture.png').convert('RGBA'))
    folder=OUT/'developments'/sketch;folder.mkdir(parents=True,exist_ok=True)
    base.save(folder/'fragment-mask.png')
    write(folder/'fragment.json',{'parent':sketch,'parent_sha256':sha(OUT/'sketches'/sketch/'picture.png'),
          'preservation_line':mark['preserve'],'mark_source':mark_record['source'],
          'polygons_px':polygons,'mask_sha256':sha(folder/'fragment-mask.png'),
          'fragment_pixels':int(fragment_pixels.sum()),
          'fragment_rgba_sha256':hashlib.sha256(parent_pixels[fragment_pixels].tobytes()).hexdigest(),
          'intents':intents,'prepared_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()})
    for fork,intent in intents.items():
        dest=folder/fork;dest.mkdir(parents=True,exist_ok=True);(dest/'intent.txt').write_text(intent+'\n')
    commit('Round 1 section 6: protect '+sketch+' and preregister incompatible forks',[folder,OUT/'marks.json',OUT/'critic-calibration.json'])


def develop(sketch):
    from .round_balm_images import edit,FORMAT,COPY,BANNED,DONT
    parent=OUT/'sketches'/sketch
    reading=json.loads((parent/'blind.json').read_text())['idea_in_ten_words']
    folder=OUT/'developments'/sketch
    fragment=json.loads((folder/'fragment.json').read_text())
    if sha(parent/'picture.png')!=fragment['parent_sha256']:raise ValueError('Parent changed')
    if sha(folder/'fragment-mask.png')!=fragment['mask_sha256']:raise ValueError('Preregistered mask changed')
    base=np.asarray(Image.open(OUT/'sheet-mask.png').convert('RGBA'))[...,3]
    mask=np.asarray(Image.open(folder/'fragment-mask.png').convert('RGBA'))[...,3]
    fragment_pixels=(base==0)&(mask!=0)
    for fork in ('A','B'):
        intent=fragment['intents'][fork]
        words=FORMAT.replace('transparent panel windows of image 1','unprotected panel windows of image 1 (the parent); image 3 is the fixed engine sheet')
        words+='\nBlind reading: '+reading+'\nIntent: '+intent+'\n'+COPY+'\n'+BANNED+'\n'+DONT
        edit(sketch+'/'+fork,words,parent=parent/'picture.png',mask=folder/'fragment-mask.png')
        pixels=np.asarray(Image.open(folder/fork/'picture.png').convert('RGBA'))[fragment_pixels]
        digest=hashlib.sha256(pixels.tobytes()).hexdigest()
        if digest!=fragment['fragment_rgba_sha256']:raise ValueError('Owner fragment pixels changed')
        write(folder/fork/'fragment-proof.json',{'byte_identical':True,'pixels':int(fragment_pixels.sum()),
            'parent_and_fork_rgba_sha256':digest,'mask_sha256':fragment['mask_sha256']})
        from .round_balm_sheet import raw_geometry
        raw_geometry(folder/fork)
        result=whole_object_check.check(folder/fork)
        whole_object_check.read_blind(folder/fork)
        print('DEVELOPED',sketch+'/'+fork,result['eligible'],flush=True)
    commit('Round 1 section 6: '+sketch+' forks and protected-pixel proofs',[folder,OUT/'image-calls.jsonl',OUT/'calls.jsonl'])


def final_order():
    marks=json.loads((OUT/'marks.json').read_text())['marks']
    candidates={};rank_sum={}
    coarse=json.loads((OUT/'jury/coarse/result.json').read_text())
    for mark in marks:
        key=mark['id'];candidates[key]={'directory':str(OUT/'sketches'/key)}
        rank_sum[key]=coarse['rank_sum'][key]
        for fork in ('A','B'):
            dest=OUT/'developments'/key/fork
            if json.loads((dest/'whole-object.json').read_text())['eligible']:
                candidates[key+'/'+fork]={'directory':str(dest)}
                rank_sum[key+'/'+fork]=coarse['rank_sum'][key]
    if len(candidates)<6:raise ValueError('Fewer than six complete eligible candidates; do not fabricate a final six')
    result=rank_round.fine(candidates,'final',None)
    result['rank_sum_basis']='Sum of competition ranks from each juror’s pairwise win counts; tied win counts share a rank. No coarse rank is inherited by a fork.'
    rank_round.calibration(final_pairwise=result,final_six=result['order'][:6],pick_status='pending')
    write(OUT/'final-order.json',result)
    round_balm_page.publish('pick',result['order'][:6])
    commit('Round 1 section 7: final pairwise order and six-object pick page',[OUT/'jury',OUT/'calls.jsonl',
             OUT/'critic-calibration.json',OUT/'final-order.json',OUT/'publication.json'])
    return result
