"""Whole-object eligibility and blind readings, not aesthetic scoring."""
import json
from pathlib import Path

from .round_balm_calls import OUT, text_call, write
from .round_balm_sheet import PANEL_IDS
from .round_balm_images import BANNED

STATES = {'present','quiet','blank','generic','different design'}
COPY_KEYS = ('brand','collection','product_en','product_ar','tint','net',
             'back_en','back_es','back_ar','inci_placeholder','ean_frame','batch')


def has_words(value):
    return isinstance(value,str) and bool(value.strip())


def decide(payload, crop):
    """Missing/invalid inspection is pending, never quietly eligible."""
    panels=payload.get('panels',{})
    if set(panels)!=set(PANEL_IDS):
        raise ValueError('Inspection must name all nine panels exactly once')
    reasons=[]
    for name,panel in panels.items():
        state=panel.get('state')
        if state not in STATES or not has_words(panel.get('evidence')):
            raise ValueError('Invalid panel inspection: '+name)
        if state in {'blank','generic','different design'}:
            reasons.append(name+': '+state+' — '+panel['evidence'])
        if state=='quiet' and not has_words(panel.get('explained_by')):
            reasons.append(name+': quiet but unexplained by the object')
    copy=payload.get('copy_presence',{})
    if set(copy)!=set(COPY_KEYS) or any(v not in ('present','absent','unclear') for v in copy.values()):
        raise ValueError('Invalid copy presence inspection')
    motifs=payload.get('banned_motifs')
    if not isinstance(motifs,list) or any(not has_words(x) for x in motifs):raise ValueError('Banned-motif evidence missing')
    reasons += ['banned motif: '+str(x) for x in motifs]
    if crop.get('qualifies') is not True:
        reasons.append('engine crop/aspect mismatch over 2%')
    # Presence is recorded, not a raster live-type or copy-fit certification.
    return {'eligible':not reasons,'reasons':reasons,
            'copy_gaps':[k+': '+v for k,v in copy.items() if v!='present'],
            'not_certified':'raster lettering presence only; all live-type sizes/fit measured day two'}


def check(dest):
    dest=Path(dest)
    words='''Inspect the complete lip-balm object on its engine sheet and its deterministic
closed-product drawing. No seed, name, artist or ranking is provided. Do not score.
For EACH of the nine panels classify: present / quiet / blank / generic / different design.
Quiet is allowed only when a named relationship to the rest explains its restraint;
flat regulated-copy ground can be quiet and designed. Construction lines, hatched copy
zone legends and empty white flaps outside the nine panels are not artwork and not
blank panels. Inspect the bottom label and carton ends as carefully as the front.
No typography-size or live-copy certification from raster. OCR presence ONLY:
BBROSE brand; collection name; Lip Balm; بلسم شفاه; tint; 4.5 g ℮ 0.15 oz;
back drafts in EN ES AR; INCI owner-to-supply placeholder; empty ladder EAN frame;
batch write-in field on bottom. Record presence/absence/unclear, never invent text.
Assess back_* / INCI / EAN on the engine BACK panel and batch on the engine BOTTOM,
not wherever the model happened to place copy. The approved BBROSE house glyph is
a brand mark, not by itself a banned rose-flower main motif.
''' + BANNED + '''
Return JSON only with keys:
"panels": {PANEL: {"state": CLASSIFICATION, "evidence": "<=12 words",
"explained_by": "named other panel and relationship, or empty string"}},
"copy_presence": {KEY:"present|absent|unclear"},
"banned_motifs": ["motif and panel", ...],
"front_third": "brief observation about hero visibility",
"seam_ground": "whether both wrap edges are flat ground, with visible evidence",
"object_relationship": "one sentence".
PANEL names: '''+', '.join(PANEL_IDS)+'.\nCOPY KEYS: '+', '.join(COPY_KEYS)
    contract=json.loads((OUT/'sheet.json').read_text())
    words+='\nEngine panel boxes [left,top,right,bottom] in the sheet pixels: '+json.dumps({k:p['box_px'] for k,p in contract['panels'].items()})
    rec=text_call('check/'+str(dest.relative_to(OUT)),words,dest/'whole-object-call.json',
        images=[('Nine panels, original sheet',dest/'picture.png'),('Closed front and three-quarter drawing',dest/'drawing.png')],
        max_tokens=3000,ceiling=.17)
    crop=json.loads((dest/'crop.json').read_text())
    result=dict(decide(rec['payload'],crop),inspection=rec['payload'])
    write(dest/'whole-object.json',result)
    return result


def read_blind(dest):
    dest=Path(dest)
    prompt='''What idea does a stranger see in this complete lip-balm object?
Read only these images. No seed or designer intent is supplied. Say the idea in ten
words maximum (idea_in_ten_words), and name the panel that proves it beyond the front
(proof_panel), with the decisive relationship in one short sentence (proof).
Describe the invention visible, never a proposed improvement. JSON only, those three keys.
proof_panel must be exactly one of: body, cap, label, back, side_left, side_right,
top_end, bottom_end. The front cannot be its own proof.'''
    rec=text_call('blind/'+str(dest.relative_to(OUT)),prompt,dest/'blind-call.json',
        images=[('Whole object',dest/'picture.png')],max_tokens=650,ceiling=.06)
    payload=rec['payload']
    if has_words(payload.get('idea_in_ten_words')) and len(payload['idea_in_ten_words'].split())>10:
        # One fresh blind reading can correct the format, within the SAME
        # per-survivor allowance. The first response remains unmodified.
        corrected=text_call('blind-word-limit/'+str(dest.relative_to(OUT)),
            prompt+'\nUse at most EIGHT words for idea_in_ten_words; count them before returning JSON.',
            dest/'blind-word-limit-call.json',images=[('Whole object',dest/'picture.png')],
            max_tokens=650,ceiling=.06-rec['accounted_usd'])
        write(dest/'blind-word-limit.json',{'reason':'Original blind reading exceeded ten words',
            'original_words':len(payload['idea_in_ten_words'].split()),
            'original_call':'blind-call.json','selected_call':'blind-word-limit-call.json',
            'total_accounted_usd':rec['accounted_usd']+corrected['accounted_usd'],
            'seed_or_prior_reading_shown':False})
        payload=corrected['payload']
    if not has_words(payload.get('idea_in_ten_words')) or not 1<=len(payload['idea_in_ten_words'].split())<=10:
        raise ValueError('Blind reading exceeds ten words; retained, not silently rewritten')
    if payload['proof_panel'] not in set(PANEL_IDS)-{'front'}:
        raise ValueError('Blind proof must name a panel beyond carton front')
    if not has_words(payload.get('proof')):raise ValueError('Blind proof must be a sentence')
    write(dest/'blind.json',payload)
    return payload
