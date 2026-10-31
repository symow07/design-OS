"""Round 1 ordinal jury. No score rubric, thresholds, caps or anchors."""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path

from .round_balm_calls import OUT, REPO, text_call, write, sha

QUESTION = 'At equal execution quality, which idea is more distinctive, and what beyond its front proves it?'
ROLES = {
    'J1':'You are the creative director of a global prestige beauty house, reading complete lip-balm objects.',
    'J2':'You are the senior packaging designer of a global prestige beauty house, reading complete lip-balm objects.'}
APPEAL = ('Separately, for each candidate answer: would a woman 18–30 in Amman, Beirut, Damascus, '
          'Ramallah or Tunis buy it for the object and photograph it? This answer NEVER decides the order.')


def validate_rank(order, ids):
    if not isinstance(order,list) or not isinstance(ids,list) or any(not isinstance(k,str) for k in ids+order):
        raise ValueError('Rank and IDs must be lists of strings')
    if len(ids)!=len(set(ids)) or len(order)!=len(ids) or set(order)!=set(ids):
        raise ValueError('A rank must contain every candidate exactly once')
    return order


def coarse_cut(j1,j2,keep=10):
    validate_rank(j1,j1)
    validate_rank(j2,j1)
    p1={k:i+1 for i,k in enumerate(j1)};p2={k:i+1 for i,k in enumerate(j2)}
    sums={k:p1[k]+p2[k] for k in j1}
    spread={k:abs(p1[k]-p2[k]) for k in j1}
    order=sorted(j1,key=lambda k:(sums[k],p1[k],k))
    disputed=sorted((k for k in j1 if spread[k]>0),key=lambda k:(-spread[k],sums[k],p1[k],k))[:2]
    reserved=disputed if len(j1)>keep else []
    chosen=[k for k in order if k not in reserved][:max(0,keep-len(reserved))]+reserved
    chosen=sorted(chosen,key=lambda k:(sums[k],p1[k],k))
    return {'order':order,'shortlist':chosen,'rank_sum':sums,'spread':spread,'reserved':reserved,
            'rule':'reserve up to two greatest nonzero absolute rank disagreements; fill remaining slots by rank sum; ties J1 then ID'}


def pair_batches(ids,size=9):
    if not 1<=size<=9:raise ValueError('At most nine pairs per call')
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate candidate ID')
    remaining=list(combinations(ids,2));batches=[]
    # Cluster pairs sharing candidates to send fewer full-size images, once each.
    while remaining:
        batch=[remaining.pop(0)];shown=set(batch[0])
        while remaining and len(batch)<size:
            i=min(range(len(remaining)),key=lambda i:(len(set(remaining[i])-shown),i))
            pair=remaining.pop(i);batch.append(pair);shown.update(pair)
        batches.append(batch)
    return batches


def validate_pairs(rows,expected):
    if not isinstance(rows,list):raise ValueError('Pairs must be a list')
    expected={frozenset(p) for p in expected};seen=set()
    for r in rows:
        pair=r.get('pair',[]);key=frozenset(pair)
        if len(pair)!=2 or len(key)!=2 or key not in expected or key in seen:
            raise ValueError('Missing, duplicate, unexpected or self pair')
        if r.get('winner') not in key or not isinstance(r.get('relationship'),str) or not r['relationship'].strip():
            raise ValueError('Pair needs a winner and decisive panel relationship')
        seen.add(key)
    if seen!=expected:raise ValueError('Missing pairs')


def validate_appeal(appeal,ids):
    if not isinstance(appeal,dict) or set(appeal)!=set(ids):raise ValueError('Appeal must cover exactly the shown candidates')
    for row in appeal.values():
        if not isinstance(row,dict) or row.get('answer') not in ('yes','no','uncertain') or not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('Malformed appeal answer')


def fine_order(ids,j1,j2,rank_sum):
    expected=list(combinations(ids,2))
    validate_pairs(j1,expected);validate_pairs(j2,expected)
    wins=Counter({k:0 for k in ids});per={}
    for juror,rows in [('J1',j1),('J2',j2)]:
        counts=Counter({k:0 for k in ids})
        for row in rows:counts[row['winner']]+=1
        wins.update(counts);per[juror]=dict(counts)
    if rank_sum is None:
        # Final forks have no coarse ranks. Use competition ranks from each
        # juror's own pairwise wins; equal win counts share the same rank.
        rank_sum={k:sum(1+sum(v>counts[k] for v in counts.values()) for counts in per.values()) for k in ids}
    if set(rank_sum)!=set(ids):raise ValueError('Rank sum must name each candidate')
    tied=defaultdict(list)
    for k in ids:tied[wins[k]].append(k)
    order=[];ties=[]
    for count,group in sorted(tied.items(),reverse=True):
        head=Counter({k:0 for k in group})
        for row in j1:
            if set(row['pair'])<=set(group):head[row['winner']]+=1
        ranked=sorted(group,key=lambda k:(-head[k],rank_sum[k],k))
        order+=ranked
        if len(group)>1:ties.append({'group':group,'J1_head_to_head_wins':dict(head),'resolved':ranked})
    juror_orders={j:sorted(ids,key=lambda k:(-counts[k],rank_sum[k],k)) for j,counts in per.items()}
    return {'order':order,'wins':dict(wins),'juror_wins':per,'juror_orders':juror_orders,'ties':ties,'rank_sum':rank_sum,
            'tie_rule':'J1 head-to-head; multiway ties use J1 wins within the tied group, then rank sum, finally ID if unresolved'}


def candidate_images(candidates,ids):
    images=[]
    for key in ids:
        row=candidates[key];dest=Path(row['directory'])
        reading=json.loads((dest/'blind.json').read_text())
        caption=key+': '+reading['idea_in_ten_words']+'; '+reading['proof_panel']+': '+reading['proof']
        images += [(caption,dest/'picture.png'),(key+' — deterministic closed-product drawing',dest/'drawing.png')]
    return images


def coarse(candidates):
    ids=list(candidates);rankings={};appeal={}
    for juror in ('J1','J2'):
        prompt=ROLES[juror]+'\n'+QUESTION+'\nOrder every candidate, best first. '+APPEAL+'''
JSON only: {"order":[IDs],"reasons":{ID:"one decisive relationship beyond the front"},
"appeal":{ID:{"answer":"yes|no|uncertain","reason":"short sentence"}}}.
No scores, execution penalties or repair suggestions. IDs: '''+', '.join(ids)
        rec=text_call('coarse/'+juror,prompt,OUT/'jury/coarse'/f'{juror}.json',
            images=candidate_images(candidates,ids),max_tokens=7000,ceiling=.80)
        rankings[juror]=validate_rank(rec['payload']['order'],ids)
        validate_appeal(rec['payload']['appeal'],ids)
        reasons=rec['payload'].get('reasons')
        if not isinstance(reasons,dict) or set(reasons)!=set(ids) or any(not isinstance(x,str) or not x.strip() for x in reasons.values()):
            raise ValueError('Each coarse candidate needs its panel relationship')
        appeal[juror]=rec['payload']['appeal']
    result=coarse_cut(rankings['J1'],rankings['J2'])
    result.update(jurors=rankings,appeal=appeal)
    write(OUT/'jury/coarse/result.json',result)
    return result


def fine(candidates,stage,rank_sum):
    ids=list(candidates);batches=pair_batches(ids);answers={};appeals={}
    for juror in ('J1','J2'):
        all_rows=[];appeals[juror]=[]
        for i,batch in enumerate(batches,1):
            shown=[k for k in ids if any(k in pair for pair in batch)]
            prompt=ROLES[juror]+'\n'+QUESTION+'\nFor every pair choose exactly one candidate. '+APPEAL+'''
For each pair give the preference and decisive panel relationship in ONE sentence.
JSON only: {"pairs":[{"pair":[ID,ID],"winner":ID,"relationship":"one sentence"}],
"appeal":{ID:{"answer":"yes|no|uncertain","reason":"short sentence"}}}.
No scores, execution penalties or repair suggestions. Pairs: '''+json.dumps(batch)
            rec=text_call(f'pairwise/{stage}/{juror}/{i}',prompt,OUT/'jury'/stage/f'{juror}-{i}.json',
                images=candidate_images(candidates,shown),max_tokens=6000,ceiling=.60)
            validate_pairs(rec['payload']['pairs'],batch)
            validate_appeal(rec['payload']['appeal'],shown)
            all_rows+=rec['payload']['pairs'];appeals[juror].append(rec['payload']['appeal'])
        answers[juror]=all_rows
    result=fine_order(ids,answers['J1'],answers['J2'],rank_sum)
    result.update(pairs=answers,appeal=appeals,batches=batches,question=QUESTION)
    write(OUT/'jury'/stage/'result.json',result)
    return result


def calibration(**updates):
    path=OUT/'critic-calibration.json'
    if path.exists():rec=json.loads(path.read_text())
    else:
        seed=REPO/'docs/audit/day-8/jury/critic-calibration-v2.json'
        original=json.loads(seed.read_text())
        rec={'schema':'r1_critic_calibration/1','format_seed':{'path':str(seed.relative_to(REPO)),
             'sha256':sha(seed),'keys':list(original)},'rule':QUESTION,
             'format_departure':'Ordinal judgments and owner marks/picks; no historical scores, caps or anchors copied.',
             'marks':[],'picks':[],'departures':[]}
    rec.update(updates);write(path,rec);return rec
