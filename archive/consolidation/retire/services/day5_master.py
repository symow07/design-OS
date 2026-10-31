"""Revision 3: two explicit ink planes and measured Cairo, retaining revision 2."""
from pathlib import Path
import copy,json,shutil
import numpy as np
from PIL import Image
from . import fidelity_master as fm, fidelity_assets as fa, cairo_measured as cm
from . import two_ink_matte as ti
from .matte_colour import lin,enc,lab,de

ROOT=fa.ROOT/'docs/audit/day-5'
INK=ROOT/'two-ink/poisson-attempt'
CAIRO=ROOT/'cairo-selected'


def fonts():
    return dict(fm.FONTS,arabic=CAIRO/'Cairo-D5-Measured.ttf')


def fallback_proof():
    p=ROOT/'two-ink/image-isolation';dst=p/'evaluated';dst.mkdir(exist_ok=False)
    image=np.array(Image.open(p/'image.png').convert('RGB'));original=np.array(Image.open(fa.CONCEPT).convert('RGB'))
    bg=np.full_like(image,128);roi=np.array(Image.open(INK/'stroke-support.png'))>0
    support=np.array(Image.open(INK/'shadow-support.png'))>0
    instrument=json.loads((INK/'fidelity-instrument.json').read_text())
    cream=np.array(instrument['endmembers']['cream']['srgb']);shadow=np.array(instrument['endmembers']['shadow']['srgb'])
    f,s,_=ti.triangle_weights(lin(image),lin(bg),lin(cream),lin(shadow));f*=roi;s*=support
    ff=ti.flat_map(f,1000);ss=ti.flat_map(s,1000);qa=np.round(ff*255).astype(np.uint8);qb=np.minimum(np.round(ss*255),255-qa).astype(np.uint8)
    layers=[]
    for name,col,a in [('cream',cream,qa),('shadow',shadow,qb)]:
        rgba=np.dstack((np.broadcast_to(col.astype(np.uint8),a.shape+(3,)),a));Image.fromarray(rgba).save(dst/f'swoosh-{name}.png');layers.append(rgba)
    result,amber,grey,flag=ti.proof(image,bg,*layers,roi,support,cream)
    original_result,original_comp,_,_=ti.proof(original,np.array(Image.open(INK/'material-field.png')),*layers,roi,support,cream)
    Image.fromarray(amber).save(dst/'own-input-proof.png');Image.fromarray(grey).save(dst/'grey-proof.png');Image.fromarray(original_comp).save(dst/'original-concept-proof.png')
    chroma=image.max(axis=2).astype(int)-image.min(axis=2).astype(int);ys,xs=np.nonzero(chroma>20)
    box=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
    background=image[:,:450];report={'route':'image_isolation_rejected','input_sha256':fa.sha(p/'image.png'),'reason':'Deterministic unmixing against an inpainted ground reached31.3595%; the image model was asked to supply a known ground. It moved/enlarged the stroke and did not supply exact uniform grey. No geometric registration was silently applied.','original_bbox_px':[475,578,691,1380],'generated_chroma_bbox_px':box,'background_exact_128_fraction':float(np.mean(np.all(background==128,axis=2))),'background_min':int(background.min()),'background_max':int(background.max()),'background_median_deltaE_to128':float(np.median(de(lab(background),lab(np.array([128]*3))))),'known_exact_ground':False,'same_instrument_own_input':result,'same_instrument_original_concept':original_result,'used_for_master':False,'illustration_independent_score':4,'production_ready':False}
    (dst/'fidelity-instrument.json').write_text(json.dumps(report,indent=2)+'\n');return report


def make_spec():
    parent=json.loads((fa.ROOT/'docs/audit/day-4/master/design-spec.json').read_text());spec=copy.deepcopy(parent)
    m=json.loads((CAIRO/'measurement.json').read_text());g=spec['graph']
    g['lines']=[cm.graph_line(line,m) if line['id']=='arabic' else line for line in g['lines']]
    g.pop('raster_asset',None);g['raster_assets']=[{'role':role,'path':f'assets/swoosh-{role.lower()}.png'} for role in ['SHADOW','CREAM']]
    g['layer_roles']=['SHADOW','CREAM','LIVE TYPE','LOGO','RULES']
    spec.update(schema_version='design_spec/3.0',revision=3,parent_hash=fm.digest(parent),review_state='designer_review',production_ready=False)
    spec['fonts']={role:{'filename':path.name,'sha256':fa.sha(path),'family':fm.font_data(role,fonts())['family'],'postscript':fm.font_data(role,fonts())['postscript']} for role,path in fonts().items()}
    spec['assets']={'logo':parent['assets']['logo'],**{role:{'path':f'assets/swoosh-{role}.png','sha256':fa.sha(INK/f'swoosh-{role}.png')} for role in ('cream','shadow')}}
    spec['projection_assets']={'material-field.png':fa.sha(INK/'material-field.png'),'historical_material_shell_sha256':fa.sha(fm.PRESET/'material-field.png'),'presentation_mask':'Poisson field inside x330..684,y585..1380 with12px inward feather; retained measured shell outside. B2 proof still uses the full clean field independently.'}
    spec['ink_model']={'authoritative':'linear-light barycentric B*(1-f-s)+F*f+S*s','editable_export_preview':'ordinary source-over of two ink separations; not the additive optical proof','route':'deterministic_three_endmember_poisson_ground','fidelity_instrument_sha256':fa.sha(INK/'fidelity-instrument.json'),'status':'fails recomposition and fringe; retained for designer review'}
    spec['arabic_instance']=m
    spec['decoration_proposal']['candidate']='Clear-film or screen proposal: CMYK/process or spot cream plus deep-amber shadow ink and opaque white for live type; owner method unselected.'
    spec['decoration_proposal']['assumed_mockup_stack']=['clear substrate unverified','CREAM raster coverage','SHADOW deep-amber raster coverage','opaque white live type and vector mark']
    spec['decoration_proposal']['screen_print_alternative']='Two halftone/spot coverage planes plus opaque white; physical overprint/trapping and opacity remain supplier proof requirements. Linear barycentric proof is an appearance model, not calibrated physical ink mixing.'
    return spec


def validate_spec(spec):
    if spec!=make_spec():raise ValueError('Revision3 pins changed; a new immutable revision is required.')
    return spec


def build(destination):
    p=Path(destination);p.mkdir(exist_ok=False,parents=True);a=p/'assets';a.mkdir();spec=make_spec();g=spec['graph']
    for role in ('cream','shadow'):shutil.copyfile(INK/f'swoosh-{role}.png',a/f'swoosh-{role}.png')
    shutil.copyfile(fm.LOGO,a/'bbrose-logo.svg')
    for role,font in fonts().items():
        shutil.copyfile(font,a/font.name)
        license=(CAIRO/'OFL.txt') if role=='arabic' else (fa.APP/'static/fonts/OFL.txt') if role=='symbol' else font.parent/'OFL.txt'
        shutil.copyfile(license,a/(role+'-OFL.txt'))
    for name,data in [('design-spec.json',spec),('design-graph.json',g)]: (p/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    rasters=[(role,a/f'swoosh-{role.lower()}.png') for role in ('SHADOW','CREAM')]
    (p/'artwork.svg').write_bytes(fm.svg(g,fonts=fonts(),rasters=rasters));fm.emit_pdf(g,p/'artwork.pdf',fonts=fonts(),rasters=rasters)
    shutil.copyfile(p/'artwork.pdf',p/'artwork-pdf-compatible.ai')
    actual=fm.render_artwork(p/'artwork.pdf');Image.fromarray(actual).save(p/'artwork.png')
    fm.emit_pdf(g,p/'live-type-logo.pdf',fonts=fonts(),rasters=[])
    type_rgba=fm.render_artwork(p/'live-type-logo.pdf');Image.fromarray(type_rgba).save(p/'live-type-logo.png')
    f=np.array(Image.open(a/'swoosh-cream.png'));s=np.array(Image.open(a/'swoosh-shadow.png'))
    # Project each coverage plane, then combine in linear light, never encoded-alpha-over.
    pf=fa.project(f);ps=fa.project(s);pt=fa.project(type_rgba);af=pf[:,:,3:4]/255;ass=ps[:,:,3:4]/255;at=pt[:,:,3:4]/255
    background=np.array(Image.open(INK/'material-field.png').convert('RGB'))
    # The fitted field is supported by body-ground observations. Keep the measured
    # shoulder/heel shell for presentation, rather than painting its rectangular crop.
    shell=np.array(Image.open(fm.PRESET/'material-field.png').convert('RGB'))
    yy,xx=np.indices(background.shape[:2]);weight=np.clip(np.minimum.reduce([xx-330,684-xx,yy-585,1380-yy])/12,0,1)[:,:,None]
    background=enc(lin(background)*weight+lin(shell)*(1-weight))
    ink=lin(pf[:,:,:3])*af+lin(ps[:,:,:3])*ass+lin(background)*np.maximum(0,1-af-ass)
    projection=enc(lin(pt[:,:,:3])*at+ink*(1-at));Image.fromarray(projection).save(p/'projected-master.png')
    # Texture for presentation combines both coverages into one equivalent premultiplied colour;
    # original two layers remain authoritative, and type is composited last in linear light.
    af=f[:,:,3:4]/255;ass=s[:,:,3:4]/255;at=type_rgba[:,:,3:4]/255
    total=af+ass;rgb=(lin(f[:,:,:3])*af+lin(s[:,:,:3])*ass)*(1-at)+lin(type_rgba[:,:,:3])*at
    alpha=total*(1-at)+at;texture=np.dstack((enc(rgb/np.maximum(alpha,1e-12)),np.round(alpha[:,:,0]*255).astype(np.uint8)))
    Image.fromarray(texture).save(p/'artwork-linear-proof-texture.png')
    from .fidelity_checks import inspect_pixels
    result=inspect_pixels(fa.project(actual),projection,json.loads(fa.MEASUREMENT.read_text()))
    result.update(revision=3,spec_hash=fm.digest(spec),two_ink=json.loads((INK/'fidelity-instrument.json').read_text()),arabic_geometric_measurement=spec['arabic_instance'],measured_fidelity_passed=False,review_state='designer_review',projection_composite='linear additive from reopened two ink planes plus actual live-text PDF; PDF separation preview uses ordinary over')
    (p/'fidelity-check.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return {'revision':3,'spec_hash':fm.digest(spec),'review_state':'designer_review'}
