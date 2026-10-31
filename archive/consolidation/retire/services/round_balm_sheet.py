"""Engine-owned whole-object sheet; no model geometry or style dependencies."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import stick_carton, product_drawing
from .round_balm_calls import REPO, OUT, write, sha

SIZE = (1536, 1024)
MARGIN = 24
PANEL_IDS = ('body', 'cap', 'label', 'back', 'side_left', 'front', 'side_right', 'top_end', 'bottom_end')
FONT = REPO / 'bbrose_design_os/static/fonts/NotoSans-Regular.ttf'


def build(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out/'sheet.json').exists():
        raise ValueError('A paid-round sheet is immutable; build a new contract in a new directory')
    coords, fold = stick_carton.die(stick_carton.PRODUCTS['lip_balm'])
    faces = stick_carton.faces(coords)
    xmin, ymin, xmax, ymax = coords.cut_polygon.bounds
    # 3 mm outer die bleed, 24 px exterior/inter-row margins; caption bands 28 px.
    die_w, die_h = xmax - xmin + 6, ymax - ymin + 6
    s = min((SIZE[0] - 2*MARGIN - 2*MARGIN) / (58.5+58.5+18),
            (SIZE[0] - 2*MARGIN) / die_w,
            (SIZE[1] - 3*MARGIN - 3*28) / (42+die_h))
    sheet = Image.new('RGBA', SIZE, 'white')
    windows = Image.new('L', SIZE, 0)
    wd = ImageDraw.Draw(windows)
    guides = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    gd = ImageDraw.Draw(guides)
    font = ImageFont.truetype(str(FONT), 12)
    title = ImageFont.truetype(str(FONT), 15)
    panels = {}
    def rect_mm(box, origin):
        return [int(round(origin[0]+box[0]*s)), int(round(origin[1]+box[1]*s)),
                int(round(origin[0]+box[2]*s)), int(round(origin[1]+box[3]*s))]
    def guide_rect(box, colour=(105, 110, 119, 255)):
        gd.rectangle([box[0],box[1],box[2]-1,box[3]-1], outline=colour, width=1)
    def dashed(box):
        x0,y0,x1,y1=box
        for x in range(x0,x1,9):
            gd.line((x,y0,min(x+3,x1),y0),fill=(155,155,155,255))
            gd.line((x,y1,min(x+3,x1),y1),fill=(155,155,155,255))
        for y in range(y0,y1,9):
            gd.line((x0,y,x0,min(y+3,y1)),fill=(155,155,155,255))
            gd.line((x1,y,x1,min(y+3,y1)),fill=(155,155,155,255))
    front_centre = 58.5 - math.pi*18/2
    front_span = [front_centre-math.pi*18/6,front_centre+math.pi*18/6]
    row1w=(58.5*2+18)*s+2*MARGIN
    x=(SIZE[0]-row1w)/2
    y=MARGIN+28
    gd.text((MARGIN,MARGIN),'LIP BALM — nine panels · provisional',font=title,fill='black')
    for name,height in [('body',40),('cap',30),('label',16)]:
        width=18 if name=='label' else 58.5
        bleed=1
        full=rect_mm((0,0,width,height+2*bleed),(x,y))
        trim_box=(1,1,17,17) if name=='label' else (0,bleed,width,height+bleed)
        trim=rect_mm(trim_box,(x,y))
        shape='circle' if name=='label' else 'rectangle'
        if shape=='circle':
            wd.ellipse((full[0],full[1],full[2]-1,full[3]-1),fill=255)
            gd.ellipse((full[0],full[1],full[2]-1,full[3]-1),outline=(105,110,119,255))
            gd.ellipse((trim[0],trim[1],trim[2]-1,trim[3]-1),outline=(105,110,119,255))
        else:
            wd.rectangle((full[0],full[1],full[2]-1,full[3]-1),fill=255)
            guide_rect(full); guide_rect(trim)
            third=rect_mm((front_span[0],bleed+2,front_span[1],bleed+height-2),(x,y))
            dashed(third)
            seam=rect_mm((56.5,0,56.5,height+2*bleed),(x,y))
            gd.line((seam[0],seam[1],seam[2],seam[3]),fill=(145,145,145,255))
            gd.text((full[0],full[3]+3),'front third dashed · seam at back',font=font,fill='black')
        gd.text((full[0],full[1]-18),name,font=font,fill='black')
        panels[name]={'box_px':full,'trim_px':trim,'mm':[width,height+2*bleed],
                      'trim_mm':[16 if name=='label' else width,height],'bleed_tb_mm':bleed,'shape':shape}
        x+=width*s+MARGIN
    die_y=y+42*s+MARGIN+28
    origin=((SIZE[0]-die_w*s)/2+(3-xmin)*s,die_y+(3-ymin)*s)
    # Only the engine's six print faces are editable, not glue, tongues or dust flaps.
    for name,face in faces.items():
        box=rect_mm(face['box'],origin)
        wd.rectangle((box[0],box[1],box[2]-1,box[3]-1),fill=255)
        guide_rect(box)
        dashed(rect_mm(face['safe'],origin))
        if face['keep_out']:
            keep=face['keep_out'];cx=origin[0]+keep['cx']*s;cy=origin[1]+keep['cy']*s;r=keep['r_mm']*s
            gd.arc((cx-r,cy-r,cx+r,cy+r),0,180,fill=(155,155,155,255),width=1)
        if name in ('back','bottom_end'):
            safe=rect_mm(face['safe'],origin)
            for yy in range(safe[1],safe[3],12):
                gd.line((safe[0],yy,min(safe[2],safe[0]+8),min(safe[3],yy+8)),fill=(190,190,190,255))
        b=face['box']
        panels[name]={'box_px':box,'trim_px':box,'mm':[b[2]-b[0],b[3]-b[1]],
                      'trim_mm':[b[2]-b[0],b[3]-b[1]],'shape':'rectangle',
                      'die_box_mm':list(b),'safe_mm':list(face['safe']),
                      'cut_edges':list(face['cut']),'ground_mm':list(face['ground']),
                      'top_orientation_deg':180 if name=='top_end' else 0}
    # Real face/bleed windows, with all construction material excluded.
    from shapely.geometry import box as geo_box
    from shapely.ops import unary_union
    print_faces=unary_union([geo_box(*f['box']) for f in faces.values()]).intersection(coords.cut_polygon)
    bleed_windows=unary_union([geo_box(*f['ground']) for f in faces.values()])
    allowed=print_faces.union(bleed_windows.difference(coords.cut_polygon).intersection(coords.cut_polygon.buffer(3)))
    die_shape=Image.new('L',SIZE,0); dd=ImageDraw.Draw(die_shape)
    def points(seq):return [(int(round(origin[0]+a*s)),int(round(origin[1]+b*s))) for a,b in seq]
    for poly in ([allowed] if allowed.geom_type=='Polygon' else allowed.geoms):
        dd.polygon(points(poly.exterior.coords),fill=255)
        for ring in poly.interiors:dd.polygon(points(ring.coords),fill=0)
    a=np.array(windows); cut=np.array(die_shape)
    a[int(die_y):]=cut[int(die_y):]
    windows=Image.fromarray(a)
    gd.line(points(coords.cut_polygon.exterior.coords),fill=(65,65,65,255),width=1)
    for x0,y0,x1,y1 in coords.fold_lines+coords.slit_lines:
        gd.line(points([(x0,y0),(x1,y1)]),fill=(145,145,145,255),width=1)
    for name in ('back','bottom_end'):
        box=panels[name]['box_px']
        # Hatched legend beside the face, not painted over the future copy ground.
        lx=origin[0]-140
        yy=(box[1]+box[3])/2
        gd.text((lx,yy-15),name+' · copy zone',font=font,fill='black')
        gd.text((lx,yy), 'leave flat ground',font=font,fill='black')
        for yy2 in range(int(yy+19),int(yy+30),4):gd.line((lx,yy2,lx+115,yy2-8),fill=(170,170,170,255))
        gd.line((lx+120,yy+6,box[0]-4,yy+6),fill=(150,150,150,255))
    for name in ('back','side_left','front','side_right'):
        box=panels[name]['box_px']
        gd.text((box[0],int(die_y+die_h*s)+3),name,font=font,fill='black')
    for name in ('top_end','bottom_end'):
        box=panels[name]['box_px'];gd.text((box[2]+8,box[1]+5),name,font=font,fill='black')
    # Guide strokes stay opaque in both edit target and mask.
    editable=(np.array(windows)>0)&(np.array(guides)[...,3]==0)
    alpha=np.where(editable,0,255).astype('uint8')
    sheet.putalpha(Image.fromarray(alpha));sheet=Image.alpha_composite(sheet,guides)
    sheet.save(out/'sheet.png')
    mask=Image.new('RGBA',SIZE,'white');mask.putalpha(Image.fromarray(alpha));mask.save(out/'sheet-mask.png')
    windows.save(out/'sheet-windows.png')
    record={'schema':'r1_balm_sheet/2','size_px':list(SIZE),'px_per_mm':s,'margin_px':MARGIN,
            'scale_computation':{'available_height_px':SIZE[1]-3*MARGIN-84,'wrap_height_mm':42,'die_height_with_bleed_mm':die_h},
            'panels':panels,'die_bounds_mm':list(coords.cut_polygon.bounds),'die_origin_px':list(origin),
            'front_centre_mm':front_centre,'front_third_mm':front_span,
            'overlap_mm':58.5-math.pi*18,'die_version':stick_carton.TEMPLATE_VERSION,
            'engine_truth_note':'back is 20.45 × 74.35; long sides/front 20.45 × 73.45; ends 20 × 20.45 mm',
            'construction':'All glue/dust/tongue flaps and guide strokes opaque; never artwork.',
            'bleed_note':'Wrap bleed 1 mm TB. Carton engine ground/cut-edge 3 mm bleed outside the die; construction material remains opaque.',
            'sha256':{'sheet.png':sha(out/'sheet.png'),'sheet-mask.png':sha(out/'sheet-mask.png')}}
    write(out/'sheet.json',record)
    write(out/'sheet-verification.json',verify(out))
    return record


def verify(out=OUT):
    out=Path(out);r=json.loads((out/'sheet.json').read_text())
    target=np.array(Image.open(out/'sheet.png'));mask=np.array(Image.open(out/'sheet-mask.png'))
    windows=np.array(Image.open(out/'sheet-windows.png'))>0
    errors=[];aspects={}
    if target.shape!=(1024,1536,4) or not np.array_equal(target[...,3],mask[...,3]):errors.append('target/mask mismatch')
    if np.any((mask[...,3]==0)&~windows):errors.append('editable pixel outside windows')
    for name,p in r['panels'].items():
        x0,y0,x1,y1=p['box_px'];w,h=p['mm']
        err=abs((x1-x0)/(y1-y0)/(w/h)-1)
        aspects[name]=err
        if err>.02:errors.append(name+' aspect')
        if not (24<=x0<x1<=1512 and 24<=y0<y1<=1000):errors.append(name+' margin')
        if abs((x1-x0)-w*r['px_per_mm'])>1 or abs((y1-y0)-h*r['px_per_mm'])>1:errors.append(name+' scale')
    return {'passes':not errors,'errors':errors,'aspect_errors':aspects,
            'mask_only_windows':not bool(np.any((mask[...,3]==0)&~windows)), 'panel_count':len(r['panels'])}


def crops_and_drawing(dest, out=OUT):
    dest=Path(dest);contract=json.loads((Path(out)/'sheet.json').read_text())
    im=Image.open(dest/'picture.png').convert('RGB')
    if list(im.size)!=contract['size_px']:raise ValueError('Sheet size changed; never stretch it.')
    crops={}
    for name,p in contract['panels'].items():
        crop=im.crop(p['box_px'])
        if p['shape']=='circle':
            alpha=Image.new('L',crop.size,0);ImageDraw.Draw(alpha).ellipse((0,0,crop.width-1,crop.height-1),fill=255)
            crop.putalpha(alpha)
        crop.save(dest/(name+'.png'))
        err=abs(crop.width/crop.height/(p['mm'][0]/p['mm'][1])-1)
        crops[name]={'file':name+'.png','box_px':p['box_px'],'mm':p['mm'],'aspect_error':err,'qualifies':err<=.02}
    top=np.asarray(Image.open(dest/'cap.png').convert('RGB'))
    rgb=np.median(top[3:12,3:-3].reshape(-1,3),axis=0).astype(int)
    record=product_drawing.draw('Lip balm',[
        ('body',dest/'body.png',(58.5,42),1,40),('cap',dest/'cap.png',(58.5,32),1,30)],
        18,contract['front_centre_mm'],contract['overlap_mm'],'#'+''.join(f'{x:02x}' for x in rgb),dest/'drawing.png')
    write(dest/'drawing.json',record);write(dest/'crop.json',{'panels':crops,'qualifies':all(x['qualifies'] for x in crops.values())})
    return crops


def raw_geometry(dest,out=OUT):
    """Independent raw footprint observations; unknown edges never become observations.

    Final panel geometry is supplied by the fixed engine windows. This additionally
    catches a confidently measurable raw footprint over the owner's 2% limit.
    Touching carton faces cannot be separated reliably by colour at this scale.
    """
    import cv2
    dest=Path(dest);contract=json.loads((Path(out)/'sheet.json').read_text())
    rgb=np.asarray(Image.open(dest/'raw.png').convert('RGB'))
    rows={};failures=[]
    for name in PANEL_IDS:
        p=contract['panels'][name]
        if name not in ('body','cap','label'):
            rows[name]={'status':'unmeasured','reason':'Contiguous die faces; colour boundaries cannot independently establish trim edges. Engine mask controls final geometry.'}
            continue
        x0,y0,x1,y1=p['box_px'];pad=10
        left=max(0,x0-pad);top=max(0,y0-pad)
        roi=rgb[top:min(rgb.shape[0],y1+pad),left:min(rgb.shape[1],x1+pad)]
        samples=[]
        for threshold in (235,240,245):
            foreground=(roi.min(axis=2)<threshold).astype('uint8')
            if name=='label':
                # A thin circular border is a perimeter even when its interior
                # ink is disconnected. Opening erases it and measures the art.
                contours,_=cv2.findContours(foreground,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
                if not contours:continue
                contour=max(contours,key=cv2.contourArea)
                x,y,w,h=cv2.boundingRect(contour);area=cv2.contourArea(contour)
            else:
                foreground=cv2.morphologyEx(foreground,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
                n,labels,stats,_=cv2.connectedComponentsWithStats(foreground)
                if n<2:continue
                i=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]));x,y,w,h,area=stats[i]
            # A small ink mark on a pale panel is not the panel's perimeter.
            expected_area=(x1-x0)*(y1-y0)*(math.pi/4 if name=='label' else 1)
            if area<expected_area*.65 or w<(x1-x0)*.85 or h<(y1-y0)*.85:continue
            aspect=w/h
            if name=='label':
                if len(contour)<5:continue
                _,axes,_=cv2.fitEllipse(contour)
                if min(axes)<=0:continue
                aspect=max(axes)/min(axes)
            error=abs(aspect/(p['mm'][0]/p['mm'][1])-1)
            samples.append({'threshold':threshold,'box_px':[int(left+x),int(top+y),int(left+x+w),int(top+y+h)],'aspect_error':float(error)})
        if len(samples)!=3:
            rows[name]={'status':'unmeasured','reason':'No stable full-panel foreground perimeter; pale/quiet artwork may be intentional.'}
            continue
        low=min(r['aspect_error'] for r in samples);high=max(r['aspect_error'] for r in samples)
        status='over_limit' if low>.02 else ('within_limit' if high<=.02 else 'borderline')
        rows[name]={'status':status,'samples':samples,'aspect_error_range':[low,high],
                    'method':'foreground 235/240/245; wraps: 3px opening and full-footprint component; label: outer contour without opening, ellipse fit'}
        if status=='over_limit':failures.append(name)
    manual_path=dest/'manual-geometry.json'
    if manual_path.exists():
        manual=json.loads(manual_path.read_text())
        if manual['raw_sha256']!=sha(dest/'raw.png'):raise ValueError('Manual geometry refers to changed raw image')
        for observation in manual['observations']:
            name=observation['panel'];left,top,right,bottom=observation['box_px']
            if name not in PANEL_IDS or not (0<=left<right<=1536 and 0<=top<bottom<=1024):
                raise ValueError('Invalid manually observed panel bounds')
            width,height=contract['panels'][name]['mm']
            error=abs(((right-left)/(bottom-top))/(width/height)-1)
            if error>.02 and name not in failures:failures.append(name)
            rows[name]['manual_observation']=dict(observation,aspect_error=error)
    result={'panels':rows,'measured_over_limit':failures,'all_panels_independently_measured':False,
            'scope':'Raw artwork footprint diagnostics; final crops keep the engine geometry and are never stretched.'}
    write(dest/'raw-geometry.json',result)
    crop=json.loads((dest/'crop.json').read_text())
    crop['raw_geometry']=result
    crop['qualifies']=all(p['qualifies'] for p in crop['panels'].values()) and not failures
    write(dest/'crop.json',crop)
    return result


def protected_edit(parent, generated, edit_mask, destination):
    """Only paste editable pixels; retain and audit untouched parent bytes exactly."""
    src=np.array(Image.open(parent).convert('RGBA'));new=np.array(Image.open(generated).convert('RGBA'))
    mask=np.array(Image.open(edit_mask).convert('RGBA'))[...,3]
    if src.shape!=new.shape or src.shape[:2]!=mask.shape:raise ValueError('Edit dimensions changed')
    edit=mask==0;result=src.copy();result[edit]=new[edit]
    Image.fromarray(result).save(destination)
    actual=np.array(Image.open(destination).convert('RGBA'))
    return {'protected_pixels':int((~edit).sum()),'protected_byte_identical':bool(np.array_equal(src[~edit],actual[~edit])),
            'raw_changed_protected_pixels':int(np.any(src[~edit]!=new[~edit],axis=1).sum()),
            'method':'masked pixel compositing; raw provider reply retained'}
