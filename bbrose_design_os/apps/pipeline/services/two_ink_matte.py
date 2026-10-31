"""D-D5-1: deterministic, source-bound three-endmember decoration proof.

The additive linear-light proof is separate from ordinary alpha-over previews.
No paid providers, database access, tracing or candidate-dependent test masks.
"""
from pathlib import Path
import json
import math
import cv2
import numpy as np
from PIL import Image
from . import fidelity_assets as fa
from .matte_colour import lin, enc, lab, de


def dilate(mask, radius):
    return cv2.dilate(mask.astype(np.uint8), np.ones((2*radius+1, 2*radius+1), np.uint8)) > 0


def separable_field(pixels, training, iterations=80):
    """Positive per-channel g(y)*h(x), fitted only to declared training pixels."""
    value = lin(pixels)
    weight = training.astype(float)
    g = np.ones((value.shape[0], 1, 3))
    h = np.ones((1, value.shape[1], 3))
    # Alternating constrained least squares; a fixed smoothness kernel suppresses grain.
    for _ in range(iterations):
        numerator = np.sum(value*h*weight[:,:,None], axis=1, keepdims=True)
        denominator = np.sum(h*h*weight[:,:,None], axis=1, keepdims=True)
        g = np.maximum(numerator/np.maximum(denominator, 1e-12), 1e-8)
        for channel in range(3):
            g[:,0,channel] = cv2.GaussianBlur(g[:,0,channel,None], (1,0), 0, sigmaY=2).ravel()
        numerator = np.sum(value*g*weight[:,:,None], axis=0, keepdims=True)
        denominator = np.sum(g*g*weight[:,:,None], axis=0, keepdims=True)
        h = np.maximum(numerator/np.maximum(denominator, 1e-12), 1e-8)
        for channel in range(3):
            h[0,:,channel] = cv2.GaussianBlur(h[0,:,channel,None], (1,0), 0, sigmaY=2).ravel()
        norm = np.mean(h, axis=1, keepdims=True)
        g *= norm; h /= norm
    return enc(g*h)


def triangle_weights(p, background, cream, shadow):
    """Closest point in the RGB triangle, including each edge and its vertices."""
    u, v, q = cream-background, shadow-background, p-background
    uu = np.sum(u*u, axis=-1); vv = np.sum(v*v, axis=-1)
    uv = np.sum(u*v, axis=-1); uq = np.sum(u*q, axis=-1); vq = np.sum(v*q, axis=-1)
    determinant = uu*vv-uv*uv
    f = (uq*vv-vq*uv)/np.maximum(determinant, 1e-16)
    s = (vq*uu-uq*uv)/np.maximum(determinant, 1e-16)
    valid = (determinant>1e-16)&(f>=0)&(s>=0)&(f+s<=1)
    edge_f = np.clip(uq/np.maximum(uu,1e-16),0,1)
    edge_s = np.clip(vq/np.maximum(vv,1e-16),0,1)
    fs = cream-shadow
    along = np.clip(np.sum((p-shadow)*fs,axis=-1)/max(float(np.sum(fs*fs)),1e-16),0,1)
    candidates = [(f,s,valid),(edge_f,np.zeros_like(f),True),
                  (np.zeros_like(s),edge_s,True),(along,1-along,True)]
    error = np.full(f.shape,np.inf); chosen_f=np.zeros_like(f);chosen_s=np.zeros_like(s)
    for cf,cs,allowed in candidates:
        residual = np.sum((q-cf[...,None]*u-cs[...,None]*v)**2,axis=-1)
        better = allowed & (residual<error)
        error=np.where(better,residual,error);chosen_f=np.where(better,cf,chosen_f);chosen_s=np.where(better,cs,chosen_s)
    return chosen_f,chosen_s,determinant


def poisson_ground(pixels, training, prior):
    """Harmonic residual to the separable prior; held-out RGB never enters RHS."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    unknown=~training;labels=np.full(training.shape,-1,int);labels[unknown]=np.arange(unknown.sum())
    ys,xs=np.nonzero(unknown);n=len(ys);rows=[];cols=[];values=[]
    rhs=np.zeros((n,3));degree=np.zeros(n)
    residual=lin(pixels)-lin(prior)
    for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
        ny,nx=ys+dy,xs+dx;valid=(ny>=0)&(ny<training.shape[0])&(nx>=0)&(nx<training.shape[1])
        i=np.flatnonzero(valid);y,x=ny[valid],nx[valid];degree[i]+=1
        other=labels[y,x];missing=other>=0
        rows.extend(i[missing]);cols.extend(other[missing]);values.extend(-np.ones(missing.sum()))
        # Only known training pixels supply boundary residuals.
        rhs[i[~missing]]+=residual[y[~missing],x[~missing]]
    rows.extend(np.arange(n));cols.extend(np.arange(n));values.extend(degree)
    matrix=coo_matrix((values,(rows,cols)),shape=(n,n)).tocsc()
    solution=spsolve(matrix,rhs)
    out=lin(prior);out[training]=lin(pixels)[training];out[unknown]+=solution
    return enc(out)


def flat_map(array, ppi=300, nearest=False):
    width,height=math.ceil(fa.WIDTH/25.4*ppi),math.ceil(fa.HEIGHT/25.4*ppi)
    sx=(np.arange(width)+.5)/width*fa.WIDTH-fa.WIDTH/2
    sy=fa.BODY_TOP+(np.arange(height)+.5)/height*(fa.BOTTOM-fa.BODY_TOP)
    x,y=np.meshgrid(505+186*np.sin(sx/fa.RADIUS),sy)
    return cv2.remap(array.astype(np.float32),x.astype(np.float32),y.astype(np.float32),
                     cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)


def resize_linear_rgba(rgba, size):
    a=rgba[:,:,3:4].astype(float)/255
    values=np.dstack((lin(rgba[:,:,:3])*a,a)).astype(np.float32)
    resized=cv2.resize(values,size,interpolation=cv2.INTER_AREA)
    a=np.clip(resized[:,:,3:4],0,1)
    return enc(resized[:,:,:3]/np.maximum(a,1e-12)),a[:,:,0]


def proof(pixels, background, cream_rgba, shadow_rgba, roi, shadow_support, cream_colour, *, ppi=300):
    """Measure reopened PNGs at physical print resolution; no threshold fitting."""
    size=(math.ceil(fa.WIDTH/25.4*ppi),math.ceil(fa.HEIGHT/25.4*ppi))
    f_rgb,f=resize_linear_rgba(cream_rgba,size);s_rgb,s=resize_linear_rgba(shadow_rgba,size)
    if np.max(f+s)>1.005:raise ValueError('Ink weights exceed unity.')
    b=flat_map(lin(background),ppi);reference=flat_map(lin(pixels),ppi)
    composite=lin(f_rgb)*f[:,:,None]+lin(s_rgb)*s[:,:,None]+b*np.maximum(0,1-f-s)[:,:,None]
    sigma=.08*ppi/25.4
    blur=lambda x:cv2.GaussianBlur(x,(0,0),sigma,borderType=cv2.BORDER_REFLECT_101)
    # lab() expects encoded bytes; retain unquantized encoded values for the metric.
    def encoded_float(x):return np.where(x<=.0031308,12.92*x,1.055*np.maximum(x,0)**(1/2.4)-.055)*255
    delta=de(lab(encoded_float(blur(composite))),lab(encoded_float(blur(reference))))
    raw=de(lab(encoded_float(composite)),lab(encoded_float(reference)))
    region=flat_map(roi.astype(float),ppi,True)>.5
    own_shadow=flat_map(shadow_support.astype(float),ppi,True)>.5
    grey=lin(np.array([128,128,128]));neutral=lin(f_rgb)*f[:,:,None]+lin(s_rgb)*s[:,:,None]+grey*np.maximum(0,1-f-s)[:,:,None]
    clean=lin(cream_colour)*(f+s)[:,:,None]+grey*np.maximum(0,1-f-s)[:,:,None]
    total=f+s; boundary=dilate(region,1)&~cv2.erode(region.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    boundary |= (total>.02)&(total<.98)
    rgb=enc(neutral);hue=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)[:,:,0].astype(float)*2
    err=de(lab(rgb),lab(enc(clean)))
    visible=(np.hypot(lab(rgb)[:,:,1],lab(rgb)[:,:,2])>3)&(de(lab(rgb),lab(np.array([128,128,128])))>1)
    flagged=boundary & ~own_shadow & (total>.02)&(hue>=17)&(hue<=35)&(err>4)&visible
    fraction=float(np.mean(delta[region]<=2))
    return {'ppi':ppi,'sigma_mm':.08,'sigma_px':sigma,'region_pixels':int(region.sum()),
            'recomposition_fraction_deltaE_le2':fraction,'recomposition_passed':fraction>=.99,
            'unsmoothed_fraction_deltaE_le2':float(np.mean(raw[region]<=2)),
            'deltaE_median':float(np.median(delta[region])),'deltaE99':float(np.quantile(delta[region],.99)),
            'fringe_flagged_pixels':int(flagged.sum()),'fringe_passed':not bool(flagged.any())},enc(composite),rgb,flagged


def build(destination, *, ground_method='separable'):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    p=np.array(Image.open(fa.CONCEPT).convert('RGB'))
    old=fa.ROOT/'docs/audit/day-4/measurement-assets'
    base=np.array(Image.open(old/'swoosh-reference-support.png'))>0
    # Freeze a full-stroke envelope before fitting/solving, including adjacent shadow.
    full=dilate(base,4);exclusion=dilate(full,8)
    known=np.zeros(base.shape,bool);known[585:1380,330:684]=True
    text=np.zeros(base.shape,bool)
    measurement=json.loads(fa.MEASUREMENT.read_text())
    for element in measurement['elements']:
        if element['id']=='swoosh':continue
        x0,y0,x1,y1=element['bbox_px'];text[max(0,y0-8):y1+8,max(0,x0-8):x1+8]=True
    ring=dilate(exclusion,4)&~exclusion&known&~text
    guard=dilate(ring,2)
    training=known&~exclusion&~guard&~text
    # Fit body crop; source beyond the body remains presentation-only, not fitted evidence.
    box=(319,547,692,1471);x0,y0,x1,y1=box
    crop_train=training[y0:y1,x0:x1]
    fitted=separable_field(p[y0:y1,x0:x1],crop_train)
    if ground_method=='poisson':
        fitted=poisson_ground(p[y0:y1,x0:x1],crop_train,fitted)
    background=p.copy();background[y0:y1,x0:x1]=fitted
    ring_delta=de(lab(background),lab(p))[ring]
    # Opaque pale core and a dark companion band on the lower-left return, fixed before solve.
    cream_box=(644,936,649,941);shadow_box=(483,1290,488,1295)
    sample=lambda b:np.median(p[b[1]:b[3],b[0]:b[2]].reshape(-1,3),axis=0)
    cream=sample(cream_box);shadow=sample(shadow_box)
    f,s,condition=triangle_weights(lin(p),lin(background),lin(cream),lin(shadow))
    # The declared shadow envelope is independent of the solved weights.
    shadow_support=full & ~cv2.erode(base.astype(np.uint8),np.ones((11,11),np.uint8)).astype(bool)
    f*=full;s*=shadow_support
    # Re-solve the pale edge where the frozen shadow support disallows shadow.
    u=lin(cream)-lin(background);q=lin(p)-lin(background)
    sole=np.clip(np.sum(q*u,axis=2)/np.maximum(np.sum(u*u,axis=2),1e-16),0,1)
    f=np.where(full&~shadow_support,sole,f)
    ff=flat_map(f,1000);ss=flat_map(s,1000)
    qa=np.round(np.clip(ff,0,1)*255).astype(np.uint8)
    qb=np.minimum(np.round(np.clip(ss,0,1)*255),255-qa).astype(np.uint8)
    for name,colour,alpha in [('cream',cream,qa),('shadow',shadow,qb)]:
        rgba=np.dstack([np.broadcast_to(np.round(colour).astype(np.uint8),alpha.shape+(3,)),alpha])
        Image.fromarray(rgba).save(destination/f'swoosh-{name}.png')
    Image.fromarray(background).save(destination/'material-field.png')
    for name,mask in [('stroke-support',full),('stroke-exclusion',exclusion),('ground-training',training),('ground-heldout-ring',ring),('shadow-support',shadow_support)]:
        Image.fromarray(mask.astype(np.uint8)*255).save(destination/(name+'.png'))
    cream_rgba=np.array(Image.open(destination/'swoosh-cream.png'));shadow_rgba=np.array(Image.open(destination/'swoosh-shadow.png'))
    results={}
    for name,cr,sh,allowed in [('two_ink',cream_rgba,shadow_rgba,shadow_support),
        ('day4_negative',np.array(Image.open(old/'swoosh-flat.png')),np.zeros_like(cream_rgba),np.zeros_like(full)),
        ('single_ink_day5_negative',np.array(Image.open(fa.ROOT/'docs/audit/day-5/matte-evaluation/swoosh-flat.png')),np.zeros_like(cream_rgba),np.zeros_like(full))]:
        result,amber,grey,flagged=proof(p,background,cr,sh,full,allowed,cream)
        results[name]=result
        Image.fromarray(amber).save(destination/(name+'-amber-300ppi.png'));Image.fromarray(grey).save(destination/(name+'-grey-300ppi.png'))
        marked=grey.copy();marked[flagged]=[255,0,140];Image.fromarray(marked).save(destination/(name+'-fringe-300ppi.png'))
    negative_ok=all(not(v['recomposition_passed'] and v['fringe_passed']) for k,v in results.items() if k!='two_ink')
    report={'schema':'two_ink_matte/1','route':'deterministic_three_endmember','source_sha256':fa.sha(fa.CONCEPT),
        'background':{'model':('Poisson fit: harmonic residual to separable prior; known RGB only on training pixels' if ground_method=='poisson' else 'linear RGB separable g_c(y)*h_c(x),80 alternating least-squares iterations, fixed2px smoothing'),'crop_xyxy':box,'stroke_dilation_radius_px':8,'additional_full_stroke_radius_px':4,'training_pixels':int(training.sum()),'heldout_ring_pixels':int(ring.sum()),'heldout_excluded_from_fit':True,'ring_median_deltaE2000':float(np.median(ring_delta)),'ring_p95_deltaE2000':float(np.quantile(ring_delta,.95)),'passed':bool(np.median(ring_delta)<=1.5)},
        'endmembers':{'cream':{'source_box_px':cream_box,'srgb':cream.tolist()},'shadow':{'source_box_px':shadow_box,'srgb':shadow.tolist()}},
        'shadow_support':'Frozen full support minus11x11 eroded prior cream support; never derived from new weights',
        'print_instrument':{'ppi':300,'blur_sigma_mm':.08,'reason':'Owner instrument correction: print cannot carry source pixel grain; compare both linear-light images at physical print scale','interpolation':'fixed nominal inverse cylinder;1000PPI output interpolated','proof_composite':'linear_barycentric_3_endmember; not raw alpha-over','fringe':'same-alpha clean pale reference outside frozen shadow support; amber17..35deg,deltaE>4,visible threshold retained'},
        'negative_controls_valid':negative_ok,'results':results,'cost_usd':0,'production_ready':False}
    report['asset_hashes']={p.name:fa.sha(p) for p in destination.glob('*.png')}
    (destination/'fidelity-instrument.json').write_text(json.dumps(report,indent=2)+'\n')
    if not negative_ok:raise ValueError('Retained negative passed both gates; instrument invalid.')
    return report
