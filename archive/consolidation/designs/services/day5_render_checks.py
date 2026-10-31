"""Actual master-edit locality and asymmetric UV fixtures, rendered headlessly."""
from pathlib import Path
import copy,json
import fitz,numpy as np
from PIL import Image
from . import day5_scene as ds,day5_master as dm,fidelity_master as fm,fidelity_assets as fa
from .matte_colour import lin,enc

def run():
    root=dm.ROOT/'render/checks';root.mkdir(exist_ok=False);cfg=json.loads((dm.ROOT/'render/scene-config.json').read_text());cfg.update(resolution=[600,800],samples=1,views=['front'])
    current=json.loads((dm.ROOT/'master/design-spec.json').read_text());cfg['bottle_spec']=current;cfg['bottle_spec_hash']=fm.digest(current)
    # Edit an actual live header line, retaining all images and other geometry.
    source=fa.ROOT/'docs/audit/day-4/stand-family/surfaces/header.front.pdf';header=root/'header-copy-edit.pdf'
    with fitz.open(source) as doc:
        page=doc[0];matches=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans'] if s['text']=='SUN' and s['origin'][0]<40]
        span=matches[0];page.add_redact_annot(fitz.Rect(span['bbox']),fill=None);page.apply_redactions(images=0,graphics=0,text=0)
        page.insert_font(fontname='ChangedTitle',fontfile=str(fm.FONTS['title']));page.insert_text(span['origin'],'NEW',fontsize=span['size'],fontname='ChangedTitle',color=(244/255,238/255,235/255));doc.save(header);page.get_pixmap(dpi=300).save(root/'header-copy-edit.png')
    # Edit the live bottle SUN line toNEW using its existing placements/fonts.
    graph=copy.deepcopy(current['graph']);line=next(l for l in graph['lines'] if l['id']=='SUN');line['logical_text']='NEW'
    for run,ch in zip(line['runs'],'NEW'):run['text']=ch
    type_pdf=root/'bottle-copy-edit.pdf';fm.emit_pdf(graph,type_pdf,fonts=dm.fonts(),rasters=[]);typ=fm.render_artwork(type_pdf)
    f=np.array(Image.open(dm.ROOT/'master/assets/swoosh-cream.png'));s=np.array(Image.open(dm.ROOT/'master/assets/swoosh-shadow.png'));af=f[:,:,3:4]/255;ass=s[:,:,3:4]/255;at=typ[:,:,3:4]/255;alpha=(af+ass)*(1-at)+at;rgb=(lin(f[:,:,:3])*af+lin(s[:,:,:3])*ass)*(1-at)+lin(typ[:,:,:3])*at
    Image.fromarray(np.dstack((enc(rgb/np.maximum(alpha,1e-12)),np.round(alpha[:,:,0]*255).astype(np.uint8)))).save(root/'bottle-copy-edit.png')
    # Asymmetric four-colour fixture; this is diagnostic art, never production.
    array=np.zeros((512,512,4),np.uint8);array[:256,:256]=[255,0,0,255];array[:256,256:]=[0,255,0,255];array[256:,:256]=[0,0,255,255];array[256:,256:]=[255,255,0,255]
    Image.fromarray(array).save(root/'uv-positive.png');Image.fromarray(array[:,::-1]).save(root/'uv-mirrored-negative.png')
    for name in ['base','header-edit','bottle-edit','uv-positive','uv-mirrored-negative']:
        conf=copy.deepcopy(cfg)
        if name=='header-edit':
            surface=next(s for s in conf['surfaces'] if s['surface_id']=='header.front');surface.update(texture=str(root/'header-copy-edit.png'),texture_sha256=fa.sha(root/'header-copy-edit.png'))
        elif name!='base':
            texture=root/('bottle-copy-edit.png' if name=='bottle-edit' else name+'.png');conf.update(bottle_texture=str(texture),bottle_texture_sha256=fa.sha(texture))
        file=root/(name+'.json');file.write_text(json.dumps(conf,ensure_ascii=False,indent=2)+'\n');ds.render(file,run=name,views=['front'],diagnostic=True)
    base=np.array(Image.open(root/'base/front.png').convert('RGB'));manifest=json.loads((root/'base/scene-manifest.json').read_text());results={}
    for name,prefix in [('header-edit','header.front'),('bottle-edit','bottle/')]:
        other=np.array(Image.open(root/name/'front.png').convert('RGB'));changed=np.any(base!=other,axis=2);mask=np.zeros(changed.shape,bool)
        for key,box in manifest['diagnostic_regions'].items():
            if key.startswith(prefix):
                x0,y0,x1,y1=box;mask[max(0,int(y0)):min(mask.shape[0],int(y1)+1),max(0,int(x0)):min(mask.shape[1],int(x1)+1)]=True
        results[name]={'changed_pixels':int(changed.sum()),'outside_surface_pixels':int((changed&~mask).sum()),'passed':bool(changed.any() and not (changed&~mask).any()),'region_padding_px':2}
        diff=np.zeros_like(base);diff[changed]=[255,0,160];Image.fromarray(diff).save(root/(name+'-delta.png'))
    uv={}
    for name in ['uv-positive','uv-mirrored-negative']:
        im=np.array(Image.open(root/name/'front.png').convert('RGB'));samples=[]
        for p in manifest['uv_samples']:
            x,y=map(round,p['pixel']);rgb=np.median(im[y-2:y+3,x-2:x+3].reshape(-1,3),axis=0);r,g,b=rgb
            ok={'red':r>160 and g<70 and b<70,'green':g>160 and r<70 and b<70,'blue':b>160 and r<70 and g<70,'yellow':r>160 and g>160 and b<70}[p['expected']]
            samples.append(dict(p,rgb=rgb.tolist(),passed=bool(ok)))
        uv[name]={'samples':samples,'passed':all(p['passed'] for p in samples)}
    report={'copy_edits':results,'uv':uv,'passed':all(x['passed'] for x in results.values()) and uv['uv-positive']['passed'] and not uv['uv-mirrored-negative']['passed'],'instrument':'All materials camera-only emission; no lighting/reflection transport. Actual livePDFcopy edits are rerasterized and mapped through the same mesh UVs.','source_hashes':{str(p.relative_to(root)):fa.sha(p) for p in root.glob('*.pdf')}}
    (root/'checks.json').write_text(json.dumps(report,indent=2)+'\n');return report
