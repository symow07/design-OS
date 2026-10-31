"""One line-geometry scene -> SVG and PDF, with exported bottle identities."""
from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from apps.pipeline.services.assembly_spec import APP_ROOT
from .stepped_display import value

INK = "#203844"
BLUE = "#BFD3DB"
PAPER = "#F7F5EF"
RED = "#A83337"
LIGHT = "#E3E7E5"


class Scene:
    def __init__(self, width, height):
        self.width,self.height,self.items = width,height,[]
        self.view,self.bottle = None,None

    def poly(self, points, fill="none", stroke=INK, width=.25, dashed=False):
        self.items.append(dict(kind="poly",points=points,fill=fill,stroke=stroke,width=width,dashed=dashed,view=self.view,bottle=self.bottle))

    def line(self, a,b, **kwargs):
        self.poly([a,b],**kwargs)

    def text(self,x,y,words,size=2.6,color=INK):
        self.items.append(dict(kind="text",x=x,y=y,text=str(words),size=size,color=color,view=self.view,bottle=self.bottle))

    def assert_bounds(self):
        for item in self.items:
            if item["kind"]=="poly": points=item["points"]
            else:
                length=pdfmetrics.stringWidth(item["text"],"AssemblySans",item["size"])
                points=[(item["x"],item["y"]-item["size"]),(item["x"]+length,item["y"])]
            if any(x<0 or y<0 or x>self.width or y>self.height for x,y in points):
                raise ValueError(f"Drawing content outside sheet: {item}")

    def svg(self, path):
        self.assert_bounds()
        out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}mm" height="{self.height}mm" viewBox="0 0 {self.width} {self.height}">']
        current=None
        for item in self.items:
            key=(item["view"],item["bottle"])
            if key != current:
                if current is not None:out.append('</g>')
                attrs=f' data-view="{html.escape(key[0] or "sheet")}"'
                if key[1]:attrs+=f' data-bottle-id="{key[1]}" id="{key[0]}-bottle-{key[1]}"'
                out.append('<g'+attrs+'>');current=key
            if item["kind"]=="poly":
                pts=' '.join(f'{x:.5f},{y:.5f}' for x,y in item['points'])
                kind='polygon' if len(item['points'])>2 else 'polyline'
                out.append(f'<{kind} points="{pts}" fill="{item["fill"]}" stroke="{item["stroke"]}" stroke-width="{item["width"]}"'+(' stroke-dasharray="1.2 1"' if item['dashed'] else '')+'/>')
            else:
                out.append(f'<text x="{item["x"]:.5f}" y="{item["y"]:.5f}" font-size="{item["size"]}" font-family="Arial, sans-serif" fill="{item["color"]}">{html.escape(item["text"])}</text>')
        if current is not None:out.append('</g>')
        out.append('</svg>');path.write_text('\n'.join(out)+'\n')

    def pdf(self,c):
        self.assert_bounds()
        c.setPageSize((self.width*mm,self.height*mm))
        current=None
        for item in self.items:
            key=(item['view'],item['bottle'])
            if key != current:
                if current is not None:c._code.append('EMC')
                c._code.append('/Assembly << /View (%s) /Bottle (%s) >> BDC' % (key[0] or 'sheet',key[1] or 'none'))
                current=key
            if item['kind']=='poly':
                c.setStrokeColor(item['stroke']);c.setLineWidth(item['width']*mm);c.setDash([1.2*mm,mm] if item['dashed'] else [])
                if item['fill']!='none':c.setFillColor(item['fill'])
                p=c.beginPath();pts=item['points'];p.moveTo(pts[0][0]*mm,(self.height-pts[0][1])*mm)
                for x,y in pts[1:]:p.lineTo(x*mm,(self.height-y)*mm)
                if len(pts)>2:p.close()
                c.drawPath(p,stroke=int(item['width']>0),fill=int(item['fill']!='none'))
            else:
                c.setFillColor(item['color']);c.setFont('AssemblySans',item['size']*mm)
                c.drawString(item['x']*mm,(self.height-item['y'])*mm,item['text'])
        if current is not None:c._code.append('EMC')
        c.showPage()


def circle(cx,cy,r,z,n=24):
    return [(cx+r*math.cos(i*2*math.pi/n),cy+r*math.sin(i*2*math.pi/n),z) for i in range(n)]


def project(p,kind):
    x,y,z=p
    if kind=='plan':return x,y
    if kind=='front':return x,-z
    if kind in ('side','section'):return y,-z
    return (x+y)*math.sqrt(3)/2,(x-y)/2-z


def cuboid(sc,box,transform,fill=LIGHT):
    x,y,z,w,d,h=box
    points=[(x,y,z),(x+w,y,z),(x+w,y+d,z),(x,y+d,z),(x,y,z+h),(x+w,y,z+h),(x+w,y+d,z+h),(x,y+d,z+h)]
    for face in ((0,1,5,4),(1,2,6,5),(4,5,6,7)):
        sc.poly([transform(points[i]) for i in face],fill=fill)


def dimension(sc,a,b,label,offset=5.):
    if abs(a[1]-b[1])<.01:
        aa,bb=(a[0],a[1]+offset),(b[0],b[1]+offset)
        sc.line(a,(aa[0],aa[1]+2),width=.15);sc.line(b,(bb[0],bb[1]+2),width=.15)
        sc.line(aa,bb,width=.18)
        for p in (aa,bb):sc.line((p[0]-1,p[1]-1),(p[0]+1,p[1]+1),width=.18)
        sc.text((aa[0]+bb[0])/2-len(label)*.65,aa[1]-1,label,2.4)
    else:
        aa,bb=(a[0]+offset,a[1]),(b[0]+offset,b[1])
        sc.line(a,(aa[0]+2,aa[1]),width=.15);sc.line(b,(bb[0]+2,bb[1]),width=.15);sc.line(aa,bb,width=.18)
        for p in (aa,bb):sc.line((p[0]-1,p[1]-1),(p[0]+1,p[1]+1),width=.18)
        sc.text(aa[0]+1,(aa[1]+bb[1])/2,label,2.3)


def view(sc,spec,model,kind,ox,oy,scale):
    sc.view=kind
    tr=lambda p:(ox+project(p,kind)[0]*scale,oy+project(p,kind)[1]*scale)
    w,d,h=model['envelope_requested'];r=spec.rules;e=spec.product_envelope
    thickness=value(r,'deck_thickness_mm');tread=model['tread_mm'];seats=[q['seat_elevation_mm']['value'] for q in model['decks']]
    drawing_h=max(h,seats[-1]+value(e,'height_mm'))
    if not model['positions']:
        sc.text(ox,oy,'REFUSED: impossible footprint; no substitute geometry.',3.5,RED);return
    # Structure primitives share these exact dimensions in every projection.
    cuboid(sc,(0,0,0,w,d,value(r,'base_thickness_mm')),tr)
    if kind=='isometric':
        cuboid(sc,(0,d-value(r,'header_thickness_mm'),0,w,value(r,'header_thickness_mm'),h),tr,'#D2D9D6')
    for row in reversed(range(3)):
        z=seats[row]
        cuboid(sc,(0,row*tread,max(0,z-thickness),w,tread,thickness),tr)
        cuboid(sc,(0,row*tread,0 if row==0 else seats[row-1],w,thickness,z if row==0 else model['uniform_rise_mm']),tr,'#D9DFDC')
        # Collar top with explicit vector openings; solid seat is below.
        top=z+value(r,'collar_offset_mm')+thickness
        sc.poly([tr(p) for p in ((0,row*tread,top),(w,row*tread,top),(w,(row+1)*tread,top),(0,(row+1)*tread,top))],fill='#EDF0ED')
        for p in [p for p in model['positions'] if p['row']==row+1]:
            x,y=p['x_mm'],p['y_mm'];size=spec.holes.derived_size_mm.value
            ring=circle(x,y,size/2,top) if spec.holes.profile.value=='circle' else [(x-size/2,y-size/2,top),(x+size/2,y-size/2,top),(x+size/2,y+size/2,top),(x-size/2,y+size/2,top)]
            sc.poly([tr(q) for q in ring],fill=PAPER,width=.18)
    if kind!='isometric':cuboid(sc,(0,d-value(r,'header_thickness_mm'),0,w,value(r,'header_thickness_mm'),h),tr,'none')
    for xx in (0,w-thickness):
        side=[(xx,0,0),(xx,d,0),(xx,d,seats[2]),(xx,2*tread,seats[2]),(xx,2*tread,seats[1]),(xx,tread,seats[1]),(xx,tread,seats[0]),(xx,0,seats[0])]
        sc.poly([tr(q) for q in side],fill='none',width=.35)
    # Header print band is a surface outline, not artwork.
    if kind in ('front','isometric'):
        yy=d-value(r,'header_thickness_mm')
        sc.poly([tr(q) for q in ((0,yy,h-value(r,'header_height_mm')),(w,yy,h-value(r,'header_height_mm')),(w,yy,h),(0,yy,h))],fill='none',stroke='#527F8D',width=.3,dashed=True)
        a=tr((5,yy,h-value(r,'header_height_mm')+10));sc.text(a[0],a[1],'header.front / artwork pending',2.3)
    # Draw far rows first. Four overlapping side projections are intentional;
    # the side and section identify each row as four positions, not one bottle.
    for p in sorted(model['positions'],key=lambda p:(-p['row'],p['col'])):
        sc.bottle=p['id'];x,y,z=p['x_mm'],p['y_mm'],p['z_mm'];pw=value(e,'width_mm');ph=value(e,'height_mm')
        if kind=='plan':
            outline=circle(x,y,pw/2,z) if e.profile.value=='circle' else [(x-pw/2,y-pw/2,z),(x+pw/2,y-pw/2,z),(x+pw/2,y+pw/2,z),(x-pw/2,y+pw/2,z)]
            sc.poly([tr(q) for q in outline],fill=BLUE,width=.2)
            a=tr((x,y,z));sc.line((a[0]-2,a[1]),(a[0]+2,a[1]),width=.15);sc.line((a[0],a[1]-2),(a[0],a[1]+2),width=.15)
            sc.text(a[0]-3.7,a[1]+5,p['id'],2.2)
        elif kind=='isometric':
            if e.profile.value=='circle':
                bodytop=ph-value(e,'cap_height_mm')-value(e,'shoulder_height_mm')
                levels=[(0.,pw/2),(bodytop,pw/2),(ph-value(e,'cap_height_mm'),value(e,'collar_width_mm')/2),
                        (ph-value(e,'cap_height_mm')+value(e,'collar_height_mm'),value(e,'collar_width_mm')/2),
                        (ph-value(e,'cap_height_mm')+value(e,'collar_height_mm'),value(e,'cap_width_mm')/2),(ph,value(e,'cap_width_mm')/2)]
                for (za,ra),(zb,rb) in zip(levels,levels[1:]):
                    aa,bb=circle(x,y,ra,z+za,16),circle(x,y,rb,z+zb,16)
                    # Visible front and right semicircle; flat fill, no materials.
                    for i in (*range(10,16),*range(0,2)):
                        j=(i+1)%16;sc.poly([tr(q) for q in (aa[i],aa[j],bb[j],bb[i])],fill=BLUE if zb<=bodytop else '#D9E0E1',stroke=BLUE if zb<=bodytop else '#D9E0E1',width=0)
                    for i in (10,2):sc.line(tr(aa[i]),tr(bb[i]),width=.18)
                    sc.poly([tr(q) for q in bb],fill=BLUE if zb<=bodytop else '#D9E0E1',width=.18)
            else:cuboid(sc,(x-pw/2,y-pw/2,z,pw,pw,ph),tr,BLUE)
            a=tr((x,y-pw/2,z+ph+5));sc.text(a[0]-3.5,a[1],p['id'],2.1)
        else:
            # Front/side profile uses the actual Day 2 proposal dimensions.
            axis=x if kind=='front' else y
            if e.profile.value=='circle':
                cap=value(e,'cap_height_mm');collar=value(e,'collar_width_mm');cw=value(e,'cap_width_mm');ch=value(e,'collar_height_mm');shoulder=value(e,'shoulder_height_mm')
                profile=[(-pw/2,0),(pw/2,0),(pw/2,ph-cap-shoulder),(collar/2,ph-cap),(collar/2,ph-cap+ch),(cw/2,ph-cap+ch),(cw/2,ph),(-cw/2,ph),(-cw/2,ph-cap+ch),(-collar/2,ph-cap+ch),(-collar/2,ph-cap),(-pw/2,ph-cap-shoulder)]
            else:profile=[(-pw/2,0),(pw/2,0),(pw/2,ph),(-pw/2,ph)]
            sc.poly([(ox+(axis+dx)*scale,oy-(z+dz)*scale) for dx,dz in profile],fill='none' if p['col']!=2 and kind!='front' else BLUE,width=.22)
            if kind=='front' and e.decoration_bottom_mm.value is not None:
                lo=e.decoration_bottom_mm.value;hi=lo+e.decoration_height_mm.value
                sc.poly([(ox+(axis+dx)*scale,oy-(z+dz)*scale) for dx,dz in [(-pw*.42,lo),(pw*.42,lo),(pw*.42,hi),(-pw*.42,hi)]],fill='none',stroke='#527F8D',width=.15,dashed=True)
            if kind=='front' or p['col']==2:
                sc.text(ox+axis*scale-3.5,oy-(z+ph+5)*scale,p['id'] if kind=='front' else f'Row {p["row"]}: x4',2.2)
        sc.bottle=None
    cuboid(sc,(0,0,seats[0],w,value(r,'lip_thickness_mm'),value(r,'lip_height_mm')),tr,'none')
    if kind=='plan':
        dimension(sc,tr((0,d,0)),tr((w,d,0)),f'{w:g} mm',7)
        dimension(sc,tr((w,0,0)),tr((w,d,0)),f'{d:g} mm',7)
        x2=model['positions'][1]['x_mm'];sc.line(tr((x2,0,0)),tr((x2,d,0)),stroke=RED,width=.18,dashed=True)
        sc.text(ox,oy-9,'PLAN / FRONT at row 1 edge',3)
        sc.text(ox,oy+d*scale+15,'REAR / header at row 3 edge',2.4)
        for yy in (0,d):
            a=tr((x2,yy,0))
            sc.line((a[0],a[1]),(a[0]+7,a[1]),stroke=RED,width=.25)
            sc.poly([(a[0]+7,a[1]),(a[0]+5,a[1]-1),(a[0]+5,a[1]+1)],fill=RED,stroke=RED,width=.15)
            sc.text(a[0]-4,a[1]-1,'A',2.5,RED)
    elif kind=='front':
        dimension(sc,tr((0,0,0)),tr((w,0,0)),f'{w:g} mm',8)
        dimension(sc,tr((w,0,0)),tr((w,0,h)),f'{h:g} mm',8)
        sc.text(ox,oy-drawing_h*scale-12,'FRONT ELEVATION',3)
    elif kind in ('side','section'):
        dimension(sc,tr((0,0,0)),tr((0,d,0)),f'{d:g} mm',8)
        sc.text(ox,oy-drawing_h*scale-12,'SECTION A-A / COLUMN 2' if kind=='section' else 'SIDE ELEVATION',3)
        for row,z in enumerate(seats):sc.text(ox+(row*tread+3)*scale,oy-z*scale+5,f'z {z:g}',2.2)
        if kind=='section':
            for row,z in enumerate(seats):
                for yy in range(0,max(1,int(tread)-3),8):
                    sc.line(tr((0,row*tread+yy,max(0,z-thickness))),tr((0,row*tread+yy+4,z)),width=.12)
    else:sc.text(ox,oy-(drawing_h+d*.5+15)*scale,'ASSEMBLED ISOMETRIC / 12 POSITIONS',3)
    sc.view=None


def header(sc,title,spec,model,scale):
    sc.text(14,16,'BBROSE / STEPPED COUNTERTOP KIT',5.2)
    sc.text(14,25,title,3.5)
    status='PROVISIONAL GEOMETRY SOLUTION' if model['status']=='solution_provisional' else 'REFUSED / DIAGNOSTIC GEOMETRY ONLY'
    sc.text(14,33,status,3.2,INK if model['status']=='solution_provisional' else RED)
    sc.text(sc.width-100,16 if sc.width>=400 else 42,f'Case {spec.case_id.value} / revision {spec.revision}',2.8)
    sc.text(sc.width-100,23 if sc.width>=400 else 49,f'Scale {scale}; dimensions in mm',2.8)


def footer(sc,spec,model):
    y=sc.height-43
    sc.line((14,y-4),(sc.width-14,y-4),width=.2)
    lines=[f'<< PROVISIONAL >> Cardboard 6 mm (grade unconfirmed); solid seats + separate collars; uniform rise {model["uniform_rise_mm"]:g}; tread {model["tread_mm"]:.3f}; minimum web 4; back web 10; header 100 high / 6 thick / 90 deg.',
           'Front lip 6 high / 6 thick; collar top 6 above seat; safe margins <=4; bleed 3. Eye: 500 in front, 350 above base; ray margin 0.25. No artwork binding.',
           'Bottle silhouette: proposal, not stock drawing. Serum cap 32 x21; collar 3.4 x23.4; shoulder 5. 108 mm datum unresolved; decoration test region z7..67, arc32.',
           'Mass / centre of gravity / tip / retention / joints / supplier thickness / manufacture: UNRESOLVED. No load claim. Full assumption register is included.',
           'Original 144 and 146 envelopes are never changed. A taller family proposal is separate. Day 4 starts with the concept147 fidelity master.']
    if spec.case_id.value=='146':lines[2]='Kiss Me: declared 16 x16 x98 envelope, not the serum. Closure shape and decoration map unresolved; no S-2422 mapping is transferred.'
    for i,line in enumerate(lines):sc.text(14,y+i*4.2,line,2.45 if sc.width>400 else 1.7)
    bar_y=sc.height-9;sc.line((14,bar_y),(64,bar_y),width=.3)
    for x in (14,64):sc.line((x,bar_y-2),(x,bar_y+2),width=.3)
    sc.text(68,bar_y+1,'50 mm calibration bar / print at 100%, no Fit to page',2.5)


def sheets(spec,model):
    w,d,h=model['envelope_requested']
    drawn_h=max(h,model['envelope_realised'][2]) if model['envelope_realised'] else h
    baseline=max(364,55+d*.5+35+drawn_h*.5)
    side_x=20+w*.5+35;section_x=side_x+d*.5+40
    iso_x=section_x+d*.5+40
    comparison=Scene(max(594,iso_x+(w+d)*.433+50),max(420,baseline+60))
    header(comparison,'Plan, elevations, section and assembled view',spec,model,'1:2')
    view(comparison,spec,model,'plan',20,55,.5)
    for kind,x in [('front',20),('side',side_x),('section',section_x)]:view(comparison,spec,model,kind,x,baseline,.5)
    view(comparison,spec,model,'isometric',iso_x,baseline-w*.25,.5)
    footer(comparison,spec,model)
    plan=Scene(max(420,w+50),max(297,65+d+80))
    header(plan,'Printable plan / exact scale 1:1',spec,model,'1:1')
    view(plan,spec,model,'plan',20,65,1.)
    if model['positions']:
        plan.text(20,65+d+20,f'Holes: 12 x {spec.holes.profile.value} {spec.holes.derived_size_mm.value:g}; x pitch {model["positions"][1]["x_mm"]-model["positions"][0]["x_mm"]:.3f}; y pitch {model["tread_mm"]:.3f}',2.8)
        plan.text(20,65+d+26,f'Edge web x {model["actual_edge_web_mm"]:.3f}; tread edge {(model["tread_mm"]-spec.holes.derived_size_mm.value)/2:.3f}. See exact centre schedule.',2.8)
    footer(plan,spec,model)
    schedules=Scene(420,297);header(schedules,'Hole centres and preliminary parts / no cut files',spec,model,'schedule')
    schedules.text(14,47,'ID / x / y / seat z / opening (mm)',3.2)
    for i,p in enumerate(model['hole_schedule']):schedules.text(14,55+i*6,f'{p["id"]}   {p["x_mm"]:.3f}   {p["y_mm"]:.3f}   {p["z_mm"]:.3f}   {p["profile"]} {p["size_mm"]:g}',2.8)
    schedules.text(155,47,'PRELIMINARY PARTS / nominal envelopes only',3.2)
    for i,p in enumerate(model['preliminary_parts']):
        schedules.text(155,55+i*7.4,f'{p["qty"]} x {p["part"]} / '+ ' x '.join(f'{v:.3f}' for v in p['nominal_size_mm'])+' mm',2.5)
    schedules.text(14,143,'SIGHTLINE / guaranteed visible fraction of the complete front region',3.2)
    for i,row in enumerate(model['sightline_table']):
        f=row['visible_fraction_lower_bound'];schedules.text(14,152+i*6,f'Row {row["row"]}: '+('UNRESOLVED' if f is None else f'{100*f:.2f}%')+' / '+('clear' if row['passed'] else 'refused'),2.8)
    schedules.text(14,178,'Envelope checks',3.2)
    for i,c in enumerate(model['checks'][:5]):schedules.text(14,186+i*7,c['words'],2.4,INK if c['passed'] else RED)
    footer(schedules,spec,model)
    out=[comparison,plan,schedules]
    entries=[f'{p["field"]}: {p["value"]} / {p["source"]}' for p in model['provenance']]
    entries += [f'UNRESOLVED {p["field"]}: {p["reason"]}' for p in model['unresolved']]
    import textwrap
    lines=[]
    for entry in entries:
        lines.extend(textwrap.wrap(entry,width=185,break_long_words=True) or [""])
    for start in range(0,len(lines),42):
        sheet=Scene(420,297);header(sheet,'Assumption and unresolved-fact register',spec,model,'text')
        for i,line in enumerate(lines[start:start+42]):sheet.text(14,47+i*4.6,line,2.25)
        footer(sheet,spec,model);out.append(sheet)
    return out


def assert_svg_count(path,expected=12):
    root=ET.parse(path).getroot();views={}
    for g in root.iter():
        if 'data-bottle-id' not in g.attrib:continue
        if not any(x.tag.endswith(('polygon','polyline')) for x in g):raise ValueError('Bottle identity has no drawn geometry.')
        views.setdefault(g.attrib['data-view'],[]).append(g.attrib['data-bottle-id'])
    if not views:raise ValueError('Export contains no bottle instances.')
    for ids in views.values():
        if len(ids)!=expected or len(set(ids))!=expected:raise ValueError(f'Export count {len(ids)}, expected {expected} distinct bottles.')
    return {k:len(v) for k,v in views.items()}


def emit(spec,model,folder):
    font=APP_ROOT/'static/fonts/brand2026/Poppins/Poppins-Regular.ttf'
    if 'AssemblySans' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('AssemblySans',str(font)))
    pages=sheets(spec,model)
    pages[0].svg(folder/'comparison.svg');pages[1].svg(folder/'plan.svg')
    for kind in ('front','side','section','isometric'):
        w,d,h=model['envelope_requested']
        drawn_h=max(h,model['envelope_realised'][2]) if model['envelope_realised'] else h
        origin=30
        scene=Scene(max(420,origin+(w+d)*.433+50 if kind=='isometric' else 60+max(w,d)*.5),max(420,drawn_h*.5+(w+d)*.25+140))
        header(scene,kind.upper(),spec,model,'1:2')
        view(scene,spec,model,kind,origin,70+drawn_h*.5+(d*.25 if kind=='isometric' else 0),.5);footer(scene,spec,model);scene.svg(folder/(kind+'.svg'))
    c=canvas.Canvas(str(folder/'drawing-set.pdf'),pageCompression=1,invariant=1)
    for page in pages:page.pdf(c)
    c.save()
    c=canvas.Canvas(str(folder/'plan-at-100-percent.pdf'),pageCompression=1,invariant=1);pages[1].pdf(c);c.save()
    checks={}
    if model['positions']:
        for name in ('comparison','plan','front','side','section','isometric'):checks[name]=assert_svg_count(folder/(name+'.svg'))
    import fitz
    with fitz.open(folder/'drawing-set.pdf') as doc:
        doc[0].get_pixmap(dpi=120,alpha=False).save(folder/'comparison.png')
        if model['positions']:
            for page in list(doc)[:2]:
                groups={}
                for viewname,ident in re.findall(rb'/Assembly << /View \(([^)]+)\) /Bottle \((r\d-c\d)\) >> BDC',page.read_contents()):groups.setdefault(viewname,[]).append(ident)
                if not groups or any(len(v)!=12 or len(set(v))!=12 for v in groups.values()):raise ValueError('PDF bottle instance count failed.')
    return checks
