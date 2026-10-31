"""Measured, front-only concept-147 master. Historical DesignSpec v1 is untouched."""
from pathlib import Path
import base64
import copy
import hashlib
import io
import json
import math
import shutil
import xml.etree.ElementTree as ET
import zipfile
import cv2
import fitz
import numpy as np
from PIL import Image
from fontTools.ttLib import TTFont as FTFont
from fontTools.pens.boundsPen import BoundsPen
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from apps.pipeline.services import fidelity_assets as fa

SCHEMA = 'design_spec/2.0'
PARENT = '1b0d5a9c760fa03c2e2662f58f38f3f6b014874a09266533f25cfdefc17f6467'
PRESET = fa.ROOT / 'docs/audit/day-4/measurement-assets'
FONTS = {
 'title':fa.APP/'static/fonts/brand2026/Instrument_Serif/InstrumentSerif-Regular.ttf',
 'support':fa.APP/'static/fonts/brand2026/Barlow_Condensed/BarlowCondensed-Regular.ttf',
 'arabic':fa.APP/'static/fonts/NotoNaskhArabic-Regular.ttf',
 'symbol':fa.APP/'static/fonts/NotoSans-Regular.ttf',
}
LOGO = fa.APP/'docs/brand/mark/bbrose-logo.svg'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def font_data(role, fonts=None):
    path=(FONTS if fonts is None else fonts)[role]
    ft=FTFont(path)
    return {'path':path,'font':ft,'glyphs':ft.getGlyphSet(),'cmap':ft.getBestCmap(),
            'upem':ft['head'].unitsPerEm,'family':ft['name'].getDebugName(1),'postscript':ft['name'].getDebugName(6)}


def glyph_metric(data,ch):
    name=data['cmap'][ord(ch)]
    pen=BoundsPen(data['glyphs']);data['glyphs'][name].draw(pen)
    bounds=pen.bounds
    scale=1000/data['upem']
    return [v*scale for v in bounds] if bounds else None,data['font']['hmtx'][name][0]*scale


def build_graph(measurement):
    from apps.dielines.exporters.text_intl import shape_ar
    fonts={role:font_data(role) for role in FONTS}
    lines=[]
    for e in measurement['elements']:
        if e['copy'] is None:
            continue
        role='title' if e['id'] in ('SUN','REPAIR') else 'arabic' if e['id']=='arabic' else 'support'
        visual=shape_ar(e['copy'],keep_harakat=True) if role=='arabic' else e['copy']
        cursor=0.;glyphs=[]
        for ch in visual:
            used=role if ord(ch) in fonts[role]['cmap'] else 'symbol'
            box,advance=glyph_metric(fonts[used],ch)
            glyphs.append({'char':ch,'role':used,'box':box,'cursor':cursor})
            cursor+=advance+(300 if e['id']=='SERUM' else 0)
        ink=[(g['cursor']+g['box'][0],g['box'][1],g['cursor']+g['box'][2],g['box'][3]) for g in glyphs if g['box']]
        xmin,ymin,xmax,ymax=min(v[0] for v in ink),min(v[1] for v in ink),max(v[2] for v in ink),max(v[3] for v in ink)
        x0,y0,x1,y1=e['bbox_px'];fx=(x1-x0)/(xmax-xmin)
        # Measured repair: the Arabic antialiased export overran the original ink by 1px.
        # Half-pixel height correction is 0.039mm, within the declared scale tolerance.
        fy=(y1-y0-(.5 if e['id']=='arabic' else 0))/(ymax-ymin)
        baseline=y0+ymax*fy;runs=[]
        for g in glyphs:
            if g['box'] is None:
                continue
            a,b,c,d=g['box'];left=x0+(g['cursor']+a-xmin)*fx;right=x0+(g['cursor']+c-xmin)*fx
            sx=float((fa.arc(right)-fa.arc(left))/(c-a));sy=fy*fa.YS
            origin=float(fa.arc(left))-a*sx
            runs.append({'text':g['char'],'font_role':g['role'],'x_mm':fa.WIDTH/2+origin,'baseline_z_mm':(fa.BOTTOM-baseline)*fa.YS,
                         'scale_x_mm_per_1000pt_unit':sx,'scale_y_mm_per_1000pt_unit':sy,
                         'source_glyph_bbox_px':[left,baseline-d*fy,right,baseline-b*fy]})
        lines.append({'id':e['id'],'logical_text':e['copy'],'colour':e['colour']['srgb_255'],'runs':runs,
                      'baseline_z_mm':(fa.BOTTOM-baseline)*fa.YS,'measured_baseline_z_mm':e['baseline_z_mm'],
                      'classification':role,'tracking_source':'measured-spaced SERUM' if e['id']=='SERUM' else 'font advances fitted to measured whole-line bounds; no redesign'})
    for data in fonts.values():data['font'].close()
    return {'schema':'fidelity_graph/1.0','width_mm':fa.WIDTH,'height_mm':fa.HEIGHT,'lines':lines,
            'elements':copy.deepcopy(measurement['elements']),'raster_asset':'assets/swoosh-flat.png',
            'logo_asset':'assets/bbrose-logo.svg','layer_roles':['SWOOSH','LIVE TYPE','LOGO','RULES'],
            'materials_outside_print_artwork':True}


def make_spec():
    measurement=json.loads(fa.MEASUREMENT.read_text());graph=build_graph(measurement)
    return {'schema_version':SCHEMA,'revision':2,'parent_hash':PARENT,'template_id':'concept-147-exact-fidelity',
            'concept_sha256':fa.sha(fa.CONCEPT),'measurement_sha256':fa.sha(fa.MEASUREMENT),'instrument_sha256':fa.sha(fa.INSTRUMENT),
            'stock':{'diameter_mm':29,'height_mm':108,'capacity_ml':30,'height_datum':'unresolved','comparison_convention':'108 mm overall only'},
            'materials':{'body':'clear_glass','fill':'amber_liquid','closure':'chrome_spray','amber_is_ink':False},
            'elevation_proposal':{'authority':'concept_measurement_plus_owner_conservative_cap','source':'concept-147-measurement.json',
                'profile':[{'id':'body','z0':0,'z1':(1470-585)*fa.YS,'r0':14.5,'r1':14.5},
                           {'id':'shoulder','z0':(1470-585)*fa.YS,'z1':(1470-546)*fa.YS,'r0':14.5,'r1':282*fa.XS/2},
                           {'id':'collar','z0':(1470-546)*fa.YS,'z1':(1470-493)*fa.YS,'r0':282*fa.XS/2,'r1':282*fa.XS/2},
                           {'id':'cap','z0':(1470-493)*fa.YS,'z1':108,'r0':10.5,'r1':10.5}],
                'cap_width_image_mm':247*fa.XS,'cap_width_occluder_mm':21,'not_stock_drawing':True},
            'identity_zones':[{'element_id':e['id'],'flat_bbox_mm':e['flat_bbox_mm']} for e in measurement['elements'] if e['id'] in measurement['identity_elements']],
            'decoration_region_mm':measurement['decoration_region_mm'],
            'surface':{'id':'body.front','width_mm':fa.WIDTH,'height_mm':fa.HEIGHT,'z_bottom_mm':0,'arc_degrees':180,'method':'unselected','safe_area_shrinking':False},
            'back':{'artwork':None,'copy':[]},'graph':graph,
            'projection_assets':{name:fa.sha(PRESET/name) for name in ('material-field.png','swoosh-reference-support.png','swoosh-source-matte.png','removed-ink-mask.png')},
            'assets':{'swoosh':{'path':'assets/swoosh-flat.png','sha256':fa.sha(PRESET/'swoosh-flat.png')},'logo':{'path':'assets/bbrose-logo.svg','sha256':fa.sha(LOGO)}},
            'fonts':{role:{'filename':path.name,'sha256':fa.sha(path)} for role,path in FONTS.items()},
            'decoration_proposal':{'candidate':'clear no-label-look film, CMYK plus opaque white, unselected by owner',
                                  'assumed_mockup_stack':['clear adhesive/film not visibly simulated','white underbase beneath swoosh only','continuous-tone CMYK swoosh','opaque white live type and vector mark'],
                                  'constraints':['Supplier printable body and shoulder limit unknown; no artwork cropped to fit.','Film edge/gloss and adhesive on glass may differ from direct print.','White opacity over amber must be proofed.','Fine lines and registration require supplier measurement; no line thickened today.'],
                                  'screen_print_alternative':'Continuous-tone cream shading would require halftone/process separations plus white; a few flat spot inks cannot reproduce the existing swoosh shading exactly.'},
            'physical_deviations':[],'review_state':'owner_review_pending','production_ready':False}


def validate_spec(data,expected_hash=None):
    if data['schema_version']!=SCHEMA or data['revision']!=2 or data['parent_hash']!=PARENT:
        raise ValueError('The fidelity master must preserve its published revision-1 parent.')
    if expected_hash is not None and digest(data)!=expected_hash:raise ValueError('Fidelity specification hash changed.')
    if data['measurement_sha256']!=fa.sha(fa.MEASUREMENT) or data['instrument_sha256']!=fa.sha(fa.INSTRUMENT):
        raise ValueError('Measurement or fidelity instrument changed; a new revision is required.')
    if data['concept_sha256']!=fa.sha(fa.CONCEPT):raise ValueError('The accepted concept bytes changed.')
    expected=make_spec()
    if data!=expected:raise ValueError('The measured revision was altered; no silent layout or copy substitution is permitted.')
    return data


def _logo_svg(element):
    root=ET.parse(LOGO).getroot()
    a,z0,b,z1=element['flat_bbox_mm'];x=a+fa.WIDTH/2;y=fa.HEIGHT-z1
    root.attrib.update(x=str(x),y=str(y),width=str(b-a),height=str(z1-z0),preserveAspectRatio='none')
    colour='#'+''.join(f'{round(v):02x}' for v in element['colour']['srgb_255'])
    for p in root.iter():
        if p.tag.endswith(('path','polygon','rect','circle','ellipse')):p.set('fill',colour)
    return root


def svg(graph, *, fonts=None, rasters=None):
    fonts=FONTS if fonts is None else fonts
    rasters=[('SWOOSH',PRESET/'swoosh-flat.png')] if rasters is None else rasters
    ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
    el=lambda tag,attrs={}:ET.Element('{'+ns+'}'+tag,{k:str(v) for k,v in attrs.items()})
    root=el('svg',{'width':str(fa.WIDTH)+'mm','height':str(fa.HEIGHT)+'mm','viewBox':f'0 0 {fa.WIDTH} {fa.HEIGHT}'})
    style=el('style')
    style.text='\n'.join("@font-face{font-family:'%s';src:url(data:font/ttf;base64,%s)}"%(font_data(role,fonts)['family'],base64.b64encode(path.read_bytes()).decode()) for role,path in fonts.items())
    root.append(style)
    for name,path in rasters:
        g=el('g',{'id':name});g.append(el('image',{'x':0,'y':0,'width':fa.WIDTH,'height':fa.HEIGHT,'href':'data:image/png;base64,'+base64.b64encode(Path(path).read_bytes()).decode()}));root.append(g)
    g=el('g',{'id':'LIVE_TYPE'})
    for line in graph['lines']:
        lg=el('g',{'id':line['id'],'aria-label':line['logical_text']})
        for run in line['runs']:
            sx,sy=run['scale_x_mm_per_1000pt_unit'],run['scale_y_mm_per_1000pt_unit']
            t=el('text',{'transform':f"matrix({sx} 0 0 {sy} {run['x_mm']} {fa.HEIGHT-run['baseline_z_mm']})",'font-size':1000,'font-family':font_data(run['font_role'],fonts)['family'],'fill':'#'+''.join(f'{round(v):02x}' for v in line['colour']),'xml:space':'preserve'})
            t.text=run['text'];lg.append(t)
        g.append(lg)
    root.append(g)
    for e in graph['elements']:
        if e['id']=='logo':root.append(_logo_svg(e))
        if e['id'] in ('logo_rule','name_rule'):
            a,z0,b,z1=e['flat_bbox_mm'];root.append(el('rect',{'id':e['id'],'x':a+fa.WIDTH/2,'y':fa.HEIGHT-z1,'width':b-a,'height':z1-z0,'fill':'#'+''.join(f'{round(v):02x}' for v in e['colour']['srgb_255'])}))
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def emit_pdf(graph,path, *, fonts=None, rasters=None):
    fonts=FONTS if fonts is None else fonts
    rasters=[('SWOOSH',PRESET/'swoosh-flat.png')] if rasters is None else rasters
    names={role:'Fidelity-'+role+'-'+fa.sha(font)[:12] for role,font in fonts.items()}
    for role,font in fonts.items():pdfmetrics.registerFont(TTFont(names[role],str(font)))
    c=Canvas(str(path),pagesize=(fa.WIDTH*mm,fa.HEIGHT*mm),pageCompression=1)
    for name,image in rasters:
        c._code.append('/Span << /LayerRole ('+name+') >> BDC')
        c.drawImage(str(image),0,0,fa.WIDTH*mm,fa.HEIGHT*mm,mask='auto')
        c._code.append('EMC')
    for line in graph['lines']:
        c._code.append('/Span << /ActualText <FEFF'+line['logical_text'].encode('utf-16-be').hex().upper()+'> >> BDC')
        c.setFillColorRGB(*[v/255 for v in line['colour']])
        for run in line['runs']:
            c.saveState();c.translate(run['x_mm']*mm,run['baseline_z_mm']*mm)
            c.scale(run['scale_x_mm_per_1000pt_unit']*mm,run['scale_y_mm_per_1000pt_unit']*mm)
            c.setFont(names[run['font_role']],1000);c.drawString(0,0,run['text']);c.restoreState()
        c._code.append('EMC')
    for e in graph['elements']:
        if e['id'] in ('logo_rule','name_rule'):
            a,z0,b,z1=e['flat_bbox_mm'];c.setFillColorRGB(*[v/255 for v in e['colour']['srgb_255']]);c.rect((a+fa.WIDTH/2)*mm,z0*mm,(b-a)*mm,(z1-z0)*mm,fill=1,stroke=0)
    c.save()
    # The approved SVG remains vector content; no tracing or rasterized mark.
    logo=next(e for e in graph['elements'] if e['id']=='logo')
    element=_logo_svg(logo);element.attrib.update(x='0',y='0')
    raw=ET.tostring(element)
    with fitz.open(stream=raw,filetype='svg') as logo_doc:logo_pdf=logo_doc.convert_to_pdf()
    temp=Path(path).with_suffix('.with-logo.pdf')
    with fitz.open(path) as doc,fitz.open(stream=logo_pdf,filetype='pdf') as mark:
        a,z0,b,z1=logo['flat_bbox_mm'];box=fitz.Rect((a+fa.WIDTH/2)*mm,(fa.HEIGHT-z1)*mm,(b+fa.WIDTH/2)*mm,(fa.HEIGHT-z0)*mm)
        doc[0].show_pdf_page(box,mark,0,keep_proportion=False)
        doc.save(temp)
    temp.replace(path)


def render_artwork(path,dpi=1000):
    with fitz.open(path) as doc:
        pix=doc[0].get_pixmap(dpi=dpi,alpha=True)
        rgba=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4).copy()
    # MuPDF emits premultiplied alpha; return straight RGBA before cylindrical resampling.
    a=rgba[:,:,3:4].astype(float);rgba[:,:,:3]=np.clip(np.where(a>0,rgba[:,:,:3].astype(float)*255/np.maximum(a,1),0),0,255)
    return rgba


def compile_bundle(data,destination):
    spec=validate_spec(data);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    assets=destination/'assets';assets.mkdir()
    shutil.copyfile(PRESET/'swoosh-flat.png',assets/'swoosh-flat.png');shutil.copyfile(LOGO,assets/'bbrose-logo.svg')
    for role,path in FONTS.items():
        shutil.copyfile(path,assets/path.name)
        license_path=path.parent/'OFL.txt'
        if role=='symbol':license_path=fa.APP/'static/fonts/OFL.txt'
        if role=='arabic':license_path=fa.APP/'static/fonts/NotoNaskhArabic-Bold.OFL.txt'
        shutil.copyfile(license_path,assets/(role+'-OFL.txt'))
    (destination/'design-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    (destination/'design-graph.json').write_text(json.dumps(spec['graph'],ensure_ascii=False,indent=2)+'\n')
    (destination/'artwork.svg').write_bytes(svg(spec['graph']))
    emit_pdf(spec['graph'],destination/'artwork.pdf')
    shutil.copyfile(destination/'artwork.pdf',destination/'artwork-pdf-compatible.ai')
    rgba=render_artwork(destination/'artwork.pdf');Image.fromarray(rgba).save(destination/'artwork.png')
    material=np.asarray(Image.open(PRESET/'material-field.png').convert('RGB'))
    projection=fa.composite(material,fa.project(rgba));Image.fromarray(projection).save(destination/'projected-master.png')
    return {'spec_hash':digest(spec),'revision':2,'parent_hash':PARENT,'production_ready':False}
