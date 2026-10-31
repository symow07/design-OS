"""Day 6 master-edit locality and asymmetric UV fixtures on the D1 header.

The Day 6 header sets type one glyph per drawString inside an ActualText span, so
the S, U, N glyphs are located individually (get_texttrace), redacted inside the
SUN ink band only (whole glyph boxes would also strip REPAIR's letters) and
replaced by NEW in the pinned title face at the same origin and the same
anisotropic x/y scales the design spec records. Diagnostics render 600x800 at one
sample with camera-only emission; passed only if every edit changes pixels inside
its mapped region alone and the mirrored UV negative fails."""
from pathlib import Path
import copy,json
import fitz,numpy as np
from PIL import Image
from . import day5_scene as ds,day6_scene as d6,day5_master as dm,fidelity_master as fm,fidelity_assets as fa
from .matte_colour import lin,enc

HEADER=d6.ROOT/'surfaces/header.front'   # surfaces revision 1; header_folder() resolves other revisions
MM=72/25.4
SUN='SUN'
TOLERANCE_MM=3.          # glyph advance boxes may sit this far outside the measured ink box
TOP_MARGIN_MM=.5         # redaction band starts this far above the measured ink top
BASELINE_MARGIN_MM=.25   # and ends this far below the glyph baseline, above REPAIR's boxes
REGION_PADDING_PX=2      # the manifest's diagnostic regions already carry this padding
RUNS=['base','header-edit','bottle-edit','uv-positive','uv-mirrored-negative']


def measured_sun_box():
    m=json.loads(d6.MEASUREMENT.read_text());face=next(f for f in m['faces'] if f['surface_id']=='header.front');e=next(e for e in face['elements'] if e['id']==SUN)
    return {'bbox_mm':list(e['bbox_mm']),'baseline_y_mm':e['baseline_y_mm'],'copy':e['copy']}


def glyph_census(page):
    return sorted((chr(c[0]),round(c[2][0]/MM,3),round(c[2][1]/MM,3),span['font']) for span in page.get_texttrace() for c in span['chars'])


def header_folder(surfaces_revision):
    return d6.profile(surfaces_revision)['surfaces']/'header.front'


def title_postscript(header):
    return json.loads((header/'design-spec.json').read_text())['fonts']['title']['postscript']


def locate_sun_glyphs(page,box,title):
    """The three glyphs in the title face `title` spelling SUN whose advance boxes and baseline sit at the measured SUN box."""
    x0,y0,x1,y1=box['bbox_mm'];found=[]
    for span in page.get_texttrace():
        if span['font']!=title or span['type']!=0:continue
        for code,glyph,origin,quad in span['chars']:
            ch=chr(code);gx0,gy0,gx1,gy1=[v/MM for v in quad];ox,oy=[v/MM for v in origin]
            if ch not in SUN or gx0<x0-TOLERANCE_MM or gx1>x1+TOLERANCE_MM or not (y0<=oy<=y1+TOLERANCE_MM):continue
            found.append({'char':ch,'glyph':glyph,'origin_mm':[ox,oy],'bbox_mm':[gx0,gy0,gx1,gy1],'size_pt':span['size'],'font':span['font'],'colour':list(span['color']),'seqno':span['seqno']})
    found.sort(key=lambda g:g['origin_mm'][0])
    if ''.join(g['char'] for g in found)!=SUN:raise ValueError(f"Expected exactly the glyphs S,U,N at the measured SUN box; found {[g['char'] for g in found]}.")
    return found


def redaction_rects(glyphs,box):
    """Per-glyph rects: the glyph's advance box in x; in y from the measured ink top to just below the baseline.
    MuPDF removes any glyph whose box intersects a rect, and SUN's full boxes reach into REPAIR's."""
    top=box['bbox_mm'][1]-TOP_MARGIN_MM
    return [fitz.Rect(g['bbox_mm'][0]*MM,top*MM,g['bbox_mm'][2]*MM,(g['origin_mm'][1]+BASELINE_MARGIN_MM)*MM) for g in glyphs]


def header_copy_edit(destination,surfaces_revision):
    """Redact S,U,N and set NEW live in the pinned title face at the S origin with the spec's x/y scales."""
    destination=Path(destination);box=measured_sun_box();header=header_folder(surfaces_revision);spec=json.loads((header/'design-spec.json').read_text());title_font=header/'assets'/spec['fonts']['title']['filename']
    if fa.sha(title_font)!=spec['fonts']['title']['sha256']:raise ValueError('The header title face differs from its pinned sha256.')
    run=next(r for l in spec['graph']['lines'] if l['id']==SUN for r in l['runs'] if r['text']=='S')
    sx_pt=run['scale_x_mm_per_1000pt_unit']*1000*MM;sy_pt=run['scale_y_mm_per_1000pt_unit']*1000*MM
    pdf=destination/'header-copy-edit.pdf';png=destination/'header-copy-edit.png'
    with fitz.open(header/'artwork.pdf') as doc:
        page=doc[0];before=glyph_census(page);glyphs=locate_sun_glyphs(page,box,spec['fonts']['title']['postscript'])
        if abs(sx_pt-glyphs[0]['size_pt'])>.05:raise ValueError('The design-spec x scale and the PDF glyph size disagree.')
        rects=redaction_rects(glyphs,box)
        for rect in rects:page.add_redact_annot(rect,fill=None)
        page.apply_redactions(images=0,graphics=0,text=0)
        after=glyph_census(page);removed=[g for g in before if g not in after];expected=sorted((g['char'],round(g['origin_mm'][0],3),round(g['origin_mm'][1],3),g['font']) for g in glyphs)
        if sorted(removed)!=expected or len(after)!=len(before)-3:raise ValueError(f'Redaction changed glyphs other than S,U,N: removed {removed}.')
        origin=fitz.Point(glyphs[0]['origin_mm'][0]*MM,glyphs[0]['origin_mm'][1]*MM)
        page.insert_font(fontname='ChangedTitle',fontfile=str(title_font))
        page.insert_text(origin,'NEW',fontsize=sy_pt,fontname='ChangedTitle',color=tuple(glyphs[0]['colour']),morph=(origin,fitz.Matrix(sx_pt/sy_pt,0,0,1,0,0)))
        doc.save(pdf);page.get_pixmap(dpi=300,alpha=False).save(png)
    flat=np.array(Image.open(png).convert('RGB'));original=np.array(Image.open(d6.profile(surfaces_revision)['render']/'textures/header.front.png').convert('RGB'))
    changed=np.any(flat!=original,axis=2);ys,xs=np.nonzero(changed)
    return {'surfaces_revision':surfaces_revision,'header_folder':str(header),'source_pdf_sha256':fa.sha(header/'artwork.pdf'),'measured_sun_box':box,'glyphs':glyphs,'redaction_rects_mm':[[v/MM for v in r] for r in rects],'glyphs_before':len(before),'glyphs_after':len(after),'removed':removed,
      'inserted':{'text':'NEW','font':spec['fonts']['title']['filename']+' (header assets, pinned)','font_sha256':fa.sha(title_font),'origin_mm':glyphs[0]['origin_mm'],'x_scale_pt':sx_pt,'y_scale_pt':sy_pt,'x_scale_mm_per_em':sx_pt/MM,'y_scale_mm_per_em':sy_pt/MM,'colour':glyphs[0]['colour'],
        'note':'The original glyphs are set with an anisotropic text matrix; NEW is set at the y scale and stretched horizontally by x/y about the origin.'},
      'flat_300ppi_change':{'changed_pixels':int(changed.sum()),'bbox_mm':[xs.min()*25.4/300,ys.min()*25.4/300,(xs.max()+1)*25.4/300,(ys.max()+1)*25.4/300]},'edited_pdf_sha256':fa.sha(pdf),'edited_texture_sha256':fa.sha(png)}


def bottle_copy_edit(destination,cfg):
    """Edit the live bottle SUN line to NEW with its existing placements and fonts (as Day 5)."""
    destination=Path(destination);current=json.loads((dm.ROOT/'master/design-spec.json').read_text())
    if fm.digest(current)!=cfg['bottle_spec_hash']:raise ValueError('The bottle spec is not the pinned revision 3; no silent re-pin.')
    graph=copy.deepcopy(current['graph']);line=next(l for l in graph['lines'] if l['id']==SUN);line['logical_text']='NEW'
    for run,ch in zip(line['runs'],'NEW'):run['text']=ch
    type_pdf=destination/'bottle-copy-edit.pdf';fm.emit_pdf(graph,type_pdf,fonts=dm.fonts(),rasters=[]);typ=fm.render_artwork(type_pdf)
    f=np.array(Image.open(dm.ROOT/'master/assets/swoosh-cream.png'));s=np.array(Image.open(dm.ROOT/'master/assets/swoosh-shadow.png'));af=f[:,:,3:4]/255;ass=s[:,:,3:4]/255;at=typ[:,:,3:4]/255
    alpha=(af+ass)*(1-at)+at;rgb=(lin(f[:,:,:3])*af+lin(s[:,:,:3])*ass)*(1-at)+lin(typ[:,:,:3])*at
    png=destination/'bottle-copy-edit.png';Image.fromarray(np.dstack((enc(rgb/np.maximum(alpha,1e-12)),np.round(alpha[:,:,0]*255).astype(np.uint8)))).save(png)
    return {'pdf_sha256':fa.sha(type_pdf),'texture_sha256':fa.sha(png)}


def uv_fixtures(destination):
    """Asymmetric four-colour fixture and its mirrored negative; diagnostic art, never production."""
    destination=Path(destination);array=np.zeros((512,512,4),np.uint8);array[:256,:256]=[255,0,0,255];array[:256,256:]=[0,255,0,255];array[256:,:256]=[0,0,255,255];array[256:,256:]=[255,255,0,255]
    Image.fromarray(array).save(destination/'uv-positive.png');Image.fromarray(array[:,::-1]).save(destination/'uv-mirrored-negative.png')


def locality(base,other,regions,prefix):
    """Changed pixels must lie inside the manifest's mapped regions for the edited surface(s)."""
    changed=np.any(base!=other,axis=2);mask=np.zeros(changed.shape,bool);count=0
    for key,(x0,y0,x1,y1) in regions.items():
        if key.startswith(prefix):count+=1;mask[max(0,int(y0)):min(mask.shape[0],int(y1)+1),max(0,int(x0)):min(mask.shape[1],int(x1)+1)]=True
    inside=int((changed&mask).sum());outside=int((changed&~mask).sum())
    return {'changed_pixels':int(changed.sum()),'inside_region_pixels':inside,'outside_surface_pixels':outside,'regions_used':count,'passed':bool(changed.any() and outside==0 and count>0),'region_padding_px':REGION_PADDING_PX},changed


def uv_verdict(image,samples):
    rows=[]
    for p in samples:
        x,y=map(round,p['pixel']);rgb=np.median(image[y-2:y+3,x-2:x+3].reshape(-1,3),axis=0);r,g,b=rgb
        ok={'red':r>160 and g<70 and b<70,'green':g>160 and r<70 and b<70,'blue':b>160 and r<70 and g<70,'yellow':r>160 and g>160 and b<70}[p['expected']]
        rows.append(dict(p,rgb=rgb.tolist(),passed=bool(ok)))
    return {'samples':rows,'passed':bool(rows) and all(r['passed'] for r in rows)}


def verdict(copy_edits,uv):
    """Every copy edit local, the UV positive passes and the mirrored negative fails."""
    return bool(copy_edits) and all(x['passed'] for x in copy_edits.values()) and uv['uv-positive']['passed'] and not uv['uv-mirrored-negative']['passed']


def run(surfaces_revision):
    render=d6.profile(surfaces_revision)['render'];root=render/'checks';root.mkdir(exist_ok=False);cfg=json.loads((render/'scene-config.json').read_text());cfg.update(resolution=[600,800],samples=1,views=['front'])
    if cfg['surfaces_revision']!=surfaces_revision:raise ValueError('The scene config is not this surfaces revision.')
    header=header_copy_edit(root,surfaces_revision);bottle=bottle_copy_edit(root,cfg);uv_fixtures(root)
    for name in RUNS:
        conf=copy.deepcopy(cfg)
        if name=='header-edit':
            surface=next(s for s in conf['surfaces'] if s['surface_id']=='header.front');surface.update(texture=str(root/'header-copy-edit.png'),texture_sha256=fa.sha(root/'header-copy-edit.png'))
        elif name!='base':
            texture=root/('bottle-copy-edit.png' if name=='bottle-edit' else name+'.png');conf.update(bottle_texture=str(texture),bottle_texture_sha256=fa.sha(texture))
        file=root/(name+'.json');file.write_text(json.dumps(conf,ensure_ascii=False,indent=2)+'\n');d6.render(file,name,views=['front'],diagnostic=True)
    base=np.array(Image.open(root/'base/front.png').convert('RGB'));manifest=json.loads((root/'base/scene-manifest.json').read_text());results={}
    for name,prefix in [('header-edit','header.front'),('bottle-edit','bottle/')]:
        other=np.array(Image.open(root/name/'front.png').convert('RGB'));results[name],changed=locality(base,other,manifest['diagnostic_regions'],prefix)
        diff=np.zeros_like(base);diff[changed]=[255,0,160];Image.fromarray(diff).save(root/(name+'-delta.png'))
    uv={name:uv_verdict(np.array(Image.open(root/name/'front.png').convert('RGB')),manifest['uv_samples']) for name in ['uv-positive','uv-mirrored-negative']}
    report={'schema':'day6_render_checks/1','surfaces_revision':surfaces_revision,'copy_edits':results,'uv':uv,'passed':verdict(results,uv),'header_edit':header,'bottle_edit':bottle,'resolution':cfg['resolution'],'samples':cfg['samples'],
      'instrument':'All materials camera-only emission; no lighting/reflection transport. Actual live PDF copy edits are rerasterized and mapped through the same mesh UVs; the Day 6 header is edited glyph by glyph.',
      'scene_config_sha256':fa.sha(render/'scene-config.json'),'script_sha256':fa.sha(d6.SCRIPT),'source_hashes':{str(p.relative_to(root)):fa.sha(p) for p in sorted(root.glob('*.pdf'))},'timing':{name:json.loads((root/name/'timing.json').read_text()) for name in RUNS}}
    (root/'checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');return report

if __name__=='__main__':
    import sys
    r=run(int(sys.argv[1]));print(json.dumps({'passed':r['passed'],'copy_edits':r['copy_edits'],'uv':{k:v['passed'] for k,v in r['uv'].items()},'header_glyphs':[g['char'] for g in r['header_edit']['glyphs']],'flat_change':r['header_edit']['flat_300ppi_change']},indent=2))
