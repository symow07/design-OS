"""D1 measured surface masters: parametric fields, one vector device, live copy.

Face-local coordinates use millimetres from the upper left. Print and scene
textures derive from this graph; a concept picture never supplies geometry.
"""
from pathlib import Path
import base64, copy, json, math, shutil, xml.etree.ElementTree as ET
import cv2, fitz, numpy as np
from PIL import Image
from scipy.optimize import least_squares
from scipy.interpolate import PchipInterpolator
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import fidelity_assets as fa, fidelity_master as fm, day5_master as dm, cairo_measured as cm
from .day6_measurement import ROOT, D1, write
from .matte_colour import lab, de


def add_measurements():
    target=ROOT/'concept-D1-measurement-addendum.json'
    if target.exists():return json.loads(target.read_text())
    m=json.loads((ROOT/'concept-D1-measurement.json').read_text());im=np.array(Image.open(D1).convert('RGB'))
    points=np.array([[840,119]]+m['faces'][0]['gesture_centreline_px'],float);profiles=[]
    for i,p in enumerate(points):
        tangent=points[min(i+1,len(points)-1)]-points[max(0,i-1)];normal=np.array([-tangent[1],tangent[0]])
        normal/=np.linalg.norm(normal);offsets=np.linspace(-90,90,1801);xy=p[None,:]+offsets[:,None]*normal
        valid=(xy[:,0]>=690)&(xy[:,0]<=841)&(xy[:,1]>=49)&(xy[:,1]<485)
        sample=im[np.clip(np.round(xy[:,1]).astype(int),0,1535),np.clip(np.round(xy[:,0]).astype(int),0,1023)]
        mask=valid&(sample[:,0]>220)&(sample[:,1]>185)&(sample[:,2]>120)
        runs=[];start=None
        for j,v in enumerate(np.r_[mask,False]):
            if v and start is None:start=j
            elif not v and start is not None:
                runs.append((start,j));start=None
        candidates=[r for r in runs if r[1]-r[0]>3]
        if not candidates:profiles.append({'xy_px':p.tolist(),'measured':False,'reason':'Tip/edge clipped'});continue
        selected=min(candidates,key=lambda r:abs(float(np.mean(offsets[r[0]:r[1]]))))
        a,b=xy[selected[0]],xy[selected[1]-1]
        delta=(b-a)*np.array([180/659,100/437])
        profiles.append({'xy_px':p.tolist(),'xy_mm':[(p[0]-183)*180/659,(p[1]-48)*100/437],
                         'normal_px':normal.tolist(),'edge_points_px':[a.tolist(),b.tolist()],
                         'normal_width_mm':float(np.linalg.norm(delta)),'measured':True,
                         'rule':'Nearest continuous lit cream interval along local normal; parallel hairline remains a separate device feature'})
    def sample(x,y):return {'xy_px':[x,y],'window_px':11,'srgb':np.median(im[y-5:y+6,x-5:x+6].reshape(-1,3),axis=0).tolist()}
    result={'schema':'day6_measurement_addendum/1','base_measurement_sha256':fa.sha(ROOT/'concept-D1-measurement.json'),
            'source_sha256':fa.sha(D1),'header_width_profile':profiles,'header_tip_px':[840,119],
            'riser3_fit_region_px':[162,865,862,1235],
            'riser3_deep_shadow_samples_status':'Original y1160 retained as photographed shadow diagnostics, not silently called lit print colour',
            'riser3_held_out':[sample(x,1040) for x in (335,492,653)],
            'lip_transform':{'source_box_px':[114,1284,908,1485],'destination_mm':[180,6],
                             'formula':'x=(px-114)*180/794; y=(py-1284)*6/201; severe vertical compression disclosed'},
            'gradient_fit_policy':'Fit a2/3-stop diagonal linear field to recorded RGB samples; report every residual and held-out point. Photographed lighting may exceed the print-field tolerance.'}
    write(target,result);return result


def field_at(field, xy):
    xy=np.asarray(xy,float);a=np.array(field['start_mm']);b=np.array(field['end_mm']);t=np.clip((xy-a)@(b-a)/np.sum((b-a)**2),0,1)
    return np.stack([np.interp(t,[s['offset'] for s in field['stops']],[s['srgb'][i] for s in field['stops']]) for i in range(3)],axis=-1)


def fit_field(face):
    w,h=face['size_mm'];box=face.get('source_box_px');samples=face['field_samples']
    if not samples:return None
    xy=np.array([[(s['xy_px'][0]-box[0])*w/(box[2]-box[0]),(s['xy_px'][1]-box[1])*h/(box[3]-box[1])] for s in samples])
    values=np.array([s['srgb'] for s in samples]);best=None
    for degrees in range(0,360,5):
        direction=np.array([math.cos(math.radians(degrees)),math.sin(math.radians(degrees))])
        corners=np.array([[0,0],[w,0],[0,h],[w,h]]);lo,hi=(corners@direction).min(),(corners@direction).max()
        t=np.clip((xy@direction-lo)/(hi-lo),0,1);weights=np.stack([np.maximum(1-2*t,0),1-abs(2*t-1),np.maximum(2*t-1,0)],axis=1)
        colours=np.clip(np.linalg.lstsq(weights,values,rcond=None)[0],0,255);predicted=weights@colours
        error=float(np.mean(de(lab(predicted),lab(values))**2))
        if best is None or error<best[0]:best=(error,degrees,lo,hi,direction,colours)
    _,degrees,lo,hi,direction,colours=best
    field={'kind':'linear_gradient','direction_degrees_from_right_down':degrees,'start_mm':(direction*lo).tolist(),'end_mm':(direction*hi).tolist(),
           'stops':[{'offset':t,'srgb':c.tolist()} for t,c in zip([0,.5,1],colours)],'space':'sRGB review, press profile unconfirmed'}
    actual=field_at(field,xy);errors=de(lab(actual),lab(values))
    field['fit_samples']=[dict(s,face_xy_mm=p.tolist(),fitted_srgb=c.tolist(),deltaE2000=float(e),passed=float(e)<=6) for s,p,c,e in zip(samples,xy,actual,errors)]
    field['all_samples_passed']=bool(np.max(errors)<=6)
    return field


def line_graph(element, height):
    identifier=element['id'];logical=element['copy'];role='title' if identifier in ('SUN','REPAIR') else 'arabic' if identifier=='arabic' else 'support'
    data=fm.font_data(role,dm.fonts());glyphs=[];cursor=0
    if role=='arabic':
        measurement=json.loads((dm.CAIRO/'measurement.json').read_text());shape=cm.shape(dm.fonts()['arabic'])
        for row in shape['rows']:
            if not row['bounds']:continue
            ch=chr(measurement['glyph_aliases'][row['g']]);box,advance=fm.glyph_metric(data,ch)
            glyphs.append({'char':ch,'cursor':row['cursor']*1000/shape['units_per_em'],'box':box,'shaped_glyph_name':row['g']})
    else:
        for ch in logical:
            box,advance=fm.glyph_metric(data,ch)
            if box:glyphs.append({'char':ch,'cursor':cursor,'box':box})
            cursor+=advance+(300 if identifier=='SERUM' else 0)
    bounds=np.array([[g['cursor']+g['box'][0],g['box'][1],g['cursor']+g['box'][2],g['box'][3]] for g in glyphs])
    xmin,ymin,xmax,ymax=bounds[:,0].min(),bounds[:,1].min(),bounds[:,2].max(),bounds[:,3].max()
    x0,y0,x1,y1=element['bbox_mm'];sx=(x1-x0)/(xmax-xmin);sy=(y1-y0)/(ymax-ymin);baseline=y0+ymax*sy
    runs=[{'text':g['char'],'font_role':role,'x_mm':x0+(g['cursor']-xmin)*sx,'baseline_z_mm':height-baseline,
           'scale_x_mm_per_1000pt_unit':sx,'scale_y_mm_per_1000pt_unit':sy,
           **({'shaped_glyph_name':g['shaped_glyph_name']} if 'shaped_glyph_name' in g else {})} for g in glyphs]
    return {'id':identifier,'logical_text':logical,'colour':element['colour_srgb'],'runs':runs,'measured_bbox_mm':element['bbox_mm'],
            'measured_baseline_y_mm':element.get('baseline_y_mm'),'realized_baseline_y_mm':baseline,
            'type_deviation':'Pinned licensed bottle face fitted to source ink bounds; generated letter anatomy is not traced'}


def main_band(xx):
    """Longest contiguous run of cream columns in one row: the main band, never the hairline beside it."""
    breaks=np.flatnonzero(np.diff(xx)>1);starts=np.r_[0,breaks+1];ends=np.r_[breaks,len(xx)-1]
    k=int(np.argmax(ends-starts));return int(xx[starts[k]]),int(xx[ends[k]])


def posed_device(device, measurement, addendum):
    """One common longitudinal warp; each face clips its segment, no new trace."""
    cream=np.array(Image.open(dm.INK/'swoosh-cream.png'))[:,:,3]>=128
    components,_=cv2.findContours(cream.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    main=max(components,key=cv2.contourArea);mask=np.zeros_like(cream,dtype=np.uint8);cv2.drawContours(mask,[main],-1,1,-1)
    ys=[];centres=[];widths=[]
    for y in range(mask.shape[0]):
        xx=np.flatnonzero(mask[y])
        if len(xx)>1:
            # Revision 2 (Day 6, after the per-surface instrument): the pose centres the MAIN cream band on each
            # measured knot; the parallel hairline is a separate device feature under the measurement's own rule,
            # so it may not pull the centre (revision 1 centred the whole row and missed the measured path by up to 2.07 mm).
            a,b=main_band(xx)
            ys.append(y*fa.HEIGHT/mask.shape[0]);centres.append((a+b)/2*fa.WIDTH/mask.shape[1]);widths.append((b-a)*fa.WIDTH/mask.shape[1])
    lo,hi=min(ys),max(ys);total=220.;start=100*(119-48)/437
    knots=[[start,180*(840-183)/659,0.8]]
    for point in addendum['header_width_profile'][1:]:
        if point.get('measured'):knots.append([point['xy_mm'][1],point['xy_mm'][0],max(.8,point['normal_width_mm'])])
    # Bottle-covered/extra row sections are composed and named as such.
    knots += [[125,124,13],[154,114,15],[181,129,14],[208,153,12],[214,153,12],[220,151,12]]
    knots=np.array(sorted(knots));centre=PchipInterpolator(knots[:,0],knots[:,1]);width=PchipInterpolator(knots[:,0],knots[:,2])
    roles=[]
    for role in device['roles']:
        paths=[]
        for path in role['paths']:
            points=np.array(path['points_mm']);source_y=points[:,1];v=start+(source_y-lo)/(hi-lo)*(total-start)
            source_c=np.interp(source_y,ys,centres);source_w=np.maximum(.15,np.interp(source_y,ys,widths))
            x=centre(v)+(points[:,0]-source_c)/source_w*width(v)
            paths.append(dict(path,points_mm=np.stack([x,v],axis=1).tolist()))
        roles.append(dict(role,paths=paths))
    return {'device_sha256':fa.sha(ROOT/'device/device.json'),'roles':roles,'knots_mm':knots.tolist(),
            'mapping':'One longitudinal pose of the same traced vertices; measured header normal widths; lower rows composed through occlusion; clipped per face.',
            'centring':'main cream band per source row (longest contiguous run); the parallel hairline is a separate device feature (measurement rule)',
            'continuous_strip_height_mm':total,'surface_offsets_mm':{'header.front':0,'riser.3.front':100,'riser.2.front':154,'lip.front':208,'riser.1.front':214}}


def logo_svg(element):
    root=ET.parse(fm.LOGO).getroot();x0,y0,x1,y1=element['bbox_mm']
    root.attrib.update(x=str(x0),y=str(y0),width=str(x1-x0),height=str(y1-y0),preserveAspectRatio='none')
    colour='#'+''.join(f'{round(v):02x}' for v in element['colour_srgb'])
    for p in root.iter():
        if p.tag.endswith(('path','polygon','rect','circle','ellipse')):p.set('fill',colour)
    return root


def svg(graph, *, vectors_only=False):
    ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
    def el(tag,attrs=None):return ET.Element('{'+ns+'}'+tag,{k:str(v) for k,v in (attrs or {}).items()})
    w,h=graph['width_mm'],graph['height_mm'];root=el('svg',{'width':f'{w}mm','height':f'{h}mm','viewBox':f'0 0 {w} {h}'})
    defs=el('defs');clip=el('clipPath',{'id':'surface_clip'});clip.append(el('rect',{'width':w,'height':h}));defs.append(clip)
    field=graph.get('field')
    if field:
        grad=el('linearGradient',{'id':'field','gradientUnits':'userSpaceOnUse','x1':field['start_mm'][0],'y1':field['start_mm'][1],'x2':field['end_mm'][0],'y2':field['end_mm'][1]})
        for stop in field['stops']:grad.append(el('stop',{'offset':stop['offset'],'stop-color':'#'+''.join(f'{round(v):02x}' for v in stop['srgb'])}))
        defs.append(grad)
    root.append(defs);style=el('style');style.text='\n'.join("@font-face{font-family:'%s';src:url(data:font/ttf;base64,%s)}"%(fm.font_data(role,dm.fonts())['family'],base64.b64encode(path.read_bytes()).decode()) for role,path in dm.fonts().items());root.append(style)
    if field:root.append(el('rect',{'id':'FIELD','width':w,'height':h,'fill':'url(#field)'}))
    for role in graph.get('device_roles',[]):
        group=el('g',{'id':role['role'],'clip-path':'url(#surface_clip)'})
        path=' '.join('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in p['points_mm'])+' Z' for p in role['paths'])
        group.append(el('path',{'fill':'#'+''.join(f'{round(v):02x}' for v in role['colour_srgb']),'fill-rule':'evenodd','d':path}));root.append(group)
    for element in graph.get('elements',[]):
        if element['id']=='logo':root.append(logo_svg(element))
        elif element['id'].endswith('rule'):
            a,b,c,d=element['bbox_mm'];root.append(el('rect',{'id':element['id'],'x':a,'y':b,'width':c-a,'height':d-b,'fill':'#'+''.join(f'{round(v):02x}' for v in element['colour_srgb'])}))
    if not vectors_only:
        for line in graph['lines']:
            group=el('g',{'id':line['id'],'aria-label':line['logical_text']})
            for run in line['runs']:
                t=el('text',{'transform':f"matrix({run['scale_x_mm_per_1000pt_unit']} 0 0 {run['scale_y_mm_per_1000pt_unit']} {run['x_mm']} {h-run['baseline_z_mm']})",'font-size':1000,'font-family':fm.font_data(run['font_role'],dm.fonts())['family'],'fill':'#'+''.join(f'{round(v):02x}' for v in line['colour'])});t.text=run['text'];group.append(t)
            root.append(group)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def emit_pdf(graph, path, *, vectors_only=False):
    w,h=graph['width_mm'],graph['height_mm'];c=Canvas(str(path),pagesize=(w*mm,h*mm));c.setTitle(graph.get('surface_id','BBROSE artwork'))
    names={r:'Day6-'+r+'-'+fa.sha(p)[:12] for r,p in dm.fonts().items()}
    for role,font in dm.fonts().items():pdfmetrics.registerFont(TTFont(names[role],str(font)))
    c.saveState();clip=c.beginPath();clip.rect(0,0,w*mm,h*mm);c.clipPath(clip,stroke=0,fill=0)
    field=graph.get('field')
    if field:
        a,b=field['start_mm'],field['end_mm'];c.linearGradient(a[0]*mm,(h-a[1])*mm,b[0]*mm,(h-b[1])*mm,
            [tuple(v/255 for v in s['srgb']) for s in field['stops']],positions=[s['offset'] for s in field['stops']])
    for role in graph.get('device_roles',[]):
        c.setFillColorRGB(*[v/255 for v in role['colour_srgb']]);pathobj=c.beginPath()
        for p in role['paths']:
            points=p['points_mm'];pathobj.moveTo(points[0][0]*mm,(h-points[0][1])*mm)
            for x,y in points[1:]:pathobj.lineTo(x*mm,(h-y)*mm)
            pathobj.close()
        c.drawPath(pathobj,fill=1,stroke=0,fillMode=0)
    c.restoreState()
    for element in graph.get('elements',[]):
        if element['id'].endswith('rule'):
            a,b,d,e=element['bbox_mm'];c.setFillColorRGB(*[v/255 for v in element['colour_srgb']]);c.rect(a*mm,(h-e)*mm,(d-a)*mm,(e-b)*mm,fill=1,stroke=0)
    if not vectors_only:
        for line in graph['lines']:
            c._code.append('/Span << /ActualText <FEFF'+line['logical_text'].encode('utf-16-be').hex().upper()+'> >> BDC')
            c.setFillColorRGB(*[v/255 for v in line['colour']])
            for run in line['runs']:
                c.saveState();c.translate(run['x_mm']*mm,run['baseline_z_mm']*mm);c.scale(run['scale_x_mm_per_1000pt_unit']*mm,run['scale_y_mm_per_1000pt_unit']*mm)
                c.setFont(names[run['font_role']],1000);c.drawString(0,0,run['text']);c.restoreState()
            c._code.append('EMC')
    c.save()
    logo=next((e for e in graph.get('elements',[]) if e['id']=='logo'),None)
    if logo:
        raw=logo_svg(logo);raw.attrib.update(x='0',y='0')
        with fitz.open(stream=ET.tostring(raw),filetype='svg') as mark:pdf=mark.convert_to_pdf()
        temporary=Path(path).with_suffix('.logo.pdf')
        with fitz.open(path) as doc,fitz.open(stream=pdf,filetype='pdf') as mark:
            doc[0].show_pdf_page(fitz.Rect(logo['bbox_mm'])*mm,mark,0,keep_proportion=False);doc.save(temporary)
        temporary.replace(path)


def build(destination,*,revision=1,parent_bindings=None,correction=None):
    add=add_measurements();m=json.loads((ROOT/'concept-D1-measurement.json').read_text());device=json.loads((ROOT/'device/device.json').read_text())
    parents={s['surface_id']:s for s in (json.loads(Path(parent_bindings).read_text())['surfaces'] if parent_bindings else [])}
    if not device['contour_passed']:raise ValueError('Device contour failed')
    dst=Path(destination);dst.mkdir(parents=True,exist_ok=False);pose=posed_device(device,m,add);write(dst/'device-pose.json',pose)
    # One continuous front strip: no separately tuned seam colours. Source
    # lighting is measured as residual rather than baked into extra gradients.
    combined=[]
    for face in (m['faces'][0],m['faces'][1],m['faces'][3]):
        box=face['source_box_px'];w,h=face['size_mm'];offset=pose['surface_offsets_mm'][face['surface_id']]
        for sample in face['field_samples']:
            x,y=sample['xy_px'];combined.append(dict(sample,source_surface=face['surface_id'],source_xy_px=[x,y],
                xy_px=[(x-box[0])*w/(box[2]-box[0]),offset+(y-box[1])*h/(box[3]-box[1])]))
    global_field=fit_field({'size_mm':[180,220],'source_box_px':[0,0,180,220],'field_samples':combined})
    write(dst/'field-fit.json',{'field':global_field,'measurement_sha256':fa.sha(ROOT/'concept-D1-measurement.json'),
                             'continuity':'One3-stop linear gradient on the220mm front artwork strip; each face is a1:1 clip. Side fields composed from the same field.'})
    specs=[]
    for face in m['faces']:
        identity=face['surface_id'];w,h=face['size_mm'];field=copy.deepcopy(global_field)
        offset=pose['surface_offsets_mm'].get(identity,100)
        for endpoint in ('start_mm','end_mm'):field[endpoint]=[field[endpoint][0]*w/180,field[endpoint][1]-offset]
        elements=copy.deepcopy(face.get('elements',[]));lines=[line_graph(e,h) for e in elements if e.get('copy')]
        elements=[e for e in elements if not e.get('copy')]
        roles=[]
        if identity in pose['surface_offsets_mm']:
            offset=pose['surface_offsets_mm'][identity]
            for role in pose['roles']:
                roles.append(dict(role,paths=[dict(p,points_mm=[[x,y-offset] for x,y in p['points_mm']]) for p in role['paths']]))
        graph={'surface_id':identity,'width_mm':w,'height_mm':h,'lines':lines,'elements':elements,'field':field,'device_roles':roles}
        spec={'schema_version':'surface_spec/day6-1','revision':revision,'surface_id':identity,'graph':graph,
              **({'parent_spec_hash':parents[identity]['spec_hash'],'parent_pdf_sha256':parents[identity]['pdf_sha256'],'correction':correction} if identity in parents else {}),
              'measurement_sha256':fa.sha(ROOT/'concept-D1-measurement.json'),'measurement_addendum_sha256':fa.sha(ROOT/'concept-D1-measurement-addendum.json'),
              'device_sha256':fa.sha(ROOT/'device/device.json'),'source_status':face['status'],'deviations':face['deviations'],
              'review_state':'designer_review','production_ready':False,
              'fonts':{r:{'filename':p.name,'sha256':fa.sha(p),'family':fm.font_data(r,dm.fonts())['family'],'postscript':fm.font_data(r,dm.fonts())['postscript']} for r,p in dm.fonts().items()}}
        folder=dst/identity;folder.mkdir();assets=folder/'assets';assets.mkdir()
        for r,p in dm.fonts().items():
            shutil.copyfile(p,assets/p.name);shutil.copyfile(dm.ROOT/'master/assets'/(r+'-OFL.txt'),assets/(r+'-OFL.txt'))
        shutil.copyfile(fm.LOGO,assets/'bbrose-logo.svg');write(folder/'design-spec.json',spec);write(folder/'design-graph.json',graph)
        (folder/'artwork.svg').write_bytes(svg(graph));(folder/'native-vectors.svg').write_bytes(svg(graph,vectors_only=True))
        emit_pdf(graph,folder/'artwork.pdf');emit_pdf(graph,folder/'native-vectors.pdf',vectors_only=True)
        shutil.copyfile(folder/'artwork.pdf',folder/'artwork-pdf-compatible.ai')
        with fitz.open(folder/'artwork.pdf') as doc:doc[0].get_pixmap(dpi=300,alpha=False).save(folder/'artwork.png')
        specs.append({'surface_id':identity,'size_mm':[w,h],'spec_hash':fm.digest(spec),'pdf_sha256':fa.sha(folder/'artwork.pdf'),'source_status':face['status']})
    write(dst/'surface-bindings.json',{'schema':'day6_surface_bindings/1','revision':revision,'surfaces':specs,'review_state':'designer_review',
                                        **({'parent_bindings_sha256':fa.sha(Path(parent_bindings)),'correction':correction} if parent_bindings else {})})
    return specs
