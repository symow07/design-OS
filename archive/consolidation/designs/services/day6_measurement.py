"""Recorded D1 face measurements and the owner's single vector-device trace."""
from pathlib import Path
import json, math
import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from . import fidelity_assets as fa, fidelity_master as fm

ROOT = fa.ROOT / 'docs/audit/day-6'
D1 = fa.ROOT / 'docs/audit/day-5/concepts/D1/attempt-2/image.png'
D1_HASH = '88ec461884b4d816fb3a53534628b5160f8fdc773e9091d96d05b1003a58f11e'


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def measure():
    target = ROOT / 'concept-D1-measurement.json'
    if target.exists():
        raise ValueError('Source measurement is immutable; use a new revision.')
    if fa.sha(D1) != D1_HASH:
        raise ValueError('Owner-selected D1 image changed.')
    im = np.array(Image.open(D1).convert('RGB'))
    def sample(x, y):
        return {'xy_px': [x, y], 'window_px': 11, 'srgb': np.median(im[y-5:y+6,x-5:x+6].reshape(-1,3),axis=0).tolist()}
    boxes = {'logo':[392,91,643,139], 'SUN':[380,162,516,229], 'REPAIR':[380,245,610,310],
             'name_rule':[380,328,512,330], 'SERUM':[381,349,520,373], 'arabic':[382,392,590,420], 'benefit':[384,445,545,461]}
    baseline = {'SUN':228,'REPAIR':309,'SERUM':372,'arabic':409,'benefit':460}
    copy = {'SUN':'SUN','REPAIR':'REPAIR','SERUM':'SERUM','arabic':'سيروم صن ريبير','benefit':'Revive + Smooth'}
    header_box = [183,48,842,485]
    def point(x,y):
        return [(x-183)*180/659, (y-48)*100/437]
    elements=[]
    for key, box in boxes.items():
        x0,y0,x1,y1=box;patch=im[y0:y1,x0:x1]
        pale=(patch[:,:,0]>232)&(patch[:,:,1]>210)&(patch[:,:,2]>165)
        colour=np.median(patch[pale],axis=0).tolist()
        elements.append({'id':key,'copy':copy.get(key),'bbox_px':box,'bbox_mm':point(x0,y0)+point(x1,y1),
                         'baseline_px':baseline.get(key),'baseline_y_mm':point(0,baseline[key])[1] if key in baseline else None,
                         'colour_srgb':colour,'colour_rule':'Median lit cream pixels R>232,G>210,B>165 inside isolated copy box',
                         'pixel_uncertainty':2,'mapping':'header communication region; inferred bottom datum'})
    centre=[[807,140],[759,180],[730,220],[720,260],[738,300],[780,340],[813,380],[814,420],[788,460],[771,480]]
    header_samples=[sample(x,y) for x,y in [(260,175),(660,150),(270,360),(830,430),(270,100),(600,80),(830,220),(280,430)]]
    faces=[{'surface_id':'header.front','size_mm':[180,100],'status':'measured with inferred face datum','source_box_px':header_box,
            'field_samples':header_samples,'elements':elements,'gesture_centreline_px':centre,'gesture_centreline_mm':[point(*xy) for xy in centre],
            'datum_note':'Top/side bounds observed. Bottom is cap-top communication limit, not a physical seam. Back plane continues to y865 behind bottles.',
            'deviations':['Picture rounded upper corners become the solved rectangular header.','Observed659x437px communication region is mapped to180x100mm; aspect deformation declared.']},
           {'surface_id':'riser.3.front','size_mm':[180,54],'status':'field measured; gesture composed through bottle occlusion',
            'source_box_px':[162,865,862,1284],'field_samples':[sample(x,y) for x,y in [(335,910),(492,910),(653,910),(335,1160),(492,1160),(653,1160)]],
            'deviations':['The source has two rows. Its exposed inter-row field is mapped to a54mm riser; bottle-covered regions are not measured.']},
           {'surface_id':'riser.2.front','size_mm':[180,54],'status':'composed, not measured','source_box_px':None,'field_samples':[],
            'deviations':['Third stepped row absent in picture. Continue the shared field and single gesture; no added motif/copy.']},
           {'surface_id':'lip.front','size_mm':[180,6],'status':'source grammar measured; geometry-compressed fascia','source_box_px':[114,1284,908,1485],
            'field_samples':[sample(x,y) for x,y in [(235,1320),(235,1440),(880,1320),(880,1440)]],
            'gesture_centreline_px':[[810,1290],[748,1320],[675,1360],[626,1400],[607,1440],[616,1470]],
            'deviations':['Tall source201px fascia cannot retain its visible S-turn on a6mm lip. Continue the common device across lip and base; do not distort one isolated stripe to claim equality.']},
           {'surface_id':'riser.1.front','size_mm':[180,6],'status':'composed, not measured','source_box_px':None,'field_samples':[],
            'deviations':['Base edge composed as continuation below lip.']},
           *[{'surface_id':'side.'+side,'size_mm':[150,114],'status':'composed, not measured','source_box_px':None,'field_samples':[],
              'deviations':['Source shows narrow inner side strips; exterior face is not measurable. Shared field only, no new element.']} for side in ['left','right']]]
    report={'schema':'day6_D1_measurement/1','source_path':str(D1.relative_to(fa.ROOT)),'source_sha256':D1_HASH,
            'owner_acceptance':'direction only, D-D6-1; artwork-source count exception D-D6-2', 'count_in_picture':8,'geometry_count':12,
            'geometry_envelope_mm':[180,150,322],'seats_mm':[6,60,114],'rise_mm':54,'header_mm':100,
            'coordinates':'Source pixels; face-local mm from top-left. Occluded geometry is never inferred from image.',
            'faces':faces,'shared_device_colours':'Recorded cream245/219/183 and shadow130/70/17; D-D6-3 overrides photographed shading of the device.',
            'required_header_copy':list(copy.values()),'uncertainty_note':'Manual visual landmark measurements,±2sourcepx; instrument reports measured-vs-composed status separately.'}
    write(target,report)
    calibration={'schema':'critic_calibration/1','weights_changed':False,'points':[
        {'source':'owner Day6 prompt D-D6-1','type':'direction_ranking','owner':['D1','D2','D3'],'critic':['D3','D2','D1'],'critic_scores':{'D1':6.9,'D2':7.1,'D3':7.2},'inference':'Single human preference observation; no automatic weight fitting.'},
        {'source':'owner Day6 prompt F5','type':'bottle_verdict','concept147':'accepted','revision3':'basic but faithful','numeric_human_score':None}],
        'future_weight_change_requirement':'Named reason and full golden bad-set rerun; no current creative threshold changed.'}
    write(ROOT/'critic-calibration.json',calibration)
    return report


def dense(points, step=.015):
    values=[]
    for a,b in zip(points,points[1:]+points[:1]):
        a=np.array(a);b=np.array(b);n=max(1,math.ceil(float(np.linalg.norm(b-a))/step))
        values.extend(a+(b-a)*t for t in np.arange(n)/n)
    return np.asarray(values)


def trace_device(destination):
    """One authorized trace of the retained1000-PPI two-plane master, never text."""
    if not (ROOT/'concept-D1-measurement.json').exists():
        raise ValueError('D1 measurement must precede artwork.')
    dst=Path(destination);dst.mkdir(parents=True,exist_ok=False)
    source=fa.ROOT/'docs/audit/day-5/two-ink/poisson-attempt'
    instrument=json.loads((source/'fidelity-instrument.json').read_text());roles=[]
    for role in ['shadow','cream']:
        file=source/f'swoosh-{role}.png';a=np.array(Image.open(file))[:,:,3];h,w=a.shape
        contours,hierarchy=cv2.findContours((a>=128).astype(np.uint8),cv2.RETR_TREE,cv2.CHAIN_APPROX_NONE)
        paths=[];original=[];vectors=[]
        for i, contour in enumerate(contours):
            xy=contour[:,0,:].astype(float)+.5;xy[:,0]*=fa.WIDTH/w;xy[:,1]*=fa.HEIGHT/h
            original.extend(xy)
            # Fixed0.04mm simplification, far below0.3mm allowed deviation.
            simplified=cv2.approxPolyDP(xy.astype(np.float32),.04,True)[:,0,:].astype(float)
            if len(simplified)<3:
                if cv2.contourArea(contour)>0:
                    simplified=xy
                else:
                    x,y=xy.mean(axis=0);r=.5*25.4/1000;simplified=np.array([[x-r,y-r],[x+r,y-r],[x+r,y+r],[x-r,y+r]])
            points=simplified.tolist();paths.append({'points_mm':points,'parent':int(hierarchy[0,i,3])})
            vectors.extend(dense(points))
        orig=np.asarray(original);vec=np.asarray(vectors)
        forward=float(cKDTree(vec).query(orig)[0].max());reverse=float(cKDTree(orig).query(vec)[0].max())
        roles.append({'role':role.upper(),'colour_srgb':instrument['endmembers'][role]['srgb'],'source_sha256':fa.sha(file),
                      'source_alpha_threshold':.5,'paths':paths,'contour_check':{'reference_to_vector_max_mm':forward,'vector_to_reference_max_mm':reverse,
                      'limit_mm':.3,'passed':max(forward,reverse)<=.3},'fill_rule':'evenodd'})
    device={'schema':'brand_device/1','id':'bbrose-sun-repair-swoosh','authority':'D-D6-3; single authorized device trace only',
            'width_mm':fa.WIDTH,'height_mm':fa.HEIGHT,'roles':roles,'source':'Day5 retained1000PPI two-plane master',
            'deviation':'vector edge replaces airbrush softness','text_traced':False,'approval':'shown for owner objection; used unless objected',
            'trace_count':1,'contour_passed':all(r['contour_check']['passed'] for r in roles)}
    write(dst/'device.json',device)
    chunks=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{fa.WIDTH}mm" height="{fa.HEIGHT}mm" viewBox="0 0 {fa.WIDTH} {fa.HEIGHT}">']
    for role in roles:
        data=' '.join('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in p['points_mm'])+' Z' for p in role['paths'])
        colour='#'+''.join(f'{round(v):02x}' for v in role['colour_srgb'])
        chunks.append(f'<path id="{role["role"]}" fill="{colour}" fill-rule="evenodd" d="{data}"/>')
    chunks.append('</svg>');(dst/'device.svg').write_text('\n'.join(chunks))
    if not device['contour_passed']:
        raise ValueError('Device contour exceeds owner tolerance; retain failed evidence.')
    return device


def repair_contour_serialization(destination):
    """Recover collapsed nonzero-area contours in the one trace, not a new design.

    Re-read the identical binary component indices to recover discarded vertices.
    Other paths, alpha threshold, colours, source and tolerance are untouched.
    """
    import shutil
    dst=Path(destination);data=json.loads((dst/'device.json').read_text())
    backup=dst/'serialization-rejected';backup.mkdir(exist_ok=False)
    for name in ('device.json','device.svg'):shutil.copyfile(dst/name,backup/name)
    repaired=[]
    for role in data['roles']:
        source=fa.ROOT/'docs/audit/day-5/two-ink/poisson-attempt'/('swoosh-'+role['role'].lower()+'.png')
        if fa.sha(source)!=role['source_sha256']:raise ValueError('Trace source changed')
        alpha=np.array(Image.open(source))[:,:,3];h,w=alpha.shape
        contours,hierarchy=cv2.findContours((alpha>=128).astype(np.uint8),cv2.RETR_TREE,cv2.CHAIN_APPROX_NONE)
        if len(contours)!=len(role['paths']):raise ValueError('Contour topology changed')
        original=[];vectors=[]
        for i,contour in enumerate(contours):
            xy=contour[:,0,:].astype(float)+.5;xy[:,0]*=fa.WIDTH/w;xy[:,1]*=fa.HEIGHT/h
            original.extend(xy)
            simplified=cv2.approxPolyDP(xy.astype(np.float32),.04,True)[:,0,:]
            if len(simplified)<3 and cv2.contourArea(contour)>0:
                role['paths'][i]['points_mm']=xy.tolist();repaired.append([role['role'],i])
            vectors.extend(dense(role['paths'][i]['points_mm']))
        original=np.asarray(original);vectors=np.asarray(vectors)
        a=float(cKDTree(vectors).query(original)[0].max());b=float(cKDTree(original).query(vectors)[0].max())
        role['contour_check'].update(reference_to_vector_max_mm=a,vector_to_reference_max_mm=b,passed=max(a,b)<=.3)
    data['serialization_repair']={'reason':'Nonzero-area contours collapsed to tiny squares when simplification produced fewer than3vertices; original traced vertices restored.',
                                  'changed_component_indices':repaired,'failed_device_sha256':fa.sha(backup/'device.json'),
                                  'alpha_threshold_changed':False,'aesthetic_retrace':False}
    data['contour_passed']=all(r['contour_check']['passed'] for r in data['roles'])
    write(dst/'device.json',data)
    chunks=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{fa.WIDTH}mm" height="{fa.HEIGHT}mm" viewBox="0 0 {fa.WIDTH} {fa.HEIGHT}">']
    for role in data['roles']:
        path=' '.join('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in p['points_mm'])+' Z' for p in role['paths'])
        colour='#'+''.join(f'{round(v):02x}' for v in role['colour_srgb'])
        chunks.append(f'<path id="{role["role"]}" fill="{colour}" fill-rule="evenodd" d="{path}"/>')
    (dst/'device.svg').write_text('\n'.join(chunks+['</svg>']))
    if not data['contour_passed']:raise ValueError('Repaired serialization still fails; no further trace authorized')
    return data
