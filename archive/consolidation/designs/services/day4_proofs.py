"""Review sheets and surface bindings from the pinned Day 4 masters. No providers."""
from pathlib import Path
import io,json,math
import cv2
import fitz
import numpy as np
from PIL import Image,ImageDraw
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from apps.pipeline.services import fidelity_master as fm
from apps.dielines.exporters.text_intl import shape_ar
ROOT=fm.fa.ROOT/'docs/audit/day-4'


def setup():
    for role,font in fm.FONTS.items():pdfmetrics.registerFont(TTFont('Fidelity-'+role,str(font)))
    pdfmetrics.registerFont(TTFont('Proof',str(fm.FONTS['symbol'])))


def words(c,x,y,text,size=9):
    c.setFillColorRGB(.13,.17,.19);c.setFont('Proof',size);c.drawString(x*mm,y*mm,text)


def heading(c,title,sub,width=210,height=297):
    words(c,14,height-18,title,15);words(c,14,height-26,sub,8)


def bar(c,x,y):
    c.setStrokeColorRGB(.15,.2,.2);c.setLineWidth(.7);c.line(x*mm,y*mm,(x+50)*mm,y*mm)
    for end in (x,x+50):c.line(end*mm,(y-2)*mm,end*mm,(y+2)*mm)
    words(c,x,y-6,'50 mm — print at 100%; disable Fit',7)


def image_on(c,path,x,y,w,h):c.drawImage(str(path),x*mm,y*mm,w*mm,h*mm,mask='auto')


def render_pdf(path,dpi=160):
    with fitz.open(path) as doc:
        for i,page in enumerate(doc):page.get_pixmap(dpi=dpi).save(str(Path(path).with_name(Path(path).stem+f'-page-{i+1}.png')))


def fidelity_sheet():
    setup();p=ROOT/'master';metrics=json.loads((p/'fidelity-check.json').read_text())
    out=p/'comparison-at-100-percent.pdf';c=Canvas(str(out),pagesize=(210*mm,297*mm))
    heading(c,'SUN REPAIR / fidelity revision 2','DESIGNER REVIEW — Arabic scale and extracted matte fail the declared bar')
    H=1536*fm.fa.YS;W=1024*fm.fa.XS
    for x,source,label in [(5,fm.fa.CONCEPT,'Concept 147'),(75,p/'projected-master.png','Reprojected actual PDF')]:
        image_on(c,source,x,128,W,H);words(c,x+12,121,label,9)
    # Flat at the same physical dimensions, white ink shown on neutral gray.
    c.setFillColorRGB(.55,.55,.55);c.rect(157*mm,139*mm,fm.fa.WIDTH*mm,fm.fa.HEIGHT*mm,fill=1,stroke=0)
    image_on(c,p/'artwork.png',157,139,fm.fa.WIDTH,fm.fa.HEIGHT);words(c,158,121,'Flat / neutral ground',8)
    words(c,14,107,'One scale: bottle convention 108 mm overall; actual height datum unresolved.',8)
    words(c,14,99,'Reference-derived amber/chrome view; this is not a physical material render.',8)
    words(c,14,88,'All copy stays on the front. Back: no artwork. Approved white vector logo.',8)
    words(c,14,80,'Closest licensed faces; each glyph is live. Unknown original font remains a difference.',8)
    words(c,14,72,'Physical deviations: none applied. Matte has amber remnants; no approval implied.',8)
    words(c,14,64,'Clear-film proposal: CMYK swoosh + opaque white. Owner method unselected.',8)
    words(c,14,56,'Shoulder conformity, film edge, white opacity and fine rules need a supplier proof.',8)
    bar(c,14,39);c.showPage()
    heading(c,'Measured fidelity / same declared instrument','Pixel quantisation is reported, not used to waive the 3% scale threshold')
    y=255;words(c,14,y,'Element / measured [x,z,w,h] mm to actual export [x,z,w,h] mm',8);y-=10
    for r in metrics['placement']:
        a=r['concept_bbox_mm'];b=r['exported_bbox_mm']
        fmt=lambda v:'/'.join(f'{x:.2f}' for x in (v[0],v[1],v[2]-v[0],v[3]-v[1]))
        words(c,14,y,f"{r['id']}: {fmt(a)} to {fmt(b)}",7);y-=7
        dx,dy=r['delta_scale_percent'];words(c,18,y,f"Δposition {r['delta_position_mm']:.3f} mm; Δscale {dx:.2f}/{dy:.2f}% — {'PASS' if r['passed'] else 'REVIEW'}",7);y-=10
    words(c,14,53,f"Swoosh masked SSIM {metrics['swoosh_ssim']:.4f} >=0.85; Day2 negative fails.",8)
    words(c,14,44,'Critic 8.5/10; illustration 6/10 fails minimum 7. Two repair rounds exhausted.',8)
    words(c,14,35,'Material appearance reuses the concept ground; optical rendering is Day 5.',8)
    c.showPage();heading(c,'Colour and retained differences','CIEDE2000 / D65 sRGB samples; print colour still needs a supplier proof')
    y=253;words(c,14,y,'Element                 ConceptRGB to exportedRGB         ΔE / limit',8);y-=12
    for r in metrics['colour']:
        rgb=lambda values:','.join(str(round(v,1)) for v in values)
        words(c,14,y,f"{r['id']}: {rgb(r['concept_srgb'])} to {rgb(r['master_srgb'])}",7);words(c,171,y,f"{r['deltaE2000']:.2f} / {r['tolerance']}",7);y-=10
    words(c,14,86,'Physical deviations: none. No crop, outline trace, moved copy or safety shrink.',8)
    words(c,14,77,'Remaining differences: closest fonts; approved logo; extracted matte ground remnants.',8)
    words(c,14,68,'Arabic visible bounds 24 px vs 25 px, absolute 4%; not waived for pixel quantisation.',8)
    words(c,14,59,'Matching amber camouflages matte remnants. SSIM does not prove transferable ink.',8)
    words(c,14,50,'Native AI validation checks live glyphs/fonts/raster/vector objects and 600-DPI transport.',8)
    words(c,14,41,'Real type is editable per glyph to preserve cylindrical placement; line reflow is limited.',8)
    bar(c,14,25)
    c.save();render_pdf(out)
    return out


def surface_art(model,folder):
    """One raster gesture across cumulative front riser heights; live header copy."""
    spec=json.loads((ROOT/'master/design-spec.json').read_text())
    fm.validate_spec(spec,expected_hash=model['product_spec_hash'])
    measurement=json.loads(fm.fa.MEASUREMENT.read_text())
    # Explicit selection for cardboard: the recorded lit upper mid-tone, not a new colour.
    ground=measurement['ground']['samples'][0];amber=ground['srgb_255']
    provenance={'measurement_sha256':spec['measurement_sha256'],'sample_index':0,'xy_px':ground['xy_px'],'srgb_255':amber,'selection':'Declared lit upper mid-tone, sampled from the concept; flat cardboard review field.'}
    setup();folder=Path(folder);folder.mkdir(exist_ok=True);w=model['envelope'][0];rise=model['rise'];total=sum([6,rise,rise]);height=model['header_height']
    sizes={'header.front':(w,height),'lip.front':(w,6),'riser.1.front':(w,6),'riser.2.front':(w,rise),'riser.3.front':(w,rise),'side.left':(model['envelope'][1],model['seats'][-1]),'side.right':(model['envelope'][1],model['seats'][-1])}
    manifest=[];logical={l['id']:l['logical_text'] for l in spec['graph']['lines']};colours={l['id']:l['colour'] for l in spec['graph']['lines']};image=Image.open(fm.PRESET/'swoosh-flat.png');pw,ph=image.size
    cumulative=0
    for surface,(sw,sh) in sizes.items():
        path=folder/(surface+'.pdf');c=Canvas(str(path),pagesize=(sw*mm,sh*mm));c.setFillColorRGB(*[x/255 for x in amber]);c.rect(0,0,sw*mm,sh*mm,fill=1,stroke=0)
        placement_h=sh;placement_w=placement_h*fm.fa.WIDTH/fm.fa.HEIGHT;offset=0
        if surface.startswith('riser.'):
            placement_h=total;placement_w=total*fm.fa.WIDTH/fm.fa.HEIGHT;offset=-cumulative;cumulative+=sh
        if surface!='lip.front':
            c.saveState();clip=c.beginPath();clip.rect(0,0,sw*mm,sh*mm);c.clipPath(clip,stroke=0,fill=0)
            c.drawImage(str(fm.PRESET/'swoosh-flat.png'),(sw-placement_w-5)*mm,offset*mm,placement_w*mm,placement_h*mm,mask='auto');c.restoreState()
        if surface=='header.front':
            # Approved mark as a vector overlay after the live type page is saved.
            lines=[('SUN','title',24,63),('REPAIR','title',24,48),('SERUM','support',11,37),('arabic','arabic',10,27),('benefit','support',10,18),('care','support',8,11)]
            for key,role,size,y in lines:
                text=logical[key];visual=shape_ar(text,keep_harakat=True) if role=='arabic' else text
                c._code.append('/Span << /ActualText <FEFF'+text.encode('utf-16-be').hex().upper()+'> >> BDC');c.setFont('Fidelity-'+role,size);c.setFillColorRGB(*[v/255 for v in colours[key]]);c.drawString(12*mm,y*mm,visual);c._code.append('EMC')
        c.save()
        if surface=='header.front':
            with fitz.open(path) as doc,fitz.open(ROOT/'master/artwork.pdf') as art:
                # Crop only the approved logo's vector region from the master.
                e=next(e for e in spec['graph']['elements'] if e['id']=='logo');a,z0,b,z1=e['flat_bbox_mm'];clip=fitz.Rect((a+fm.fa.WIDTH/2)*mm,(fm.fa.HEIGHT-z1)*mm,(b+fm.fa.WIDTH/2)*mm,(fm.fa.HEIGHT-z0)*mm)
                doc[0].show_pdf_page(fitz.Rect(12*mm,11*mm,43*mm,18*mm),art,0,clip=clip,keep_proportion=True)
                tmp=path.with_suffix('.tmp.pdf');doc.save(tmp)
            tmp.replace(path)
        with fitz.open(path) as doc:doc[0].get_pixmap(dpi=180).save(str(path.with_suffix('.png')))
        ppi=ph/(placement_h/25.4) if surface!='lip.front' else None
        manifest.append({'surface_id':surface,'size_mm':[sw,sh],'required_copy':[logical[k] for k in ('SUN','REPAIR','SERUM','arabic','benefit','care')] if surface=='header.front' else [],'languages':['EN','AR'] if surface=='header.front' else [],'effective_ppi':ppi,'raster_source_sha256':spec['assets']['swoosh']['sha256'] if ppi else None,'interpolated_source':True,'production_blockers':['DEPENDENCY_FIDELITY_REVIEW','PRESS_PROFILE_UNCONFIRMED'],'colour_ground':provenance,'output_colour_space':'RGB review proof; CMYK separations and press profile unconfirmed'})
    (folder/'surface-bindings.json').write_text(json.dumps({'product_spec_hash':fm.digest(spec),'source':'Only pinned r2 artwork and sampled amber','artwork_is_review_proof':True,'header_copy_colours_srgb_255':colours,'surfaces':manifest},indent=2,ensure_ascii=False)+'\n')
    return manifest


def bottle_cutout():
    im=Image.open(ROOT/'master/projected-master.png').convert('RGBA');mask=Image.new('L',im.size,0);draw=ImageDraw.Draw(mask)
    # Clip to the declared measured contour; preserve the projected image inside.
    points=[(382,95),(629,95),(629,493),(647,493),(647,546),(691,585),(691,1435),(674,1470),(337,1470),(319,1435),(319,585),(365,546),(365,493),(382,493)]
    draw.polygon(points,fill=255);im.putalpha(mask);return im.crop((300,95,710,1470))


def stand_picture(model,folder):
    """Orthographic axonometric 2D face projection; no optical/UV claim."""
    scale=6;W,H=360,385;canvas=np.full((H*scale,W*scale,4),255,np.uint8)
    def pt(x,y,z):return ((32+x+.42*y)*scale,(353-z-.23*y)*scale)
    def face(points,colour):
        cv2.fillConvexPoly(canvas,np.round([pt(*p) for p in points]).astype(np.int32),(*colour,255));cv2.polylines(canvas,[np.round([pt(*p) for p in points]).astype(np.int32)],True,(93,62,39,255),1)
    def tex(image,points):
        rgba=np.asarray(image.convert('RGBA'));hh,ww=rgba.shape[:2]
        dest=np.float32([pt(*p) for p in points]);src=np.float32([[0,0],[ww,0],[ww,hh],[0,hh]])
        matrix=cv2.getPerspectiveTransform(src,dest);warp=cv2.warpPerspective(rgba,matrix,(W*scale,H*scale));alpha=warp[:,:,3:4]/255
        canvas[:,:,:3]=(warp[:,:,:3]*alpha+canvas[:,:,:3]*(1-alpha)).astype(np.uint8)
    w,d,_=model['envelope'];h=model['required_height'];t=model['tread'];sides=folder/'surfaces'
    header_y=d-6;header_bottom=h-100
    tex(Image.open(sides/'header.front.png'),[(0,header_y,h),(w,header_y,h),(w,header_y,header_bottom),(0,header_y,header_bottom)])
    tex(Image.open(sides/'side.right.png'),[(w,d,model['seats'][-1]),(w,0,model['seats'][-1]),(w,0,0),(w,d,0)])
    bottle=bottle_cutout()
    for row in (3,2,1):
        seat=model['seats'][row-1];front=(row-1)*t
        face([(0,front,seat),(w,front,seat),(w,front+t,seat),(0,front+t,seat)],(194,139,77))
        low=0 if row==1 else model['seats'][row-2]
        tex(Image.open(sides/f'riser.{row}.front.png'),[(0,front,seat),(w,front,seat),(w,front,low),(0,front,low)])
        for p in [p for p in model['positions'] if p['row']==row]:
            x,y,z=p['xyz'];bw=410*fm.fa.XS
            tex(bottle,[(x-bw/2,y,z+108),(x+bw/2,y,z+108),(x+bw/2,y,z),(x-bw/2,y,z)])
    # Same-scale separate bottle alongside the assembly.
    tex(bottle,[(278,0,108),(278+410*fm.fa.XS,0,108),(278+410*fm.fa.XS,0,0),(278,0,0)])
    out=folder/'bottle-and-stand.png';Image.fromarray(canvas[:,:,:3]).save(out)
    return out


def construction(model,folder):
    setup();folder=Path(folder);w,d,h=model['envelope'];rise=model['rise'];top=model['required_height'];out=folder/'construction.pdf';c=Canvas(str(out),pagesize=(297*mm,420*mm))
    minimum_label=str(model['minimum_height_mm'])
    if model['minimum_height_mm'] is None:minimum_label='not certified (width refusal)'
    heading(c,'Twelve positions / declared geometry',f"{model['case_id']} - requested {w} x {d} x {h} mm; minimum height {minimum_label}",297,420)
    words(c,14,376,f"Rise {rise} mm; seats {model['seats']}; header 100 mm; cardboard 6 mm PROVISIONAL",8)
    words(c,14,368,'Identity: complete logo/name/descriptor. Opaque bottle silhouettes; eye 550/500.',8)
    words(c,14,358,f"Holes {model['hole']} mm {'square' if model['square'] else 'diameter'}; pitch {model['pitch']:.3f}; tread {model['tread']:.3f} mm.",8)
    if model['square']:words(c,14,350,'PROVISIONAL: decoration 16 x 86 mm, z0..86 (98 minus 12 closure); identity z48..80.',8)
    elif model['stagger']:words(c,14,350,'REFUSED: literal half-pitch offset exceeds width. Rise 6 is diagnostic only.',8)
    else:words(c,14,350,'Measured serum identity proxy; not a measurement of Ginkgo copy. Height datum unresolved.',8)
    ox,oy=35,175;c.setStrokeColorRGB(.15,.2,.22);c.rect(ox*mm,oy*mm,w*mm,d*mm,fill=0,stroke=1)
    for p in model['positions']:
        x,y,z=p['xyz'];c.setFillColorRGB(.96,.93,.87)
        if model['square']:c.rect((ox+x-model['hole']/2)*mm,(oy+y-model['hole']/2)*mm,model['hole']*mm,model['hole']*mm,fill=1,stroke=1)
        else:c.circle((ox+x)*mm,(oy+y)*mm,model['hole']/2*mm,fill=1,stroke=1)
        words(c,ox+x-7,oy+y-1,p['id'],7)
    words(c,35,165,'Plan at 1:1; front lip below. Exact circular/square holes shown.',8);bar(c,35,149)
    y=125
    for key in ('pass_point','median','secondary','far_advisory'):
        result=model['sightlines'].get(key)
        if result:
            words(c,14,y,f"{key}: eye {result['eye_above_base_mm']}/{result['front_distance_mm']} mm; identities {'clear' if result['passed'] else 'not certified'}",8);y-=7
            rows=' / '.join(f"r{r['row']}: {r['decoration_fraction_lower']:.1%}–{r['decoration_fraction_upper']:.1%}" for r in result['rows'])
            words(c,14,y,rows,7);y-=9
    words(c,14,39,'Decoration fractions: nominal cylindrical artwork area; shoulder conformity unresolved.',7)
    words(c,14,31,'Bounded shoulder/collar approximations fail closed; no load, join or machine-cut approval.',7)
    words(c,14,23,'Cut layout + BOM deferred by owner cut order. All inputs and original brief remain in JSON.',7)
    c.showPage()
    height_role='certified proposal'
    if model['stagger']:height_role='diagnostic only - width refused'
    heading(c,'Side elevation / heights',f"Rise {rise}; seats {model['seats']}; header 100; height {top} mm ({height_role})",297,420)
    ox,oy=55,55
    for i,seat in enumerate(model['seats']):
        c.setFillColorRGB(.75,.6,.42);c.rect((ox+i*model['tread'])*mm,oy*mm,model['tread']*mm,seat*mm,fill=1,stroke=1)
        cy=(i+.5)*model['tread'];r=model['product_width']/2
        if model['square']:c.rect((ox+cy-r)*mm,(oy+seat)*mm,2*r*mm,model['product_height']*mm,fill=0,stroke=1)
        else:
            path=c.beginPath()
            pts=[]
            for part in model['profile']:pts.extend([(cy-part['r0'],seat+part['z0']),(cy-part['r1'],seat+part['z1'])])
            for part in reversed(model['profile']):pts.extend([(cy+part['r1'],seat+part['z1']),(cy+part['r0'],seat+part['z0'])])
            path.moveTo((ox+pts[0][0])*mm,(oy+pts[0][1])*mm)
            for x,z in pts[1:]:path.lineTo((ox+x)*mm,(oy+z)*mm)
            path.close();c.drawPath(path,stroke=1,fill=0)
        words(c,ox+i*model['tread'],oy+seat+model['product_height']+4,f"seat {seat}",7)
    c.rect((ox+d-6)*mm,oy*mm,6*mm,top*mm,fill=0,stroke=1);c.setDash(3,2);c.line((ox-8)*mm,(oy+h)*mm,(ox+d+8)*mm,(oy+h)*mm);c.setDash()
    if model['stagger']:words(c,14,44,f"Dashed: requested {h} mm. Diagnostic {top} mm; no solution certified.",8)
    else:words(c,14,44,f"Dashed: requested {h} mm. Required {top} mm; difference {top-h:+g} mm.",8)
    if model['square']:identity_note='146: separate provisional identity z48-80.'
    else:identity_note='Serum r2 identity; 144 uses a declared proxy, not measured Ginkgo copy.'
    words(c,14,35,identity_note,7);bar(c,14,21);c.save();render_pdf(out,120)
    return out


def stand_sheet(model,folder):
    setup();folder=Path(folder);surface_art(model,folder/'surfaces');picture=stand_picture(model,folder);c=Canvas(str(folder/'presentation.pdf'),pagesize=(420*mm,450*mm))
    heading(c,'SUN REPAIR / bottle + twelve-bottle display','DEPENDENT REVIEW PROOF — extracted matte and Arabic scale remain unresolved',420,450)
    image_on(c,picture,3,19,360,385)
    words(c,14,23,f"322 mm proposal: rise 54, seats 6/60/114, header 100. 2D face projection; same-scale bottle.",8)
    words(c,14,14,'Amber printed cardboard; glass/chrome from reference. Cut/join/load approval pending.',8)
    c.save();render_pdf(folder/'presentation.pdf',140)


def build():
    fidelity_sheet()
    for case in ('family','144','146','family-stagger'):
        folder=ROOT/('stand-'+case);m=json.loads((folder/'assembly-spec.json').read_text());construction(m,folder)
        if case=='family':stand_sheet(m,folder)

if __name__=='__main__':build()
