"""Independent measurements of emitted proof pixels, including a retained v1 control."""
import json
import math
from collections import Counter
from pathlib import Path
import cv2
import fitz
import numpy as np
from PIL import Image
from apps.pipeline.services import fidelity_assets as fa
from apps.pipeline.services.fidelity_master import render_artwork,validate_spec,font_data


def lab(rgb):
    a=np.asarray(rgb,dtype=float)/255
    a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
    xyz=np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]])@a
    v=xyz/np.array([.95047,1,1.08883]);f=np.where(v>(6/29)**3,np.cbrt(v),v/(3*(6/29)**2)+4/29)
    return np.array([116*f[1]-16,500*(f[0]-f[1]),200*(f[1]-f[2])])


def delta_e_2000(a,b):
    l1,a1,b1=map(float,a);l2,a2,b2=map(float,b)
    c1,c2=math.hypot(a1,b1),math.hypot(a2,b2);cm=(c1+c2)/2
    g=.5*(1-math.sqrt(cm**7/(cm**7+25**7)))
    ap1,ap2=(1+g)*a1,(1+g)*a2;cp1,cp2=math.hypot(ap1,b1),math.hypot(ap2,b2)
    h1=math.degrees(math.atan2(b1,ap1))%360;h2=math.degrees(math.atan2(b2,ap2))%360
    dl=l2-l1;dc=cp2-cp1;dh=h2-h1
    if cp1*cp2==0:dh=0
    elif dh>180:dh-=360
    elif dh < -180:dh+=360
    dH=2*math.sqrt(cp1*cp2)*math.sin(math.radians(dh/2))
    lm=(l1+l2)/2;cm=(cp1+cp2)/2
    if cp1*cp2==0:hm=h1+h2
    elif abs(h1-h2)<=180:hm=(h1+h2)/2
    elif h1+h2<360:hm=(h1+h2+360)/2
    else:hm=(h1+h2-360)/2
    t=1-.17*math.cos(math.radians(hm-30))+.24*math.cos(math.radians(2*hm))+.32*math.cos(math.radians(3*hm+6))-.20*math.cos(math.radians(4*hm-63))
    sl=1+.015*(lm-50)**2/math.sqrt(20+(lm-50)**2);sc=1+.045*cm;sh=1+.015*cm*t
    rt=-2*math.sqrt(cm**7/(cm**7+25**7))*math.sin(math.radians(60*math.exp(-((hm-275)/25)**2)))
    return math.sqrt((dl/sl)**2+(dc/sc)**2+(dH/sh)**2+rt*(dc/sc)*(dH/sh))


def inspect_pixels(ink,projection,measurement):
    placements=[];colours=[]
    for e in measurement['elements']:
        x0,y0,x1,y1=e['bbox_px'];pad=4 if e['id'] in ('benefit','care','logo_rule','name_rule') else 8
        xa,ya,xb,yb=x0-pad,y0-pad,x1+pad,y1+pad
        alpha=ink[ya:yb,xa:xb,3]
        # Alpha defines printed ink; glass and amber cannot masquerade as lettering.
        occupied=alpha>96
        if e['id']=='swoosh':
            # The swoosh bbox overlaps the x-range of some copy, not the actual swoosh.
            # Exclude those independently measured text/logo regions from this element's bounds.
            for other in measurement['elements']:
                if other['id']=='swoosh':continue
                q0,q1,q2,q3=other['bbox_px']
                left,right=max(0,q0-2-xa),min(occupied.shape[1],q2+2-xa)
                upper,lower=max(0,q1-2-ya),min(occupied.shape[0],q3+2-ya)
                if left<right and upper<lower:occupied[upper:lower,left:right]=False
        if not np.any(occupied):
            placements.append({'id':e['id'],'present':False,'passed':False,'reason':'No exported ink in the measured region.'});continue
        yy,xx=np.nonzero(occupied);actual=[int(xx.min()+xa),int(yy.min()+ya),int(xx.max()+xa+1),int(yy.max()+ya+1)]
        a,b,c,d=actual
        shift=math.hypot(((a+c-x0-x1)/2)*fa.XS,((b+d-y0-y1)/2)*fa.YS)
        scales=[100*abs((c-a)/(x1-x0)-1),100*abs((d-b)/(y1-y0)-1)]
        # Thin original rules are ~3sourcepx; ±1px alpha quantisation is measured explicitly.
        quantisation_mm=math.hypot(fa.XS,fa.YS)
        passed=shift<=1 and max(scales)<=3
        placements.append({'id':e['id'],'present':True,'concept_bbox_px':e['bbox_px'],'exported_bbox_px':actual,
                           'concept_bbox_mm':e['projected_bbox_mm'],'exported_bbox_mm':[(a-505)*fa.XS,(1470-d)*fa.YS,(c-505)*fa.XS,(1470-b)*fa.YS],
                           'delta_position_mm':shift,'delta_scale_percent':scales,'passed':passed,'pixel_quantisation_mm':quantisation_mm})
        if e['id']=='swoosh':
            rgb=np.median(projection[936:941,644:649].reshape(-1,3),axis=0)
        else:
            solid=alpha>245
            rgb=np.median(ink[ya:yb,xa:xb,:3][solid if np.any(solid) else occupied],axis=0)
        de=delta_e_2000(e['colour']['Lab_D65'],lab(rgb))
        colours.append({'id':e['id'],'concept_srgb':e['colour']['srgb_255'],'master_srgb':rgb.tolist(),'deltaE2000':de,'tolerance':4,'passed':de<=4})
    for i,sample in enumerate(measurement['ground']['samples']):
        x,y=sample['xy_px'];rgb=np.median(projection[y-2:y+3,x-2:x+3].reshape(-1,3),axis=0)
        de=delta_e_2000(sample['Lab_D65'],lab(rgb))
        colours.append({'id':'material_ground_'+str(i+1),'concept_srgb':sample['srgb_255'],'master_srgb':rgb.tolist(),'deltaE2000':de,'tolerance':6,'passed':de<=6})
    ref=np.asarray(Image.open(fa.CONCEPT).convert('RGB'))
    mask=np.asarray(Image.open(fa.ROOT/'docs/audit/day-4/measurement-assets/swoosh-reference-support.png'))
    mask=cv2.dilate(mask,np.ones((7,7),np.uint8))
    value=fa.ssim(ref,projection,mask)
    return {'placement':placements,'colour':colours,'swoosh_ssim':value,'swoosh_threshold':.85,
            'all_elements_present':all(p['present'] for p in placements),'placement_passed':all(p['passed'] for p in placements),
            'colour_passed':all(c['passed'] for c in colours),'swoosh_passed':value>=.85}


def inspect_bundle(folder):
    folder=Path(folder);measurement=json.loads(fa.MEASUREMENT.read_text())
    spec=validate_spec(json.loads((folder/'design-spec.json').read_text()))
    ink=fa.project(render_artwork(folder/'artwork.pdf'))
    material=np.asarray(Image.open(fa.ROOT/'docs/audit/day-4/measurement-assets/material-field.png').convert('RGB'))
    projection=fa.composite(material,ink)
    result=inspect_pixels(ink,projection,measurement)
    cached=np.asarray(Image.open(folder/'projected-master.png').convert('RGB'))
    result['cached_projection_matches_pdf']=bool(np.array_equal(projection,cached))
    with fitz.open(folder/'artwork.pdf') as pdf:
        actual=pdf[0].read_contents().upper()
        required=[e['copy'] for e in measurement['elements'] if e['copy']]
        logical=all(('FEFF'+t.encode('utf-16-be').hex()).upper().encode() in actual for t in required)
        image_rows=pdf[0].get_images(full=True)
        expected=Counter((r['text'],font_data(r['font_role'])['postscript']) for line in spec['graph']['lines'] for r in line['runs'])
        emitted=Counter((chr(char[0]),span['font']) for span in pdf[0].get_texttrace() for char in span['chars'])
        result['actual_live_glyphs_and_fonts_match']=emitted==expected
        result['live_copy_logical_actualtext']=logical and emitted==expected
        result['rgba_soft_mask_embedded']=any(row[1]>0 for row in image_rows)
        result['embedded_fonts']=[row[3] for row in pdf[0].get_fonts() if pdf.extract_font(row[0])[3]]
        result['page_count']=len(pdf)
        result['page_mm']=[v/(72/25.4) for v in (pdf[0].rect.width,pdf[0].rect.height)]
    result['measured_fidelity_passed']=all(result[k] for k in ('all_elements_present','placement_passed','colour_passed','swoosh_passed','live_copy_logical_actualtext','cached_projection_matches_pdf'))
    return result


def negative_control(destination):
    """The retained Day2 flat artwork and actual bottle drawing, with fixed mm alignment."""
    destination=Path(destination);old=fa.ROOT/'docs/audit/day-2/master'
    with fitz.open(old/'comparison-at-100-percent.pdf') as pdf:
        clip=fitz.Rect(70,46,99,154)*(72/25.4)
        pix=pdf[1].get_pixmap(matrix=fitz.Matrix(4.5,4.5),clip=clip,alpha=False)
        crop=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
    photo=np.full((1536,1024,3),255,np.uint8)
    photo[95:1470,319:691]=cv2.resize(crop,(372,1375),interpolation=cv2.INTER_AREA)
    oldart=render_artwork(old/'artwork.pdf')
    flat=np.zeros((math.ceil(fa.HEIGHT/25.4*1000),math.ceil(fa.WIDTH/25.4*1000),4),np.uint8)
    width=round(32/fa.WIDTH*flat.shape[1]);height=round(60/fa.HEIGHT*flat.shape[0]);x=(flat.shape[1]-width)//2;y=round((fa.HEIGHT-67)/fa.HEIGHT*flat.shape[0])
    flat[y:y+height,x:x+width]=cv2.resize(oldart,(width,height),interpolation=cv2.INTER_AREA)
    report=inspect_pixels(fa.project(flat),photo,json.loads(fa.MEASUREMENT.read_text()))
    report['required_copy_on_front']=False;report['measured_fidelity_passed']=False
    report['independent_hard_failures']=['Benefit, care and volume are on the back, contrary to accepted concept.','Opaque ivory field and dark type replace amber material and white lettering.']
    if report['placement_passed'] and report['colour_passed'] and report['swoosh_passed']:
        raise ValueError('The instrument is broken: retained Day2 redesign passed.')
    Image.fromarray(photo).save(destination/'day2-negative-control.png')
    return report
