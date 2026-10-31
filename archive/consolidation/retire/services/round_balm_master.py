"""Round 1 B: HAYAT's preserved raster and live-type, five-layer PDF-compatible AI.

No Illustrator-native claim: the independent read-back parses the actual PDF fonts,
text operators, OCG usage/locks, image placement and isolated-layer pixels.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path
import fitz
import numpy as np
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import arabic_reshaper
from bidi.algorithm import get_display

from .round_files_export import FONT_PATHS, glyph_metrics, raster, rgb, set_layers, shaped

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / 'docs/rounds/r1-balm/master'
PICK = REPO / 'docs/rounds/r1-balm/developments/D1/A'
PT = 72 / 25.4
LAYERS = ('plate', 'type', 'mark', 'die', 'guides')
MARK = REPO / 'bbrose_design_os/docs/brand/mark/bbrose-logo.svg'
INK = '#F4E9E5'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rel(path): return str(Path(path).resolve().relative_to(REPO))
def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def point_size_for_height(copy, height_mm, face='latin'):
    box=glyph_metrics(copy,face)['box_em']
    return height_mm*PT/(box[3]-box[1])

class SurfaceBuilder:
    """One top-left millimetre coordinate system; box_mm = x0,y0,x1,y1."""
    def __init__(self, size_mm, title, trim_mm=None):
        self.size_mm=list(size_mm); self.title=title; self.doc=fitz.open()
        self.ocg={n:self.doc.add_ocg(n,on=n not in ('die','guides')) for n in LAYERS}
        for n in LAYERS:
            printable=n not in ('die','guides')
            self.doc.xref_set_key(self.ocg[n],'Usage',f'<</Print <</PrintState /{"ON" if printable else "OFF"}>> /Export <</ExportState /{"ON" if printable else "OFF"}>>>>')
        locked='['+' '.join(f'{self.ocg[n]} 0 R' for n in ('die','guides'))+']'
        self.doc.xref_set_key(self.doc.pdf_catalog(),'OCProperties/D/Locked',locked)
        self.page=self.doc.new_page(width=size_mm[0]*PT,height=size_mm[1]*PT)
        self.page.set_trimbox(fitz.Rect(*[v*PT for v in trim_mm]) & self.page.rect if trim_mm else self.page.rect)
        self.page.set_bleedbox(self.page.rect)
        self.fonts=dict(FONT_PATHS); self.rows=[]; self.elements=[]
        for name,path in self.fonts.items(): self.page.insert_font(fontname=name,fontfile=str(path))
    def add_plate(self,path,box_mm,name='plate'):
        self.page.insert_image(fitz.Rect(*[v*PT for v in box_mm]),filename=str(path),keep_proportion=False,oc=self.ocg['plate'])
        self.elements.append({'name':name,'layer':'plate','kind':'raster','box_mm':list(box_mm),'source':rel(path),'sha256':sha(path)})
    def text(self,copy,box_mm,*,face='latin',size_pt=5,color=INK,align='center',name=None,shrink=True):
        display=shaped(copy,face); m=glyph_metrics(copy,face); b=m['box_em']; requested=size_pt
        bw,bh=(box_mm[2]-box_mm[0])*PT,(box_mm[3]-box_mm[1])*PT
        max_size=min(bw/max(m['advance_em'],.0001),bh/max(b[3]-b[1],.0001))
        if shrink:size_pt=max(5,min(size_pt,max_size))
        else:size_pt=max(5,size_pt)
        aw=m['advance_em']*size_pt
        x=box_mm[0]*PT + ((bw-aw)/2 if align=='center' else bw-aw if align=='right' else 0)
        baseline=box_mm[1]*PT+(bh-(b[3]-b[1])*size_pt)/2+b[3]*size_pt
        self.page.insert_text((x,baseline), display, fontname=face, fontsize=size_pt,color=rgb(color),oc=self.ocg['type'])
        xref=self.page.get_contents()[-1]
        stream=self.doc.xref_stream(xref)
        actual=('FEFF'+copy.encode('utf-16-be').hex()).upper()
        self.doc.update_stream(xref,b'/Span << /ActualText <'+actual.encode()+b'> >> BDC\n'+stream+b'\nEMC\n')
        inkbox=[(x+b[0]*size_pt)/PT,(baseline-b[3]*size_pt)/PT,(x+b[2]*size_pt)/PT,(baseline-b[1]*size_pt)/PT]
        cap=glyph_metrics('H' if face=='latin' else 'ا',face)['box_em']
        row={'name':name or copy,'copy':copy,'display':display,'face':face,'font_path':rel(self.fonts[face]),'size_pt':round(size_pt,5),'requested_size_pt':round(requested,5),'ink_height_mm':round((b[3]-b[1])*size_pt/PT,5),'cap_height_mm':round((cap[3]-cap[1])*size_pt/PT,5),'ink_box_mm':inkbox,'zone_mm':list(box_mm),'baseline_mm':baseline/PT,'at_least_5pt':size_pt>=5,'cap_floor_2_5mm':(cap[3]-cap[1])*size_pt/PT>=2.5-1e-5,'overflow':bool(aw>bw+.01 or (b[3]-b[1])*size_pt>bh+.01),'missing_glyphs':m['missing'],'color':color,'logical_actual_text':copy}
        self.rows.append(row);self.elements.append({'name':row['name'],'layer':'type','kind':'live_type','box_mm':inkbox,'copy':copy})
        return row
    def svg(self,path,box_mm,*,layer='mark',name=None,color=None):
        source=Path(path).read_text()
        if color:
            source=re.sub(r'#[0-9a-fA-F]{6}',color,source)
            source=re.sub(r'fill="(?:black|white)"',f'fill="{color}"',source)
        with fitz.open(stream=source.encode(),filetype='svg') as svg:
            with fitz.open(stream=svg.convert_to_pdf(),filetype='pdf') as doc:
                self.page.show_pdf_page(fitz.Rect(*[v*PT for v in box_mm]),doc,0,keep_proportion=False,oc=self.ocg[layer])
        self.elements.append({'name':name or Path(path).stem,'layer':layer,'kind':'vector','box_mm':list(box_mm),'source':rel(path),'sha256':sha(path)})
    def rect(self,box_mm,layer='guides',color=(0,.7,.8),width=.2,fill=None):
        self.page.draw_rect(fitz.Rect(*[v*PT for v in box_mm]),color=rgb(color),fill=rgb(fill) if fill else None,width=width,oc=self.ocg[layer])
    def line(self,p0_mm,p1_mm,layer='guides',color=(0,.7,.8),width=.2):
        self.page.draw_line(fitz.Point(*[v*PT for v in p0_mm]),fitz.Point(*[v*PT for v in p1_mm]),color=rgb(color),width=width,oc=self.ocg[layer])
    def circle(self,center_mm,radius_mm,layer='die',color=(1,0,.5),width=.2):
        self.page.draw_circle(fitz.Point(*[v*PT for v in center_mm]),radius_mm*PT,color=rgb(color),width=width,oc=self.ocg[layer])
    def save(self,path,flat_path=None):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        self.doc.set_metadata({'title':self.title,'creator':'HAYAT Round 1 B preservation master','subject':'Process colour; PDF-compatible Illustrator interchange. Native Illustrator validation is separately reported.'})
        self.doc.save(str(path),garbage=3,deflate=True)
        self.doc.close()
        check=read_back_ai(path,self.elements,self.rows)
        contrast=contrast_report(path,self.rows)
        if flat_path:render_flat(path,flat_path)
        return {'file':rel(path),'sha256':sha(path),'ai_check':check,'type':self.rows,'contrast':contrast,'elements':self.elements}


def render_flat(path,out,clip_mm=None,layers=('plate','type','mark'),dpi=300):
    with fitz.open(str(path)) as d:
        set_layers(d,layers)
        clip=fitz.Rect(*[v*PT for v in clip_mm]) if clip_mm else None
        arr=raster(d,dpi,clip)
    Path(out).parent.mkdir(parents=True,exist_ok=True);Image.fromarray(arr).save(out,dpi=(dpi,dpi))

def read_back_ai(path,elements=None,rows=None):
    elements=elements or [];rows=rows or []
    with fitz.open(str(path)) as d:
        page=d[0];ocgs=d.get_ocgs();catalog=d.pdf_catalog()
        locked=d.xref_get_key(catalog,'OCProperties/D/Locked')[1]
        layers=[]
        for x,oc in ocgs.items():
            usage=d.xref_get_key(x,'Usage')[1]
            if re.fullmatch(r'\d+ 0 R',usage): usage=d.xref_object(int(usage.split()[0]))
            layers.append({'name':oc['name'],'default_visible':x in d.get_layer().get('on',[]),'locked':bool(re.search(r'\b'+str(x)+r' 0 R\b',locked)),'print_on':'/PrintState/ON' in usage.replace(' ',''),'usage':usage})
        fonts=[]
        for f in page.get_fonts(full=True):
            basename,ext,typ,data=d.extract_font(f[0]);fonts.append({'xref':f[0],'name':basename,'type':typ,'embedded_bytes':len(data),'embedded':len(data)>0,'sha256':hashlib.sha256(data).hexdigest() if data else None})
        raw=b'\n'.join(d.xref_stream(x) or b'' for x in range(1,d.xref_length()) if d.xref_is_stream(x))
        texts=page.get_text('text')
        actual=[bytes.fromhex(x.decode()).decode('utf-16-be').lstrip('\ufeff') for x in re.findall(rb'/ActualText\s*<([A-Fa-f0-9]+)>',raw)]
        glyphs=sum(len(t['chars']) for t in page.get_texttrace())
        images=[{'width_px':i['width'],'height_px':i['height'],'bbox_pt':list(i['bbox']),'effective_ppi_x':round(i['width']*72/(i['bbox'][2]-i['bbox'][0]),3),'effective_ppi_y':round(i['height']*72/(i['bbox'][3]-i['bbox'][1]),3)} for i in page.get_image_info()]
    normtext=' '.join(unicodedata.normalize('NFKC',texts).split())
    def has_copy(copy):
        n=' '.join(unicodedata.normalize('NFKC',copy).split())
        return copy in actual or n in normtext or n[::-1] in normtext
    presence=[]
    for element in elements:
        with fitz.open(str(path)) as d:
            set_layers(d,{element['layer']});box=fitz.Rect(*[v*PT for v in element['box_mm']]);box=box & d[0].rect
            arr=raster(d,300,box)
            ink=float((arr.min(2)<245).mean()) if arr.size else 0
            presence.append({'name':element['name'],'layer':element['layer'],'kind':element['kind'],'ink_share':round(ink,6),'present':ink>0,'logical_text_present':has_copy(element['copy']) if element.get('copy') else None})
    checks={'five_named_layers':[r['name'] for r in layers]==list(LAYERS),'die_guides_locked_nonprinting':all(r['locked'] and not r['print_on'] for r in layers if r['name'] in ('die','guides')),'fonts_embedded':bool(fonts) and all(r['embedded'] for r in fonts),'live_text_glyphs':glyphs>0,'all_expected_elements':all(x['present'] and x['logical_text_present'] is not False for x in presence),'all_expected_copy':all(has_copy(x['copy']) for x in rows),'no_missing_glyphs':all(not x.get('missing_glyphs') for x in rows)}
    native_path=Path(path).parent/'native-checks'/(Path(path).stem+'.json')
    native=json.loads(native_path.read_text()) if native_path.exists() else {}
    native_valid=bool(native.get('holds') and native.get('final_sha256')==sha(path))
    return {'schema':'round1b_ai_readback/1','method':'Fresh PyMuPDF PDF parse; actual font streams, text glyph operators, OCG lock/Print usage, each expected element rastered on its own isolated layer. Not an Illustrator application open/save.','layers':layers,'fonts':fonts,'images':images,'extracted_text':texts,'actual_text':actual,'live_glyph_count':glyphs,'elements':presence,'checks':checks,'pdf_compatible_holds':all(checks.values()),'native_illustrator_validated':native_valid,'native_census':rel(native_path) if native_valid else None,'native_illustrator_note':'Actual Illustrator 30.0 native save: live text frames, correct fonts, embedded raster and five locked/printable layer states independently censused; matching final file hash.' if native_valid else 'PDF-compatible .ai; no matching successful actual Illustrator census for these exact bytes.'}

def contrast_report(path,rows):
    with fitz.open(str(path)) as d:
        set_layers(d,{'plate'});arr=raster(d,300)
    def lum(c):
        c=np.asarray(c)/255.;c=np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
        return c@np.array([.2126,.7152,.0722])
    records=[]
    for r in rows:
        x0,y0,x1,y1=[round(v*300/25.4) for v in r['ink_box_mm']];bg=arr[max(0,y0):max(0,y1),max(0,x0):max(0,x1)]
        if not bg.size:records.append({'name':r['name'],'unmeasured':'ink outside page'});continue
        a=lum(bg);b=lum(np.array(rgb(r['color']))*255);rat=(np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)
        records.append({'name':r['name'],'minimum_ratio':round(float(rat.min()),3),'mean_ratio':round(float(rat.mean()),3),'ratio_4_5_report_only':bool(rat.min()>=4.5),'method':'WCAG relative-luminance ratio against every plate pixel behind the line ink bounding box; not a creative gate.'})
    return records

def clean_live_type(panel, boxes_source_px):
    """Glyph-local removal; pink paint never enters the cream-letter mask."""
    import cv2
    base=np.asarray(Image.open(OUT/f'cleaning/{panel}-after.png').convert('RGB')).copy()
    mask=np.zeros(base.shape[:2],np.uint8)
    for box in boxes_source_px:
        x0,y0,x1,y1=[int(v*2) for v in box]
        crop=base[y0:y1,x0:x1]
        # Only pale, near-neutral type/separator pixels; red painted strokes excluded.
        letters=(crop.min(2)>115)&((crop.max(2)-crop.min(2))<65)
        mask[y0:y1,x0:x1]|=letters.astype(np.uint8)*255
    mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    cleaned=cv2.inpaint(base,mask,7,cv2.INPAINT_TELEA)
    folder=OUT/'type-cleaning';folder.mkdir(exist_ok=True)
    for name,array in [('before',base),('after',cleaned),('mask',mask)]:Image.fromarray(array).save(folder/f'{panel}-{name}.png')
    rec={'panel':panel,'method':'Cream glyph mask within measured small-line boxes, dilated four upscaled pixels to include the dark embossed rim; local Telea radius 7 px. Painting excluded by red chroma. No rectangle replaced.','boxes_source_px':boxes_source_px,'changed_share':round(float(np.any(base!=cleaned,axis=2).mean()),6),'mask_share':round(float((mask>0).mean()),6),'before':rel(folder/f'{panel}-before.png'),'after':rel(folder/f'{panel}-after.png'),'mask':rel(folder/f'{panel}-mask.png')}
    return cleaned,rec

def prepare_wrap(panel,arr):
    from apps.pipeline.services.round_files_faces import delta_e00, srgb_to_lab
    from scipy.ndimage import gaussian_filter1d
    k=arr.shape[1]/58.5;overlap=58.5-np.pi*18
    # Crop the sketch's drawn 1mm top/bottom bleed, then extend the trim's own edge.
    bleed=max(1,round(arr.shape[0]/(42 if panel=='body' else 32)))
    trim=arr[bleed:-bleed].copy();full=np.pad(trim,((bleed,bleed),(0,0),(0,0)),mode='edge')
    band=round(2*k);ov=round(overlap*k);read=round(k)
    def measure(a):
        left=gaussian_filter1d(a[:,ov:ov+read].astype(float).mean(1),.5*k,axis=0)
        right=gaussian_filter1d(a[:,-read:].astype(float).mean(1),.5*k,axis=0)
        return delta_e00(srgb_to_lab(left),srgb_to_lab(right))
    before=measure(full);target=full[:,ov:ov+band][:,::-1].astype(float)
    w=np.linspace(0,1,band)[None,:,None]
    full[:,-band:]=np.round(full[:,-band:]*(1-w)+target*w).astype(np.uint8)
    after=measure(full)
    dest=OUT/f'composed-plates/{panel}.png';dest.parent.mkdir(exist_ok=True);Image.fromarray(full).save(dest)
    return dest,{'trim_mm':[58.5,40 if panel=='body' else 30],'page_mm':[58.5,42 if panel=='body' else 32],'bleed_top_bottom_mm':1,'bleed_method':'Crop source bleed row band then extend exact trim edge; no interior resize.','bleed_rows':bleed,'bleed_top_identical':bool(np.all(full[:bleed]==full[bleed])),'bleed_bottom_identical':bool(np.all(full[-bleed:]==full[-bleed-1])),'seam':{'band_mm':2,'overlap_mm':float(overlap),'method':'Right back edge feathered over 2 mm to mirrored corresponding left overlap; join profile mean over 1 mm, sigma 0.5 mm, CIEDE2000.','before_mean':round(float(before.mean()),4),'after_mean':round(float(after.mean()),4),'after_max':round(float(after.max()),4),'holds':bool(after.mean()<=2)},'ppi_x':round(k*25.4,3),'ppi_300_holds':k*25.4>=300}

def font_record():
    book=json.loads((REPO/'docs/audit/day-8/fonts/type-book.json').read_text());faces={}
    for script,family in [('latin','DM Sans'),('arabic','Almarai')]:
        row=next(r for group in book[script].values() for r in group if r['family']==family)
        faces[script]={'family':family,'style':'Regular','path':rel(FONT_PATHS[script]),'sha256':sha(FONT_PATHS[script]),'pool':'GRANTED','source':'Day 8 type book / Day 7 GRANTED pool','licence':row['licence'],'choice_basis':'D1/A small copy has plain, even-weight sans strokes and rounded bowls. DM Sans retains its open Latin counters and compact capitals; Almarai retains the simple rounded connected Arabic. Compared with geometric Montserrat/Poppins and square Droid Kufi; no rescue face inherited.','shaping':'Presentation-form joining and bidi; isolated presentation forms absent from cmap canonically map to their identical basic-codepoint glyphs. Every actual string checked for missing glyphs.' if script=='arabic' else 'Native Unicode glyphs, full face embedded.'}
    return {'schema':'round1b_type/1','faces':faces,'surfaces':{s:{'latin':faces['latin'],'arabic':faces['arabic']} for s in ['body','cap','label','carton']},'scope':'One Latin and one Arabic face per surface; cap logotype vector and mark are not font substitutions. The label has Latin tint only, Arabic face is available but no unused Arabic copy is added.','floor_pt':5,'cap_floor_mm':2.5}

def add_wrap_guides(s,height):
    s.rect((0,1,58.5,height-1),layer='die',color=(1,0,.5))
    s.rect((.05,.05,58.45,height-.05));s.rect((20.8009,2,39.6504,height-2));s.rect((56.5,1,58.5,height-1));s.rect((20.8009,3,39.6504,height-3))

def add_net(s,center_x,top,width=18.8495,name='net'):
    # Two lines preserve all content while meeting physical figure/sign heights.
    # The flat-topped 4 is shorter than the overshooting 0/5. Calibrate the
    # minimum digit, with 1 micron allowance for native PDF point rounding.
    figure_size=point_size_for_height('4',2.001)
    sign_size=point_size_for_height('℮',3)
    fwidth=glyph_metrics('4.5 g')['advance_em']*figure_size/PT
    ewidth=glyph_metrics('℮')['advance_em']*sign_size/PT
    total=fwidth+.7+ewidth;left=center_x-total/2
    fb=glyph_metrics('4.5 g')['box_em'];baseline=top+3
    r1=s.text('4.5 g',(left,baseline-fb[3]*figure_size/PT,left+fwidth,baseline-fb[1]*figure_size/PT),size_pt=figure_size,shrink=False,name=name+' grams')
    e=s.text('℮',(left+fwidth+.7,top,left+total,top+3),size_pt=sign_size,shrink=False,name=name+' estimated sign')
    r2=s.text('0.15 oz',(center_x-width/2,top+3.45,center_x+width/2,top+5.55),size_pt=figure_size,shrink=False,name=name+' ounces')
    # Actual ink height of digits, rather than g's descender, is the statutory measure.
    return {'figures_size_pt':figure_size,'figures_height_mm':2.001,'figure_calibration':'Minimum digit 4; 2 mm floor plus 0.001 mm native-rounding allowance. Curved 0/5 overshoot is retained.','estimated_sign_height_mm':e['ink_height_mm'],'baseline_shared':abs(r1['baseline_mm']-e['ink_box_mm'][3])<.02,'rows':[r1,e,r2],'copy':'4.5 g ℮ 0.15 oz','front_third_overflow':total>width or r2['overflow'],'legal_sizes_hold':abs(e['ink_height_mm']-3)<.0001}

def tint_size(width_mm,height_mm):
    m=glyph_metrics('ROSEWATER');b=m['box_em']
    return max(5,min(width_mm*PT/m['advance_em'],height_mm*PT/(b[3]-b[1])))

def build_wraps(tint='ROSEWATER',target=None,panels=('body','cap')):
    target=Path(target or OUT);target.mkdir(parents=True,exist_ok=True)
    reports={};cleaning=[];wraps={};nets={}
    body,rec=clean_live_type('body',[(106,24,189,49),(116,57,179,94),(115,98,180,127),(124,130,172,138),(110,141,184,157),(103,167,194,184)])
    cleaning.append(rec)
    bodyplate,wraps['body']=prepare_wrap('body',body)
    cap_source=OUT/'repair/cap-after.png'
    if not cap_source.exists():cap_source=OUT/'logotype/cap-without-spurious-one.png'
    cap=np.asarray(Image.open(cap_source).convert('RGB'))
    capplate,wraps['cap']=prepare_wrap('cap',cap)
    wraps['cap']['underlay_source']=rel(cap_source);wraps['cap']['underlay_sha256']=sha(cap_source)
    for panel,height,plate in [('body',42,bodyplate),('cap',32,capplate)]:
        if panel not in panels:continue
        s=SurfaceBuilder((58.5,height),'HAYAT '+panel+' — '+tint,trim_mm=(0,1,58.5,height-1));s.add_plate(plate,(0,0,58.5,height),name=panel+' preserved painting')
        if panel=='body':
            s.svg(MARK,(22.1,5.3,38.2,8.66),name='approved BBROSE mark',color=INK)
            for copy,box,face in [('HAYAT',(21,12.4,39.45,14.9),'latin'),('حياة',(21,15.4495,39.45,18.5505),'arabic'),('LIP BALM',(21,20.4,39.45,22.9),'latin'),('بلسم شفاه',(21,22.9115,39.45,26.7885),'arabic'),(tint,(21,29.7,39.45,32.2),'latin')]:
                s.text(copy,box,face=face,size_pt=tint_size(box[2]-box[0],box[3]-box[1]) if copy==tint else point_size_for_height('ا',2.5,'arabic') if face=='arabic' else point_size_for_height(copy,box[3]-box[1],face),shrink=copy!=tint and face!='arabic',name='body '+('tint' if copy==tint else copy))
            s.line((26.5,27.8),(34,27.8),layer='type',color=rgb(INK),width=.3)
            nets['body']=add_net(s,30.2257,34.2)
        else:
            s.svg(OUT/'logotype/hayat.svg',(0,0,58.5,32),layer='type',name='cap hayat traced logotype')
            s.svg(MARK,(24.1,1.9,36.35,4.45),name='approved BBROSE mark',color=INK)
            s.text(tint,(21,27.2,39.45,29.2),size_pt=tint_size(18.45,2),shrink=False,name='cap tint')
        add_wrap_guides(s,height)
        reports[panel]=s.save(target/f'{panel}-wrap.ai',target/f'{panel}-flat.png')
        render_flat(target/f'{panel}-wrap.ai',target/f'panels/{panel}-flat.png')
    dump(target/'wraps.json',wraps)
    for filename,key in [('wrap-ai-check.json','ai_check'),('wrap-type-checks.json','type'),('wrap-contrast.json','contrast')]:
        p=target/filename;prior=json.loads(p.read_text()) if p.exists() else {};prior.update({k:r[key] for k,r in reports.items()});dump(p,prior)
    if nets:dump(target/'net-checks.json',nets)
    dump(OUT/'type-cleaning.json',cleaning)
    return reports

def build_label(tint='ROSEWATER',target=None):
    target=Path(target or OUT);target.mkdir(parents=True,exist_ok=True)
    s=SurfaceBuilder((16,16),'HAYAT label — '+tint)
    s.add_plate(OUT/'cleaning/label-after.png',(0,0,16,16),name='label fragment painting')
    s.text(tint,(2.4,12.1,13.6,13.9),size_pt=tint_size(11.2,1.8),shrink=False,name='label tint')
    s.circle((8,8),8,layer='die');s.circle((8,8),7,layer='guides')
    rec=s.save(target/'label.ai',target/'label-flat.png')
    render_flat(target/'label.ai',target/'label-with-die.png',layers=('plate','type','mark','die'))
    render_flat(target/'label.ai',target/'panels/label-flat.png')
    dump(target/'label-checks.json',rec)
    return rec

def native_roundtrip(path, area_frames=None):
    """Rebuild the five groups in the real Illustrator, then independently read back.

    Temporary layer PDFs are solely interchange inputs and removed with their
    temporary directory; the deliverable remains one PDF-compatible native .ai.
    """
    import tempfile
    import subprocess
    from apps.ire.handoff.illustrator_exec import run_jsx
    path=Path(path);stem=path.stem;checkdir=path.parent/'native-checks';checkdir.mkdir(exist_ok=True)
    before_sha=sha(path)
    with fitz.open(path) as d:
        size=[d[0].rect.width,d[0].rect.height];trim_before=list(d[0].trimbox);before=raster(d,300)
        oldtext=d[0].get_text('text');oldglyphs=sum(len(x['chars']) for x in d[0].get_texttrace());expected_rasters=len(d[0].get_image_info())
    with tempfile.TemporaryDirectory(prefix='hayat-native-') as td:
        td=Path(td);sources={}
        for layer in LAYERS:
            lp=td/f'{layer}.pdf'
            with fitz.open(path) as d:
                set_layers(d,{layer})
                d.xref_set_key(d[0].xref,'PieceInfo','null')
                d.xref_set_key(d.pdf_catalog(),'PieceInfo','null')
                d.set_metadata({'creator':'HAYAT layer interchange'})
                d.xref_set_key(d.pdf_catalog(),'OCProperties/D/Locked','[]')
                for x in d.get_ocgs():d.xref_set_key(x,'Usage','<</View <</ViewState /ON>> /Print <</PrintState /ON>>>>')
                d.save(lp,garbage=3,deflate=True)
            sources[layer]=str(lp)
        dest=td/'native.ai';census=td/'census.json'
        area_frames=[] if area_frames is None else list(area_frames)
        for f in area_frames:
            if 'copy' not in f and 'fullcopy' not in f:raise ValueError('Declared native frame has no copy: '+str(f))
            if 'copy' in f and 'fullcopy' in f and f['copy']!=f['fullcopy']:raise ValueError('Conflicting native frame copies')
            f['copy']=f['copy'] if 'copy' in f else f['fullcopy']
            if not isinstance(f['copy'],str) or not f['copy'].strip():raise ValueError('Native frame copy must be nonempty')
        data={'sources':sources,'out':str(dest),'census':str(census),'size':size,'layers':list(LAYERS),'frames':area_frames,'progress':str(td/'stage.txt')}
        script=r'''(function(){var D=__DATA__,doc=null,src=null,old=app.userInteractionLevel,report={};
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
function stage(s){var f=new File(D.progress);f.open('w');f.write(s);f.close();}function charEvidence(t){var a=[],contents=t.contents;for(var k=0;k<contents.length;k++){var text=contents.charAt(k);if(/\s/.test(text)){a.push({text:text,font:null,size:null,nonprintingWhitespace:true});continue;}var v=t.characters[k].characterAttributes;a.push({text:text,font:v.textFont.name,size:v.size});}return a;}function linesEvidence(t){var a=[];for(var k=0;k<t.lines.length;k++)a.push(t.lines[k].contents);return a;}
try{stage('create document');app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.documents.add(DocumentColorSpace.RGB,D.size[0],D.size[1]);doc.artboards[0].artboardRect=[0,D.size[1],D.size[0],0];
for(var i=0;i<D.layers.length;i++){var name=D.layers[i],L=i===0?doc.layers[0]:doc.layers.add();L.name=name;doc.activeLayer=L;stage('open layer '+name);src=app.open(new File(D.sources[name]));stage('copy layer '+name);var items=[];for(var j=0;j<src.pageItems.length;j++){var it=src.pageItems[j];if(it.parent.typename==='Layer')items.push(it);}for(var j=items.length-1;j>=0;j--){var bounds=items[j].geometricBounds;var cp=items[j].duplicate(L,ElementPlacement.PLACEATBEGINNING);var cb=cp.geometricBounds;cp.translate(bounds[0]-cb[0],bounds[1]-cb[1]);}src.close(SaveOptions.DONOTSAVECHANGES);src=null;doc.activate();L.visible=name!=='die'&&name!=='guides';L.printable=name!=='die'&&name!=='guides';L.locked=name==='die'||name==='guides';}
report.areaFrames=[];if(D.frames.length){for(var z=0;z<doc.layers.length;z++){doc.layers[z].locked=false;doc.layers[z].visible=true;}}
for(var f=0;f<D.frames.length;f++){stage('area '+f);var F=D.frames[f],L=doc.layers.getByName('type');L.locked=false;L.visible=true;doc.activeLayer=L;report.stage='frame '+F.name+' path';stage(report.stage);var box=F.box_mm,mm=72/25.4;for(var j=doc.textFrames.length-1;j>=0;j--){var ex=doc.textFrames[j],b=ex.geometricBounds,cx=(b[0]+b[2])/2/mm,cy=(D.size[1]-(b[1]+b[3])/2)/mm;if(cx>=box[0]&&cx<=box[2]&&cy>=box[1]&&cy<=box[3])ex.remove();}var pa=L.pathItems.rectangle(D.size[1]-box[1]*mm,box[0]*mm,(box[2]-box[0])*mm,(box[3]-box[1])*mm);pa.stroked=false;pa.filled=false;report.stage='frame '+F.name+' text';stage(report.stage);var tf=doc.textFrames.areaText(pa);tf.move(L,ElementPlacement.PLACEATBEGINNING);tf.name=F.name;report.stage='frame '+F.name+' contents';stage(report.stage);tf.contents=F.copy;tf.note='Complete logical draft: '+F.copy;tf.textRange.characterAttributes.textFont=app.textFonts.getByName(F.face==='arabic'?'Almarai-Regular':'DMSans-Regular');tf.textRange.characterAttributes.size=F.size_pt||5;tf.textRange.characterAttributes.leading=F.leading_pt||((F.size_pt||5)*1.2);tf.textRange.characterAttributes.autoLeading=false;stage('frame '+F.name+' character fonts');for(var ci=0;ci<tf.characters.length;ci++){var ch=tf.characters[ci].contents;tf.characters[ci].characterAttributes.textFont=app.textFonts.getByName(/[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufeff]/.test(ch)?'Almarai-Regular':'DMSans-Regular');}stage('frame '+F.name+' color/composer');var C=new RGBColor();var col=F.color||[244,233,229];C.red=col[0];C.green=col[1];C.blue=col[2];tf.textRange.characterAttributes.fillColor=C;if(F.face==='arabic'){tf.textRange.paragraphAttributes.justification=Justification.RIGHT;tf.textRange.paragraphAttributes.composerEngine=ComposerEngineType.optycaComposer;tf.textRange.paragraphAttributes.paragraphDirection=ParagraphDirectionType.RIGHT_TO_LEFT_DIRECTION;}
if(F.ltr_paragraph_indices){for(var pi=0;pi<F.ltr_paragraph_indices.length;pi++){var paragraph=tf.paragraphs[F.ltr_paragraph_indices[pi]];paragraph.paragraphAttributes.paragraphDirection=ParagraphDirectionType.LEFT_TO_RIGHT_DIRECTION;paragraph.paragraphAttributes.justification=Justification.LEFT;}}stage('frame '+F.name+' redraw');app.redraw();stage('frame '+F.name+' census');var visible=[];for(var l=0;l<tf.lines.length;l++){stage('line census '+F.name+' '+l);visible.push(tf.lines[l].contents);}stage('frame attributes '+F.name);report.areaFrames.push({name:F.name,layer:tf.layer.name,kind:String(tf.kind),composer:String(tf.textRange.paragraphAttributes.composerEngine),direction:String(tf.textRange.paragraphAttributes.paragraphDirection),fullContents:tf.contents,characters:tf.characters.length,visibleLines:visible,visibleCharacterCount:visible.join('').length,characterFonts:charEvidence(tf),overflow:visible.join('').replace(/\s/g,'').length<tf.contents.replace(/\s/g,'').length});}
for(var z=0;z<doc.layers.length;z++){var Z=doc.layers[z];Z.visible=Z.name!=='die'&&Z.name!=='guides';Z.printable=Z.visible;Z.locked=!Z.visible;}
report.frames=[];for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i],a=t.characters[0].characterAttributes;report.frames.push({text:t.contents,fullContents:t.contents,visibleLines:linesEvidence(t),characterFonts:charEvidence(t),font:a.textFont.name,size:a.size,bounds:t.visibleBounds,kind:String(t.kind),layer:t.layer.name});}
report.layers=[];for(var i=0;i<doc.layers.length;i++){var L=doc.layers[i];report.layers.push({name:L.name,locked:L.locked,printable:L.printable,visible:L.visible,rasters:L.rasterItems.length,placed:L.placedItems.length,paths:L.pathItems.length,groups:L.groupItems.length,textFrames:L.textFrames.length});}
report.rasters=doc.rasterItems.length;report.placed=doc.placedItems.length;report.artboards=doc.artboards.length;report.version=app.version;
stage('save');var options=new IllustratorSaveOptions();options.pdfCompatible=true;options.embedICCProfile=true;options.fontSubsetThreshold=0;doc.saveAs(new File(D.out),options);report.saved=true;
}catch(e){report.saved=false;report.error=String(e);}finally{if(src)src.close(SaveOptions.DONOTSAVECHANGES);if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);app.userInteractionLevel=old;}
var file=new File(D.census);file.encoding='UTF-8';file.open('w');file.write(json(report));file.close();return json({saved:report.saved,error:report.error});})();'''
        jsx=td/'native.jsx';jsx.write_text(script.replace('__DATA__',json.dumps(data,ensure_ascii=False)))
        result=run_jsx(str(jsx),timeout_s=180)
        report=json.loads(census.read_text()) if census.exists() else {'saved':False,'execution':result}
        report['last_native_stage']=(td/'stage.txt').read_text() if (td/'stage.txt').exists() else None
        report['character_font_scope']='Every non-whitespace character; whitespace contents retained but font attributes are not queried because Illustrator30 crashes on a trailing RTL space.'
        report['execution']=result;report['input_sha256']=before_sha;report['expected_rasters']=expected_rasters
        if report.get('saved'):
            with fitz.open(dest) as d:
                after=raster(d,300);report['native_pdf_fonts']=[{'name':d.extract_font(f[0])[0],'embedded_bytes':len(d.extract_font(f[0])[3])} for f in d[0].get_fonts(full=True)]
                report['native_pdf_live_glyphs']=sum(len(x['chars']) for x in d[0].get_texttrace());report['native_pdf_text']=d[0].get_text('text')
                report['native_pdf_ocgs']=[x['name'] for x in d.get_ocgs().values()]
            same_shape=after.shape==before.shape
            Image.fromarray(before).save('/tmp/hayat-native-before.png');Image.fromarray(after).save('/tmp/hayat-native-after.png')
            Path('/tmp/hayat-native-candidate.ai').write_bytes(dest.read_bytes())
            report['render_shape_match']=same_shape
            report['render_mean_absolute_error']=float(np.abs(after.astype(float)-before.astype(float)).mean()) if same_shape else None
            outside=np.ones(before.shape[:2],dtype=bool)
            for frame in area_frames or []:
                x0,y0,x1,y1=[round(v*300/25.4) for v in frame['box_mm']];outside[max(0,y0):y1,max(0,x0):x1]=False
            report['outside_copy_zone_render_mae']=float(np.abs(after.astype(float)-before.astype(float))[outside].mean()) if same_shape else None
            report['render_comparison_scope']='Full page at300dpi; declared full-copy area frames excluded from the preservation comparison and measured separately for overset.'
            report['input_live_glyphs']=oldglyphs
            report['checks']={'five_layers':sorted(x['name'] for x in report['layers'])==sorted(LAYERS),'die_guides_locked_nonprinting':all(x['locked'] and not x['printable'] for x in report['layers'] if x['name'] in ('die','guides')),'live_fonts_expected':all(c['text'].isspace() or c['font'] in ('DMSans-Regular','Almarai-Regular') for x in report['frames'] for c in x['characterFonts']),'fonts_embedded':bool(report['native_pdf_fonts']) and all(x['embedded_bytes']>0 for x in report['native_pdf_fonts']),'live_type_present':report['native_pdf_live_glyphs']>0,'raster_preserved':report['rasters']==expected_rasters,'placed_assets_embedded':report['placed']==0,'same_dimensions':same_shape,'render_preserved':same_shape and report['outside_copy_zone_render_mae']<3,'full_drafts_on_type':all(x['layer']=='type' and x['kind']=='TextType.AREATEXT' for x in report['areaFrames']), 'full_drafts_retained':len(report['areaFrames'])==len(area_frames) and all(x['fullContents']==f['copy'] for x,f in zip(report['areaFrames'],area_frames))}
            report['holds']=all(v for v in report['checks'].values() if v is not None)
            if report['holds']:
                path.write_bytes(dest.read_bytes())
                # Illustrator's native layer lock is real (census above); mirror it
                # into PDF optional-content compatibility metadata as well.
                with fitz.open(path) as final:
                    ids=final.get_ocgs();lockedids=[k for k,v in ids.items() if v['name'] in ('die','guides')]
                    final.xref_set_key(final.pdf_catalog(),'OCProperties/D/Locked','['+' '.join(f'{k} 0 R' for k in lockedids)+']')
                    for k,v in ids.items():
                        final.xref_set_key(k,'Usage','<</Print <</PrintState '+('/OFF' if k in lockedids else '/ON')+'>>>>')
                    final[0].set_trimbox(fitz.Rect(trim_before)&final[0].rect);final[0].set_bleedbox(final[0].rect);final.saveIncr()
                report['pdf_compatibility_patch']='PDF OCG Locked/PrintState mirrors the actual native locks/printability; original TrimBox retained. Private Illustrator editing data unchanged.'
                report['final_sha256']=sha(path);report['final_is_native_illustrator']=True
            else:report['final_is_native_illustrator']=False
        dump(checkdir/f'{stem}.json',report)
    return report

def refresh_surface_records(folder=OUT):
    folder=Path(folder);path=folder/'surface-builds.json';records=json.loads(path.read_text())
    for surface,r in records.items():
        file=folder/('label.ai' if surface=='label' else surface+'-wrap.ai')
        r['file']=rel(file);r['sha256']=sha(file);r['ai_check']=read_back_ai(file,r['elements'],r['type']);r['contrast']=contrast_report(file,r['type'])
        r['native_check']=rel(folder/'native-checks'/(file.stem+'.json'))
        render_flat(file,folder/(surface+'-flat.png'))
        render_flat(file,folder/'panels'/(surface+'-flat.png'))
        if surface=='label':render_flat(file,folder/'label-with-die.png',layers=('plate','type','mark','die'))
        measurements=measure_native_lines(file,r['type'])
        for row,measurement in zip(r['type'],measurements):row['native_readback']=measurement
        if surface=='body' and (folder/'net-checks.json').exists():
            net=json.loads((folder/'net-checks.json').read_text());net['body']['native_readback']=[x for x in measurements if x['name'].startswith('net')]
            gram=next(x for x in measurements if x['name']=='net grams');sign=next(x for x in measurements if x['name']=='net estimated sign')
            net['body']['baseline_shared']=abs(gram['digits'][0]['ink_bottom_mm']-sign['ink_box_mm'][3])<.02
            heights=[d['height_mm'] for row in net['body']['native_readback'] for d in row.get('digits',[])]
            net['body']['native_figure_min_mm']=min(heights);net['body']['native_figure_max_mm']=max(heights)
            net['body']['native_figure_floor_holds']=min(heights)>=2
            net['body']['native_estimated_sign_mm']=sign['ink_height_mm']
            net['body']['native_baseline_difference_mm']=abs(gram['digits'][0]['ink_bottom_mm']-sign['ink_box_mm'][3])
            dump(folder/'net-checks.json',net)
    dump(path,records)
    dump(folder/'type-checks.json',{k:r['type'] for k,r in records.items()})
    dump(folder/'contrast.json',{k:r['contrast'] for k,r in records.items()})
    dump(folder/'ai-check.json',{k:r['ai_check'] for k,r in records.items()})
    dump(folder/'wrap-ai-check.json',{k:r['ai_check'] for k,r in records.items() if k!='label'})
    dump(folder/'wrap-type-checks.json',{k:r['type'] for k,r in records.items() if k!='label'})
    dump(folder/'label-checks.json',records['label'])
    return records

def native_reopen_checks(paths):
    """Read the saved final .ai files in Illustrator itself; no source document edits."""
    import tempfile
    from apps.ire.handoff.illustrator_exec import run_jsx
    paths=[Path(p) for p in paths]
    with tempfile.TemporaryDirectory(prefix='hayat-reopen-') as td:
        td=Path(td);result=td/'reopened.json';script=td/'read.jsx'
        js=r'''(function(){var paths=__PATHS__,out=[],old=app.userInteractionLevel,d=null;function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}function j(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(j(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+j(v[k]));return '{'+a.join(',')+'}';}function charEvidence(t){var a=[],contents=t.contents;for(var k=0;k<contents.length;k++){var text=contents.charAt(k);if(/\s/.test(text)){a.push({text:text,font:null,size:null,nonprintingWhitespace:true});continue;}var v=t.characters[k].characterAttributes;a.push({text:text,font:v.textFont.name,size:v.size});}return a;}function linesEvidence(t){var a=[];for(var k=0;k<t.lines.length;k++)a.push(t.lines[k].contents);return a;}app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;try{for(var p=0;p<paths.length;p++){var r={file:paths[p],layers:[],frames:[]};try{d=app.open(new File(paths[p]));app.redraw();for(var i=0;i<d.layers.length;i++){var l=d.layers[i];r.layers.push({name:l.name,locked:l.locked,printable:l.printable});}for(var i=0;i<d.textFrames.length;i++){var t=d.textFrames[i];r.frames.push({text:t.contents,fullContents:t.contents,visibleLines:linesEvidence(t),characterFonts:charEvidence(t),font:t.characters[0].characterAttributes.textFont.name,layer:t.layer.name,kind:String(t.kind)});}r.rasters=d.rasterItems.length;r.placed=d.placedItems.length;r.reopened=true;}catch(e){r.error=String(e);r.reopened=false;}finally{if(d)d.close(SaveOptions.DONOTSAVECHANGES);d=null;}out.push(r);}}finally{app.userInteractionLevel=old;}var f=new File(__OUT__);f.encoding='UTF-8';f.open('w');f.write(j(out));f.close();return j({files:out.length});})();'''
        script.write_text(js.replace('__PATHS__',json.dumps([str(p) for p in paths])).replace('__OUT__',json.dumps(str(result))))
        execution=run_jsx(str(script),timeout_s=180)
        rows=json.loads(result.read_text()) if result.exists() else []
    if len(rows)!=len(paths):raise ValueError('Incomplete saved-file reopen census')
    for p,r in zip(paths,rows):
        recpath=p.parent/'native-checks'/(p.stem+'.json');rec=json.loads(recpath.read_text())
        if not isinstance(rec.get('frames'),list) or not rec['frames'] or not isinstance(r.get('frames'),list) or not r['frames']:raise ValueError('Missing saved/reopened native frame census')
        complete_character_evidence=all('characterFonts' in x for x in rec['frames'])
        if complete_character_evidence:
            def signature(frame):return (frame['text'],tuple((c['text'],c['font'],round(c['size'],4) if c['size'] is not None else None) for c in frame['characterFonts']))
            expected=sorted(signature(x) for x in rec['frames']);found=sorted(signature(x) for x in r['frames'])
        else:
            # Explicit compatibility for the unchanged Round1B wraps/labels.
            expected=sorted((x['text'],x['font']) for x in rec['frames']);found=sorted((x['text'],x['font']) for x in r['frames'])
        r['font_comparison_scope']='Every non-whitespace character: text, font, size; all whitespace retained in exact contents. Whitespace font query omitted because Illustrator30 crashes on a trailing RTL space.' if complete_character_evidence else 'Legacy unchanged file: text and original single-font frame census'
        r['checks']={'reopened':r['reopened'],'same_live_text_and_fonts':expected==found,'five_layers':sorted(x['name'] for x in r['layers'])==sorted(LAYERS),'die_guides_locked_nonprinting':all(x['locked'] and not x['printable'] for x in r['layers'] if x['name'] in ('die','guides')),'raster_embedded':r['rasters']==rec.get('expected_rasters',rec['rasters']) and r['placed']==0,'area_frames_on_type':all(t['layer']=='type' for t in r['frames'] if t.get('kind')=='TextType.AREATEXT'),'area_frame_count':sum(t.get('kind')=='TextType.AREATEXT' for t in r['frames'])==len(rec['areaFrames'])}
        r['holds']=all(r['checks'].values());r['final_sha256']=sha(p);rec['saved_file_reopen']=r;rec['holds']=bool(rec['checks']) and all(rec['checks'].values()) and r['holds'];dump(recpath,rec)
    return rows

def measure_native_lines(path, rows):
    """Measure final PDF text operators and embedded TrueType glyph contours."""
    results=[]
    with fitz.open(path) as doc:
        candidates={}
        for resource in doc[0].get_fonts(full=True):
            name,ext,kind,data=doc.extract_font(resource[0])
            if not data or ext not in ('ttf','otf'):continue
            font=TTFont(io.BytesIO(data));family=name.split('+')[-1].replace(' ','').lower()
            candidates.setdefault(family,[]).append((resource[0],font))
        traces=doc[0].get_texttrace()
        for row in rows:
            # Match actual emitted glyph string and nearest measured baseline.
            display=row.get('display',row['copy'])
            spans=[t for t in traces if ''.join(chr(c[0]) for c in t['chars'])==display]
            if not spans:
                results.append({'name':row['name'],'measured':False,'reason':'No exact span; may be split or area text. Complete contents checked in native census.'});continue
            t=min(spans,key=lambda t:abs(t['chars'][0][2][1]/PT-row['baseline_mm']))
            boxes=[];digits=[];font_refs=set()
            for char,gid,origin,bbox in t['chars']:
                bounds=None
                for xref,font in candidates.get(t['font'].replace(' ','').lower(),[]):
                    order=font.getGlyphOrder()
                    if gid>=len(order):continue
                    gs=font.getGlyphSet();pen=BoundsPen(gs);gs[order[gid]].draw(pen)
                    if pen.bounds:bounds=pen.bounds;units=font['head'].unitsPerEm;font_refs.add(xref);break
                if bounds is None:continue
                scale=t['size']/units;x0,y0,x1,y1=bounds
                box=[(origin[0]+x0*scale)/PT,(origin[1]-y1*scale)/PT,(origin[0]+x1*scale)/PT,(origin[1]-y0*scale)/PT]
                boxes.append(box)
                if chr(char).isdigit():digits.append({'char':chr(char),'height_mm':box[3]-box[1],'ink_bottom_mm':box[3]})
            if not boxes:results.append({'name':row['name'],'measured':False});continue
            ib=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
            reference=glyph_metrics('H' if row['face']=='latin' else 'ا',row['face'])['box_em']
            results.append({'name':row['name'],'measured':True,'actual_pdf_size_pt':t['size'],'ink_box_mm':ib,'ink_height_mm':ib[3]-ib[1],'digits':digits,'cap_reference_height_mm':(reference[3]-reference[1])*t['size']/PT,'cap_reference':'H' if row['face']=='latin' else 'ا','cap_reference_source':row['font_path'],'embedded_font_xrefs':sorted(font_refs),'method':'Actual final PDF span size/origin/glyph IDs; ink contours from embedded font bytes. Canonical H/alif reference from the hash-pinned licensed face; native point size measured, not requested.'})
    return results

def refresh_carton_records(folder=OUT):
    """Replace preview-row metadata with the actual full native area frames."""
    import tempfile
    from apps.pipeline.services import stick_carton as sc
    folder=Path(folder);meta=json.loads((folder/'carton.json').read_text());result=meta['files'];path=folder/'carton-artwork.ai'
    native=json.loads((folder/'native-checks/carton-artwork.json').read_text());assert native.get('holds') and native.get('final_sha256')==sha(path)
    frames=json.loads((folder/'carton-native-frames.json').read_text())['frames'];preview={n for f in frames for n in f['preview_row_names']}
    replaced=preview|{f['name'] for f in frames}
    rows=[r for r in result['type'] if r['name'] not in replaced];elements=[e for e in result['elements'] if e['name'] not in replaced]
    for f,a in zip(frames,native['areaFrames']):
        assert a['fullContents']==f['copy'] and a['layer']=='type'
        elements.append({'name':f['name'],'layer':'type','kind':'live_area_type','box_mm':f['box_mm']})
    check=read_back_ai(path,elements,rows)
    check['native_full_copy_retained']=all(a['fullContents']==f['copy'] for a,f in zip(native['areaFrames'],frames))
    check['native_area_text']=native['areaFrames']
    measurements=measure_native_lines(path,rows)
    for row,m in zip(rows,measurements):row['native_readback']=m
    for f,a in zip(frames,native['areaFrames']):
        rows.append({'name':f['name'],'copy':f['copy'],'face':f['face'],'font_path':rel(FONT_PATHS[f['face']]),'size_pt':f['size_pt'],'ink_box_mm':f['box_mm'],'zone_mm':f['box_mm'],'at_least_5pt':True,'overflow':a['overflow'],'native_area_text':a,'color':INK,'note':'Full editable draft retained. Only the listed native visible lines print; overset is an unresolved fit defect.'})
    result.update(file=rel(path),sha256=sha(path),ai_check=check,type=rows,elements=elements,contrast=contrast_report(path,rows),native_check=rel(folder/'native-checks/carton-artwork.json'))
    meta['files']=result;dump(folder/'carton.json',meta)
    render_flat(path,folder/'carton-flat.png')
    for place in meta['placement']:
        element=next(e for e in elements if e['kind']=='raster' and e['name']==place['panel'])
        dx=element['box_mm'][0]-place['ground_mm'][0];dy=element['box_mm'][1]-place['ground_mm'][1]
        box=[v+(dx if i%2==0 else dy) for i,v in enumerate(place['trim_mm'])]
        render_flat(path,folder/f"panels/{place['panel']}-flat.png",clip_mm=box)
    fit=json.loads((folder/'carton-fit-report.json').read_text());fit['full_text_native_retention_pending']=False;fit['full_text_native_retained']=True;fit['native_census']=result['native_check'];fit['all_lines_live']=True;fit['all_copy_visible_in_print']=False;fit['copy_shortened']=False
    fit['native_area_frames']=native['areaFrames'];fit['overset']=[]
    for f,a in zip(frames,native['areaFrames']):
        visible=''.join(a['visibleLines']);full=a['fullContents']
        fit['overset'].append({'language':f['language'],'frame_mm':f['box_mm'],'size_pt':f['size_pt'],'full_characters':len(full),'visible_characters':len(visible),'visible_lines':a['visibleLines'],'overset':a['overflow'],'hidden_remainder':full[len(visible):] if full.startswith(visible) else None,'full_copy':full,'native_layer':a['layer'],'status':'Incomplete in print at 5pt; entire draft remains editable in the native area text. No copy discarded.'})
    fit['copy_lines_native']=native['areaFrames'];fit['net']={r['name']:r for r in rows if 'net ' in r['name']}
    gram=fit['net']['front net grams']['native_readback'];sign=fit['net']['front net e-mark']['native_readback']
    heights=[d['height_mm'] for row in fit['net'].values() for d in row['native_readback'].get('digits',[])]
    fit['net_native_checks']={'figure_min_mm':min(heights),'figure_max_mm':max(heights),'figures_at_least_2mm':min(heights)>=2,'estimated_sign_height_mm':sign['ink_height_mm'],'estimated_sign_3mm':abs(sign['ink_height_mm']-3)<.001,'baseline_difference_mm':abs(gram['digits'][0]['ink_bottom_mm']-sign['ink_box_mm'][3]),'baseline_shared':abs(gram['digits'][0]['ink_bottom_mm']-sign['ink_box_mm'][3])<.02}
    dump(folder/'carton-fit-report.json',fit)
    product=dict(sc.PRODUCTS['lip_balm'],name='HAYAT lip balm',shade=meta['tint'].title());coords,_=sc.die(product);ox,oy=coords.bleed_polygon.bounds[:2]
    with tempfile.TemporaryDirectory(prefix='hayat-die-read-') as td:
        temp=Path(td)/'die.ai'
        with fitz.open(path) as d:set_layers(d,{'die'});d.save(temp)
        die=sc.die_readback(temp,coords,ox,oy)
    fold=json.loads((folder/'carton-fold-check.json').read_text());fold['die_readback']=die;fold['native_artwork_sha256']=sha(path);fold['native_full_copy_frames']=native['areaFrames'];dump(folder/'carton-fold-check.json',fold)
    for filename,key in [('ai-check.json','ai_check'),('type-checks.json','type'),('contrast.json','contrast')]:
        p=folder/filename;r=json.loads(p.read_text()) if p.exists() else {};r['carton']=result[key];dump(p,r)
    return result
