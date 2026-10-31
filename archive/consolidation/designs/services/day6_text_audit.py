"""Day 6 TRACED_TEXT for the D1 stand surfaces (review finding F7, prompt §2.2).

Positive controls are baked from the header package itself at 300 PPI and at
the copy's real size, so the OCR half of the instrument is proven able to see
copy of exactly this scale before any surface is judged. Every surface is then
inspected in all three editable formats (PDF, SVG, native AI). One negative —
the header PDF with its live copy replaced by its own glyph outlines — must
fail. Everything is written under docs/audit/day-6/stand/text-audit/ and into
each surface folder as TRACED_TEXT.json; nothing under day-1…day-5 is touched.
"""
from pathlib import Path
import io,json,subprocess
import fitz,numpy as np
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import traced_text as tt,fidelity_assets as fa
from .day6_native import ROOT as SURFACES,SURFACES as ORDER

STAND=fa.ROOT/'docs/audit/day-6/stand'
AUDIT=STAND/'text-audit'
CONTROL_LINES=('SUN','arabic')
CONTROL_PPI=300
LOOK_ALIKE_LIMIT=3.
LOOK_ALIKE_DPI=300
PACKAGE=('artwork.pdf','artwork.svg','artwork-pdf-compatible.ai','artwork-native.ai','artwork-native-validation.json')
TESSDATA_SOURCES={'eng':Path('/opt/homebrew/share/tessdata/eng.traineddata'),'ara':fa.ROOT/'docs/audit/day-5/ocr/ara.traineddata'}


def tessdata(root):
    data=Path(root)/'tessdata';data.mkdir(parents=True,exist_ok=True)
    for language,source in TESSDATA_SOURCES.items():
        if not source.exists():raise FileNotFoundError(f'{language} traineddata is missing at {source}.')
        target=data/(language+'.traineddata')
        if not target.exists():target.symlink_to(source)
    return data


def _rgb(path,dpi,clip=None):
    with fitz.open(path) as doc:
        pix=doc[0].get_pixmap(dpi=dpi,clip=clip,alpha=False)
        return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)[:,:,:3].astype(float)


def text_plane(pdf_path,clip,*,ppi=CONTROL_PPI):
    """Bake the live copy inside `clip` at its real size: exactly the pixels that vanish when the text is removed."""
    with fitz.open(pdf_path) as doc:
        page=doc[0];rect=fitz.Rect(clip)&page.rect
        full=page.get_pixmap(dpi=ppi,clip=rect,alpha=False);a=np.frombuffer(full.samples,np.uint8).reshape(full.height,full.width,full.n)[:,:,:3].astype(float)
        with fitz.open(stream=doc.tobytes(),filetype='pdf') as stripped:
            stripped[0].add_redact_annot(rect,fill=None,cross_out=False);stripped[0].apply_redactions(images=0,graphics=0,text=0)
            bare=stripped[0].get_pixmap(dpi=ppi,clip=rect,alpha=False);b=np.frombuffer(bare.samples,np.uint8).reshape(bare.height,bare.width,bare.n)[:,:,:3].astype(float)
    if a.shape!=b.shape:raise ValueError('The text-removed render changed shape; the bake cannot be aligned.')
    difference=np.abs(a-b).max(axis=2);peak=float(difference.max())
    if peak<=4:raise ValueError('Removing the live text changed no pixel; there is no text plane to bake.')
    alpha=np.clip(difference/peak*255,0,255).astype(np.uint8)
    image=Image.fromarray(np.dstack([a.astype(np.uint8),alpha]),'RGBA')
    record={'ppi':ppi,'clip_points':list(rect),'size_px':[int(a.shape[1]),int(a.shape[0])],'size_mm':[float(rect.width/tt.MM),float(rect.height/tt.MM)],'peak_difference':peak,
            'alpha':'max-channel difference between the live render and the text-redacted render of the same PDF, normalised to its peak; colours are the live render'}
    return image,record


def positive_controls(header,root,data):
    header=Path(header);spec=json.loads((header/'design-spec.json').read_text());lines=tt.expected_lines(spec,header/'assets');live=tt.pdf_live(header/'artwork.pdf',lines)
    controls=[]
    for line,result in zip(lines,live['lines']):
        if line['id'] not in CONTROL_LINES:continue
        if not result['live_font_and_position']:raise ValueError(f'Header line {line["id"]} is not live in artwork.pdf; no positive control can be baked from it.')
        image,bake=text_plane(header/'artwork.pdf',result['bbox_points']);image.save(Path(root)/(line['id']+'-baked-positive-300ppi.png'))
        ocr=tt.ocr_layers([image],[line['logical_text']],tessdata=data)
        controls.append({'id':line['id'],'copy':line['logical_text'],'source':'header.front/artwork.pdf','bake':bake,'detected':bool(ocr['hits']),'result':ocr})
    return controls,live


class _OutlinePen(BasePen):
    """Glyph contours straight onto a reportlab path at the run's own matrix (quadratics become cubics in BasePen)."""
    def __init__(self,glyph_set,path,scale,origin):
        super().__init__(glyph_set);self.path=path;self.sx,self.sy=scale;self.tx,self.ty=origin
    def _xy(self,p):return self.tx+p[0]*self.sx,self.ty+p[1]*self.sy
    def _moveTo(self,p):self.path.moveTo(*self._xy(p))
    def _lineTo(self,p):self.path.lineTo(*self._xy(p))
    def _curveToOne(self,p1,p2,p3):self.path.curveTo(*self._xy(p1),*self._xy(p2),*self._xy(p3))
    def _closePath(self):self.path.close()


def outline_overlay(graph,fonts):
    """Every copy run drawn as filled glyph outlines — no text operators — on a page of the graph's size."""
    w,h=graph['width_mm'],graph['height_mm'];buffer=io.BytesIO();canvas=Canvas(buffer,pagesize=(w*mm,h*mm));count=0
    faces={role:TTFont(path) for role,path in fonts.items()}
    for line in graph['lines']:
        canvas.setFillColorRGB(*[v/255 for v in line['colour']]);path=canvas.beginPath()
        for run in line['runs']:
            font=faces[run['font_role']];glyph_set=font.getGlyphSet();unit=1000/font['head'].unitsPerEm
            scale=(run['scale_x_mm_per_1000pt_unit']*mm*unit,run['scale_y_mm_per_1000pt_unit']*mm*unit);origin=(run['x_mm']*mm,run['baseline_z_mm']*mm)
            glyph_set[font.getBestCmap()[ord(run['text'])]].draw(_OutlinePen(glyph_set,path,scale,origin));count+=1
        canvas.drawPath(path,fill=1,stroke=0,fillMode=1)
    canvas.save()
    for font in faces.values():font.close()
    return buffer.getvalue(),count


def outline_copy(source_pdf,spec,fonts,destination,*,dpi=LOOK_ALIKE_DPI):
    """A copy of `source_pdf` whose live copy is replaced by its own outlines: alike to the eye, traced in law."""
    overlay,count=outline_overlay(spec['graph'],fonts)
    with fitz.open(source_pdf) as doc,fitz.open(stream=overlay,filetype='pdf') as paths:
        page=doc[0];page.add_redact_annot(page.rect,fill=None,cross_out=False);page.apply_redactions(images=0,graphics=0,text=0)
        page.show_pdf_page(page.rect,paths,0);doc.save(destination,garbage=3,deflate=True)
    a=_rgb(source_pdf,dpi);b=_rgb(destination,dpi)
    if a.shape!=b.shape:raise ValueError('The outlined copy renders at a different size from its source.')
    look=float(np.abs(a-b).mean())
    return {'runs_outlined':count,'look_alike_dpi':dpi,'look_alike_mae':look,'look_alike_limit':LOOK_ALIKE_LIMIT,'looks_alike':look<LOOK_ALIKE_LIMIT}


def negative_control(header,root,data):
    header=Path(header);spec=json.loads((header/'design-spec.json').read_text());lines=tt.expected_lines(spec,header/'assets')
    fonts={role:header/'assets'/record['filename'] for role,record in spec['fonts'].items()}
    folder=Path(root)/'negatives'/'header-outlined-copy';folder.mkdir(parents=True,exist_ok=True);target=folder/'artwork.pdf'
    construction=outline_copy(header/'artwork.pdf',spec,fonts,target)
    live=tt.pdf_live(target,lines);ocr=tt.ocr_layers(tt.pdf_rasters(target),[line['logical_text'] for line in lines],tessdata=data)
    verdict=live['passed'] and ocr['passed']
    return {'id':'header-outlined-copy','file':str(target.relative_to(fa.ROOT)),'source':'header.front/artwork.pdf',
            'construction':'live text removed by redaction (graphics and images kept); every run re-drawn as filled glyph outlines from the pinned faces at the run matrix',
            'build':construction,'pdf_live':live,'raster_ocr':ocr,'matched_visible_runs':sum(l['matched_visible_runs'] for l in live['lines']),'expected_runs':sum(l['expected_runs'] for l in live['lines']),
            'traced_text_verdict':'passed' if verdict else 'failed','expected':'failed','failed_as_required':not verdict}


def inspect_surface(folder,*,data,controls_passed):
    folder=Path(folder);report=tt.inspect_bundle(folder,tessdata=data,ocr_controls_passed=controls_passed)
    spec=json.loads((folder/'design-spec.json').read_text());lines=len(spec['graph']['lines'])
    report['surface_id']=spec['surface_id'];report['copy_lines']=lines
    report['live_text_note']=('No copy on this face: the live-text law holds trivially (zero expected runs in PDF, SVG and native); embedded raster planes were still counted and OCR-checked.'
                              if lines==0 else f'{lines} copy lines checked live, by glyph, font and position, in every format.')
    package={name:(folder/name).exists() for name in PACKAGE}
    native=json.loads((folder/'artwork-native-validation.json').read_text())['passed'] if package['artwork-native-validation.json'] else None
    report['package']={'files':package,'complete':all(package.values()),'native_validation_passed':native}
    report['f7_rule_met']=bool(report['package']['complete'] and native is True and report['passed'])
    (folder/'TRACED_TEXT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def run(*,root=SURFACES,audit=AUDIT,revision='surfaces revision 1'):
    """Audit one emitted surface revision; `root` holds the seven surface folders and `audit` receives every written file."""
    root=Path(root);audit=Path(audit);audit.mkdir(exist_ok=True);data=tessdata(audit);header=root/'header.front'
    controls,header_live=positive_controls(header,audit,data)
    passed=len(controls)==len(CONTROL_LINES) and all(c['detected'] for c in controls)
    surfaces={identity:inspect_surface(root/identity,data=data,controls_passed=passed) for identity in ORDER}
    negative=negative_control(header,audit,data)
    summary={k:{'passed':v['passed'],'state':v['state'],'copy_lines':v['copy_lines'],'formats':{f:x['passed'] for f,x in v['formats'].items()},
                'package_complete':v['package']['complete'],'native_validation_passed':v['package']['native_validation_passed'],'f7_rule_met':v['f7_rule_met'],'note':v['live_text_note']} for k,v in surfaces.items()}
    report={'code':'TRACED_TEXT','scope':'Day 6 D1 stand surfaces (F7; §2.2 package rule)','revision':revision,'surfaces_root':str(root.relative_to(fa.ROOT)),'positive_controls':controls,'positive_controls_passed':passed,'header_pdf_live':header_live,
            'surfaces':summary,'negative_controls':[negative],'negative_controls_failed_as_required':negative['failed_as_required'],
            'state':'passed' if passed and all(v['passed'] for v in surfaces.values()) and negative['failed_as_required'] else 'failed_or_unverified',
            'f7_package_rule_met':all(v['f7_rule_met'] for v in surfaces.values()),
            'exclusions':'Concept pictures are presentation sources, never artwork rasters. The approved vector logo is exempt from the live-text law. Faces without copy pass the live checks trivially and say so.',
            'tesseract_version':subprocess.check_output(['/opt/homebrew/bin/tesseract','--version'],text=True).splitlines()[0]}
    (audit/'TRACED_TEXT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
