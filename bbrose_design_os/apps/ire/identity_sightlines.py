"""D-D4-1 opaque solids and conservative interval ray bundles.

A clear result covers a complete surface cell, not its sampled centre. Unresolved
boundary cells never pass identity. Decoration fractions are bounded by area.
"""
import math


def interval_product(a,b):
    v=[x*y for x in a for y in b]
    return min(v),max(v)


def trig_range(a,b,fn):
    points=[a,b]
    step=math.pi/2
    points += [k*step for k in range(math.ceil(a/step),math.floor(b/step)+1)]
    values=[fn(v) for v in points]
    return min(values),max(values)


def patch_bounds(position,cell,radius,square=False):
    u0,z0,u1,z1=cell;x,y,z=position
    if square:return (x+u0,x+u1),(y-radius,y-radius),(z+z0,z+z1)
    sx=trig_range(u0/radius,u1/radius,math.sin);cy=trig_range(u0/radius,u1/radius,math.cos)
    return (x+radius*sx[0],x+radius*sx[1]),(y-radius*cy[1],y-radius*cy[0]),(z+z0,z+z1)


def self_facing(position,cell,radius,eye,square):
    if square:return 1
    a,b=cell[0]/radius,cell[2]/radius
    dx,dy=eye[0]-position[0],position[1]-eye[1]
    phi=math.atan2(dx,dy);values=[dx*math.sin(t)+dy*math.cos(t)-radius for t in (a,b)]
    values += [dx*math.sin(t)+dy*math.cos(t)-radius for t in (phi,phi-math.pi,phi+math.pi) if a<=t<=b]
    return 1 if min(values)>0 else -1 if max(values)<=0 else 0


def ray_range(eye,bounds,t):
    out=[]
    for e,v in zip(eye,bounds):
        lo,hi=interval_product((v[0]-e,v[1]-e),t);out.append((e+lo,e+hi))
    return out


def solid_relation(eye,bounds,solid,margin=.25):
    """1 = whole bundle clear; -1 = whole bundle blocked; 0 unresolved.

    Cylinders bound each one-mm shoulder slice outward. This explicit <=1mm
    silhouette approximation is conservative; no full-row wall is substituted.
    """
    lo,hi=solid['bounds'];ty=bounds[1]
    if ty[0]<=eye[1]:return 0
    t0=max(0.,(lo[1]-eye[1])/(ty[1]-eye[1]));t1=min(1.-1e-9,(hi[1]-eye[1])/(ty[0]-eye[1]))
    if t1<t0:return 1
    if solid['kind']=='cylinder':
        cx,cy,r=solid['circle'];mx=(bounds[0][0]+bounds[0][1])/2;my=(ty[0]+ty[1])/2
        dx,dy=mx-eye[0],my-eye[1];error=t1*math.hypot((bounds[0][1]-bounds[0][0])/2,(ty[1]-ty[0])/2)
        aa=dx*dx+dy*dy;bb=2*((eye[0]-cx)*dx+(eye[1]-cy)*dy)
        cc=(eye[0]-cx)**2+(eye[1]-cy)**2-(r+error+margin)**2
        disc=bb*bb-4*aa*cc
        if disc<0:return 1
        root=math.sqrt(disc);t0=max(t0,(-bb-root)/(2*aa));t1=min(t1,(-bb+root)/(2*aa))
        if t1<t0:return 1
    rays=ray_range(eye,bounds,(t0,t1))
    if any(r[1]<a-margin or r[0]>b+margin for r,a,b in zip(rays,lo,hi)):return 1
    if solid['kind']=='cylinder':
        cx,cy,r=solid['circle'];mx=(bounds[0][0]+bounds[0][1])/2;my=(ty[0]+ty[1])/2
        dx,dy=mx-eye[0],my-eye[1];length=dx*dx+dy*dy
        t=max(t0,min(t1,((cx-eye[0])*dx+(cy-eye[1])*dy)/length))
        dist=math.hypot(eye[0]+t*dx-cx,eye[1]+t*dy-cy)
        error=t1*math.hypot((bounds[0][1]-bounds[0][0])/2,(ty[1]-ty[0])/2)
        if dist>r+error+margin:return 1
        test=ray_range(eye,bounds,(t,t))
        maxdist=max(math.hypot(x-cx,y-cy) for x in test[0] for y in test[1])
        if maxdist<r-margin and test[2][0]>lo[2]+margin and test[2][1]<hi[2]-margin:return -1
    else:
        test=ray_range(eye,bounds,((t0+t1)/2,)*2)
        if all(r[0]>a+margin and r[1]<b-margin for r,a,b in zip(test,lo,hi)):return -1
    return 0


def cylinder(name,x,y,z0,z1,r):
    return {'id':name,'kind':'cylinder','circle':(x,y,r),'bounds':((x-r,y-r,z0),(x+r,y+r,z1))}


def box(name,x0,y0,z0,x1,y1,z1):
    return {'id':name,'kind':'box','bounds':((x0,y0,z0),(x1,y1,z1))}


def solids_for(model,target):
    solids=[]
    for p in model['positions']:
        if p['id']==target['id']:continue
        x,y,z=p['xyz']
        if model['square']:
            r=model['product_width']/2;solids.append(box(p['id'],x-r,y-r,z,x+r,y+r,z+model['product_height']))
        else:
            for profile in model['profile']:
                dz=profile['z1']-profile['z0'];n=math.ceil(dz) if profile['r0']!=profile['r1'] else 1
                for i in range(n):
                    a,b=i/n,(i+1)/n;r=max(profile['r0']+(profile['r1']-profile['r0'])*v for v in (a,b))
                    solid=cylinder(p['id']+'/'+profile['id'],x,y,z+profile['z0']+dz*a,z+profile['z0']+dz*b,r)
                    solid['bounds_only']=profile['r0']!=profile['r1'];solids.append(solid)
    # Same-row solids included. Host body omitted; its facing is analytic.
    # Own closure does not overhang the 29mm host cylinder. Square vial has no overhang.
    w,d=model['envelope'][:2];t=model['tread'];th=model['thickness']
    for i,seat in enumerate(model['seats']):
        solids.append(box('riser.'+str(i+1),0,i*t,0,w,i*t+th,seat))
        solids.append(box('seat.'+str(i+1),0,i*t,seat-th,w,(i+1)*t,seat))
        # Collar is a plate minus holes. Four rails and edge strips give an
        # exact square-hole plate; circle openings conservatively use an inscribed
        # square (explicit approximation), never an uninterrupted full plate.
        row=[p for p in model['positions'] if p['row']==i+1];cy=row[0]['xyz'][1]
        half=model['hole']/2/(math.sqrt(2) if not model['square'] else 1)
        solids.extend([box('collar.front',0,i*t,seat,w,cy-half,seat+th),box('collar.back',0,cy+half,seat,w,(i+1)*t,seat+th)])
        start=0
        for p in row:
            x=p['xyz'][0];solids.append(box('collar.web',start,cy-half,seat,x-half,cy+half,seat+th));start=x+half
        solids.append(box('collar.edge',start,cy-half,seat,w,cy+half,seat+th))
    solids.extend([box('lip',0,0,model['seats'][0],w,th,model['seats'][0]+th),
                   box('side.left',0,0,0,th,d,model['seats'][-1]),box('side.right',w-th,0,0,w,d,model['seats'][-1])])
    for solid in solids:
        if solid['id'].startswith('collar.') and not model['square']:solid['bounds_only']=True
    return solids


def visibility(model,p,rect,eye,resolution=.5,identity=False):
    solids=solids_for(model,p);radius=model['product_width']/2
    queue=[rect];clear=blocked=unknown=0.;limiting=set();cells=0
    while queue:
        cell=queue.pop();cells+=1;area=(cell[2]-cell[0])*(cell[3]-cell[1])
        facing=self_facing(p['xyz'],cell,radius,eye,model['square'])
        relations=[]
        if facing==1:
            bounds=patch_bounds(p['xyz'],cell,radius,model['square'])
            for solid in solids:
                relation=solid_relation(eye,bounds,solid)
                if relation==-1 and solid.get('bounds_only'):relation=0
                if relation!=1:relations.append((relation,solid['id']))
                if relation==-1:break
        if facing==1 and not relations:clear+=area;continue
        if facing==-1 or any(r==-1 for r,_ in relations):
            blocked+=area;limiting.update(n for _,n in relations)
            if identity:return {'passed':False,'lower':0.,'upper':1.,'limiting':sorted(limiting or {'self-facing'}),'certification':'blocked complete subcell'}
            continue
        if max(cell[2]-cell[0],cell[3]-cell[1])<=resolution:
            unknown+=area;limiting.update(n for _,n in relations)
            if identity:return {'passed':False,'lower':0.,'upper':1.,'limiting':sorted(limiting or {'self-facing'}),'certification':'boundary unresolved; fails closed'}
        elif cell[2]-cell[0]>=cell[3]-cell[1]:
            mid=(cell[0]+cell[2])/2;queue.extend([(cell[0],cell[1],mid,cell[3]),(mid,cell[1],cell[2],cell[3])])
        else:
            mid=(cell[1]+cell[3])/2;queue.extend([(cell[0],cell[1],cell[2],mid),(cell[0],mid,cell[2],cell[3])])
    total=clear+blocked+unknown
    return {'passed':blocked==0 and unknown==0,'lower':clear/total,'upper':(clear+unknown)/total,'unresolved_area_mm2':unknown,'cells':cells,'limiting':sorted(limiting),'certification':'interval ray bundles; opaque actual-position solids'}


def validate_model(model):
    expected={f'r{r}-c{c}' for r in (1,2,3) for c in (1,2,3,4)}
    if len(model['positions'])!=12 or {p['id'] for p in model['positions']}!=expected:raise ValueError('Exactly twelve unique positions required.')
    if not model['identity']:raise ValueError('Identity zones are required; empty cannot pass.')
    for p in model['positions']:
        if p['id']!=f"r{p['row']}-c{p['column']}" or not all(math.isfinite(v) for v in p['xyz']):raise ValueError('Invalid placement identity.')
    for zone in model['identity']:
        a,b,c,d=zone['flat_bbox_mm']
        if not all(math.isfinite(v) for v in (a,b,c,d)) or a>=c or b>=d or b<0:raise ValueError('Invalid identity extent.')
        top=model['product_height']-12 if model['square'] else model['profile'][0]['z1']
        if d>top:raise ValueError('Identity outside supported straight host surface.')
    if not model['square']:
        z=0
        for part in model['profile']:
            if abs(part['z0']-z)>1e-8 or part['z1']<=z or min(part['r0'],part['r1'])<=0 or max(part['r0'],part['r1'])>model['product_width']/2:raise ValueError('Invalid/non-host-safe product profile.')
            z=part['z1']
        if abs(z-model['product_height'])>1e-8:raise ValueError('Profile height mismatch.')


def evaluate(model,eye_z=550,distance=500,decoration=True):
    validate_model(model)
    eye=(model['envelope'][0]/2,-distance,eye_z);results=[]
    for p in model['positions']:
        zones=[dict(element=z['element_id'],**visibility(model,p,z['flat_bbox_mm'],eye,.05,True)) for z in model['identity']]
        result={'bottle':p['id'],'row':p['row'],'identity_passed':all(z['passed'] for z in zones),'zones':zones}
        if decoration:result['decoration']=visibility(model,p,model['decoration'],eye,1.)
        results.append(result)
        if not decoration and not result['identity_passed']:break
    return {'eye_above_base_mm':eye_z,'front_distance_mm':distance,'passed':len(results)==12 and all(r['identity_passed'] for r in results),'bottles':results,
            'rows':[{'row':row,'identity_passed':all(r['identity_passed'] for r in results if r['row']==row),
                     'decoration_fraction_lower':min((r['decoration']['lower'] for r in results if r['row']==row and 'decoration'in r),default=None),
                     'decoration_fraction_upper':min((r['decoration']['upper'] for r in results if r['row']==row and 'decoration'in r),default=None)} for row in (1,2,3)]}
