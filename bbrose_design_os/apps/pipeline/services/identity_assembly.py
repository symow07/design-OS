"""Explicit D-D4-1 assembly revision; Day 3 instrument remains unchanged."""
import copy
import json
from pathlib import Path
from apps.pipeline.services import fidelity_master as fm
from apps.ire.identity_sightlines import evaluate

ROOT=fm.fa.ROOT
INSTRUMENT={'id':'D-D4-1','counter_mm':900,'eye_floor_band_mm':[1450,1650],'eye_above_base_band_mm':[550,750],
 'front_distance_band_mm':[500,800],'pass_point':[550,500],'median':[650,650],'secondary':[350,500],'far_advisory':[550,800],
 'pass_point_note':'Owner-declared pass point, not a mathematical worst case over the entire eye band.',
 'pass_law':'Every complete logo/name/descriptor zone on every bottle certified clear; unresolved boundary cells fail.',
 'decoration_law':'Nominal cylindrical artwork-area visibility bounds; shoulder conformity unresolved. Not an acceptance threshold.',
 'shoulder_approximation':'Outward cylinders at <=1mm vertical slices; conservative silhouette approximation.',
 'collar_approximation':'Circular openings bounded inward by inscribed squares; conservative, actual hole vectors remain circular.',
 'identity_cell_mm':.05,'decoration_cell_mm':1.,'ray_margin_mm':.25,'whole_mm_rise':True,'about_tolerance_percent':10}


def model_at(case='family',rise=30,stagger=False):
    if case not in ('family','144','146'):raise ValueError('Unknown declared assembly case.')
    square=case=='146';w,d,h=(120,120,260) if square else (180,150,300)
    source=json.loads((ROOT/'docs/audit/day-4/master/design-spec.json').read_text())
    hole=18 if square else 31;width=16 if square else 29;height=98 if square else 108
    web=(w-4*hole)/5;pitch=hole+web;tread=(d-16)/3;seats=[6+i*rise for i in range(3)]
    positions=[{'id':f'r{r+1}-c{c+1}','row':r+1,'column':c+1,'xyz':[web+hole/2+c*pitch+(pitch/2 if stagger and r==1 else 0),(r+.5)*tread,seats[r]]} for r in range(3) for c in range(4)]
    identity=source['identity_zones'] if not square else [{'element_id':'Kiss-Me-provisional-upper-identity','flat_bbox_mm':[-7,48,7,80]}]
    deco=[-8,0,8,86] if square else source['decoration_region_mm']
    parent=json.loads((ROOT/('docs/audit/day-3/case-146' if square else 'docs/audit/day-3/master' if case=='family' else 'docs/audit/day-3/case-144')/'assembly-spec.json').read_text())
    return {'schema_version':'assembly_spec/2.0','revision':2,'parent_hash':fm.digest(parent),'case_id':case,
     'product_spec_hash':None if square else fm.digest(source),'product_revision':None if square else 2,'instrument':copy.deepcopy(INSTRUMENT),
     'envelope':[w,d,h],'about_height_range_mm':[h*.9,h*1.1],'square':square,'product_width':width,'product_height':height,
     'profile':[] if square else source['elevation_proposal']['profile'],'identity':identity,'decoration':deco,'hole':hole,'thickness':6,
     'header_height':100,'rise':rise,'seats':seats,'tread':tread,'pitch':pitch,'positions':positions,'stagger':stagger,
     'material':'printed cardboard, PROVISIONAL owner input; 6mm construction proposal pending fabricator',
     'identity_authority':'PROVISIONAL vial identity z48..80; no artwork measurement supplied' if square else 'Measured concept147 fidelity r2 identity; for 144 this is an explicit same-envelope identity proxy, not measured Ginkgo lettering',
     'decoration_authority':'PROVISIONAL full 98mm height minus12mm closure' if square else 'Measured decoration bounds on nominal radius14.5 cylinder; upper0.55mm enters shoulder; physical conformity unresolved',
     'required_height':6+2*rise+height+100,'height_datum':'108mm overall comparison unresolved' if not square else '98mm overall provisional',
     'production_ready':False,'geometry_only':case!='family','artwork_state':'dependency designer review' if case=='family' else 'original copy retained; no substitute artwork',
     'structural_approval':'pending fabricator; no load rating; cuts/glue/joints not released'}


def plan_checks(model):
    w,d,h=model['envelope'];hole=model['hole'];half=hole/2;positions=model['positions'];failures=[]
    for p in positions:
        x,y,z=p['xyz']
        if x-half<4 or x+half>w-4 or y-half<4 or y+half>3*model['tread']-4:failures.append(p['id']+' hole violates 4mm edge margin')
        if x-model['product_width']/2<model['thickness'] or x+model['product_width']/2>w-model['thickness']:failures.append(p['id']+' body intersects side support corridor')
    for i,a in enumerate(positions):
        for b in positions[i+1:]:
            if a['row']==b['row'] and abs(a['xyz'][0]-b['xyz'][0])-hole<4:failures.append('hole ligament below4mm')
    return {'passed':not failures,'failures':failures,'count':len(positions),'literal_half_pitch_mm':model['pitch']/2 if model['stagger'] else 0,
            'minimum_width_for_recentered_same_pitch_mm':3.5*model['pitch']+hole+8 if model['stagger'] else None,
            'rightmost_hole_edge_mm':max(p['xyz'][0]+half for p in positions)}


def solve(case='family',stagger=False):
    fm.validate_spec(json.loads((ROOT/'docs/audit/day-4/master/design-spec.json').read_text()))
    chosen=None;attempts=[]
    for rise in range(6,201):
        model=model_at(case,rise,stagger)
        if not plan_checks(model)['passed']:
            chosen=model;break
        result=evaluate(model,decoration=False);attempts.append({'rise_mm':rise,'identity_passed':result['passed']})
        if result['passed']:chosen=model;break
    if chosen is None:chosen=model_at(case,200,stagger)
    model=chosen;plan=plan_checks(model)
    cases={name:evaluate(model,*point) for name,point in [('pass_point',(550,500)),('median',(650,650)),('secondary',(350,500)),('far_advisory',(550,800))]} if plan['passed'] else {}
    exact_h=model['envelope'][2];exact_rise=int((exact_h-6-model['product_height']-100)//2)
    exact=evaluate(model_at(case,exact_rise,stagger),decoration=False) if plan['passed'] else None
    minimum=model['required_height'] if cases and cases['pass_point']['passed'] else None
    return dict(model,plan_checks=plan,rise_search=attempts,sightlines=cases,minimum_height_mm=minimum,
      exact_requested_height={'height_mm':exact_h,'maximum_whole_mm_rise':exact_rise,'identity_passed':exact['passed'] if exact else False},
      requested_height_shortfall_mm=max(0,minimum-exact_h) if minimum else None,
      status='solution_provisional' if minimum and minimum<=exact_h and plan['passed'] else 'refused',
      about_height_passed=bool(minimum and minimum<=model['about_height_range_mm'][1]),
      original_brief=json.loads((fm.fa.APP/'docs/design_presets/stepped-display-v1/original-briefs.json').read_text()).get(case,'Family uses exact Sun Repair copy from measured master'))


def legacy_negative():
    from apps.pipeline.services.assembly_spec import make_assembly
    from apps.ire.stepped_display import solve as legacy_solve
    result=legacy_solve(make_assembly('144'))
    return {'instrument':'Day3 full-decoration opaque-row-wall eye350/500','status':result['status'],'required_height_mm':result['required_height_mm'],'checks':result['checks'],'passed_negative':result['status']=='refused','unchanged_legacy_module':True}
