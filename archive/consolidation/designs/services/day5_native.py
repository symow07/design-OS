"""Native r3 through editable PDF import, avoiding per-glyph size setters."""
import json,shutil,tempfile
from pathlib import Path
from collections import Counter
import fitz,numpy as np
from . import day5_master as dm,fidelity_assets as fa
from apps.ire.handoff.illustrator_exec import run_jsx

def build(bundle):
    p=Path(bundle).resolve();spec=dm.validate_spec(json.loads((p/'design-spec.json').read_text()))
    for font in dm.fonts().values():
        installed=Path.home()/'Library/Fonts'/font.name
        if installed.exists() and installed.read_bytes()!=font.read_bytes():raise ValueError('Installed font differs from pin.')
        if not installed.exists():shutil.copyfile(font,installed)
    with tempfile.TemporaryDirectory(prefix='bbrose-day5-native-') as tmp:
        owned=Path(tmp)/'owned-type.pdf';shutil.copyfile(p/'live-type-logo.pdf',owned)
        data={'input':str(owned),'output':str(p/'artwork-native.ai'),'status':str(p/'artwork-native-census.json'),'w':fa.WIDTH*72/25.4,'h':fa.HEIGHT*72/25.4,'layers':[{'name':role,'file':str(p/f'assets/swoosh-{role.lower()}.png')} for role in ['CREAM','SHADOW']]}
        code=r'''(function(){var D=__DATA__,doc=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,R={};
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function js(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(js(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+js(v[k]));return '{'+a.join(',')+'}';}
function census(){var rows=[];for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i],chars=[];for(var j=0;j<t.characters.length;j++)chars.push({text:t.characters[j].contents,font:t.characters[j].characterAttributes.textFont.name});rows.push({text:t.contents,characters:chars,bounds:t.visibleBounds,hidden:t.hidden,opacity:t.opacity,layer_visible:t.layer.visible});}return {frames:rows,rasters:doc.rasterItems.length,paths:doc.pathItems.length,artboards:doc.artboards.length,artboard:doc.artboards[0].artboardRect};}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;R.stage='open_pdf';doc=app.open(new File(D.input));R.stage='census_import';R.imported=census();R.stage='raster_layers';
for(var i=0;i<D.layers.length;i++){var L=D.layers[i],layer=doc.layers.add();layer.name=L.name;layer.zOrder(ZOrderMethod.SENDTOBACK);doc.activeLayer=layer;var item=doc.placedItems.add();item.file=new File(L.file);item.position=[0,D.h];item.width=D.w;item.height=D.h;item.name=L.name;item.embed();}
R.before_save=census();var options=new IllustratorSaveOptions();options.pdfCompatible=true;doc.saveAs(new File(D.output),options);doc.close(SaveOptions.DONOTSAVECHANGES);doc=null;doc=app.open(new File(D.output));R.reopened=census();R.saved=true;
}catch(e){R.saved=false;R.error=String(e);}finally{if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);if(prior)prior.activate();app.userInteractionLevel=old;}
var f=new File(D.status);f.encoding='UTF-8';f.open('w');f.write(js(R));f.close();return js({saved:R.saved,error:R.error});})();'''
        script=p/'artwork-native.jsx';script.write_text(code.replace('__DATA__',json.dumps(data)))
        execution=run_jsx(str(script));report=json.loads((p/'artwork-native-census.json').read_text()) if (p/'artwork-native-census.json').exists() else execution
    report.update(route='Editable live-type/logo PDF import plus embedded CREAM and SHADOW; avoids Day4 MRAP per-glyph setters.',passed=False)
    if report.get('saved'):
        expected=Counter((r['text'],spec['fonts'][r['font_role']]['postscript']) for line in spec['graph']['lines'] for r in line['runs'])
        found=Counter((ch['text'],ch['font']) for frame in report['reopened']['frames'] for ch in frame['characters'] if ch['text'].strip())
        report.update(glyph_fonts_match=expected==found,expected_glyphs=sum(expected.values()),found_glyphs=sum(found.values()))
        arrays=[]
        for file in ('artwork.pdf','artwork-native.ai'):
            with fitz.open(p/file) as doc:
                pix=doc[0].get_pixmap(dpi=600,alpha=True);a=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4);arrays.append(a[:,:,:3].astype(float)+128*(1-a[:,:,3:4]/255))
        report['render_shape_match']=arrays[0].shape==arrays[1].shape
        if report['render_shape_match']:
            error=np.abs(arrays[0]-arrays[1]);report.update(render_mae=float(error.mean()),render_p99=float(np.quantile(error,.99)))
        report['passed']=bool(report['glyph_fonts_match'] and report['reopened']['rasters']==2 and report['render_shape_match'] and report['render_mae']<3)
    report['source_hashes']={name:fa.sha(p/name) for name in ['artwork.pdf','artwork-native.ai','design-spec.json','assets/swoosh-cream.png','assets/swoosh-shadow.png'] if (p/name).exists()}
    (p/'artwork-native-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

def direct_build(bundle):
    """Use the established native glyph builder with explicit r3 data and two planes."""
    import re
    from reportlab.lib.units import mm
    from . import fidelity_master as fm
    p=Path(bundle);spec=dm.validate_spec(json.loads((p/'design-spec.json').read_text()));g=spec['graph']
    for name in ['artwork-native.ai','artwork-native-validation.json','artwork-native-census.json']:
        if (p/name).exists():shutil.copyfile(p/name,p/('rejected-pdf-import-'+name))
    logo=next(e for e in g['elements'] if e['id']=='logo');root=fm._logo_svg(logo);root.attrib.update(x='0',y='0');(p/'native-logo.svg').write_bytes(fm.ET.tostring(root))
    data={'w':fa.WIDTH*mm,'h':fa.HEIGHT*mm,'mm':mm,'lines':g['lines'],'fonts':{r:spec['fonts'][r]['postscript'] for r in spec['fonts']},'rasters':[{'role':r,'path':str(p/f'assets/swoosh-{r.lower()}.png')} for r in ['SHADOW','CREAM']],'logo':str(p/'native-logo.svg'),'box':logo['flat_bbox_mm'],'rules':[e for e in g['elements'] if e['id'].endswith('_rule')],'out':str(p/'artwork-native.ai'),'pdf':str(p/'artwork-native-check.pdf'),'census':str(p/'artwork-native-direct-census.json')}
    template=(fa.ROOT/'docs/audit/day-4/master/artwork-native.jsx').read_text()
    prefix,rest=template.split('var D=',1);old,tail=rest.split(',doc=null',1);code=prefix+'var D='+json.dumps(data)+',doc=null'+tail
    start=code.index("report.stage='raster';");end=code.index("report.stage='type';",start)
    code=code[:start]+"report.stage='raster';for(var k=0;k<D.rasters.length;k++){var rasterLayer=doc.layers.add();rasterLayer.name=D.rasters[k].role;doc.activeLayer=rasterLayer;var placed=doc.placedItems.add();placed.file=new File(D.rasters[k].path);placed.position=[0,D.h];placed.width=D.w;placed.height=D.h;placed.embed();}app.redraw();\n"+code[end:]
    # Snapshot top-level logo items before grouping (Day4 registration-symbol correction).
    # Existing source already snapshots; no hierarchy mutation while enumerating.
    script=p/'artwork-native-direct.jsx';script.write_text(code);execution=run_jsx(str(script))
    report=json.loads((p/'artwork-native-direct-census.json').read_text()) if (p/'artwork-native-direct-census.json').exists() else execution
    report['route']='Native glyph creation with measured Cairo and two original ink planes; prior PDF import outlined Arabic and estimated sign and was rejected.'
    if report.get('saved'):
        expected=Counter((r['text'],spec['fonts'][r['font_role']]['postscript']) for l in g['lines'] for r in l['runs'])
        found=Counter((r['text'],r['font']) for r in report['frames']);report['glyph_fonts_match']=expected==found
        arrays=[]
        for name in ['artwork.pdf','artwork-native.ai']:
            with fitz.open(p/name) as pdf:
                pix=pdf[0].get_pixmap(dpi=600,alpha=True);v=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4);arrays.append(v[:,:,:3].astype(float)+128*(1-v[:,:,3:4]/255))
        report['render_shape_match']=arrays[0].shape==arrays[1].shape
        if report['render_shape_match']:report['render_mae']=float(np.abs(arrays[0]-arrays[1]).mean())
        report['passed']=bool(report['glyph_fonts_match'] and report['rasters']==2 and report['render_shape_match'] and report['render_mae']<3)
    else:report['passed']=False
    report['source_hashes']={n:fa.sha(p/n) for n in ['artwork.pdf','artwork-native.ai','design-spec.json'] if(p/n).exists()}
    (p/'artwork-native-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');return report

def verify_existing(bundle):
    from .traced_text import pdf_live,expected_lines
    p=Path(bundle);spec=dm.validate_spec(json.loads((p/'design-spec.json').read_text()));live=pdf_live(p/'artwork-native.ai',expected_lines(spec,p/'assets'))
    arrays=[];mask=None
    for name in ['artwork.pdf','artwork-native.ai']:
        with fitz.open(p/name) as doc:
            pix=doc[0].get_pixmap(dpi=600,alpha=True);v=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4)
            arrays.append(v[:,:,:3].astype(float)+128*(1-v[:,:,3:4]/255))
            if mask is None:mask=v[:,:,3]>0
    error=np.abs(arrays[0]-arrays[1]);crops=[];k=600/25.4
    for e in spec['graph']['elements']:
        if e['id']=='swoosh':continue
        a,b,c,d=e['flat_bbox_mm'];x0=max(0,int((a+fa.WIDTH/2-.5)*k));x1=min(mask.shape[1],int((c+fa.WIDTH/2+.5)*k)+1);y0=max(0,int((fa.HEIGHT-d-.5)*k));y1=min(mask.shape[0],int((fa.HEIGHT-b+.5)*k)+1)
        region=error[y0:y1,x0:x1];m=mask[y0:y1,x0:x1];crops.append({'element':e['id'],'ink_mae':float(region[m].mean())})
    with fitz.open(p/'artwork-native.ai') as doc:rasters=len(doc[0].get_images())
    r={'route':'Direct native glyph creation, then owned-copy logo transport correction; actual native PDF stream rechecked','live_text':live,'raster_images':rasters,'critical_crops':crops,'ink_mae':float(error[mask].mean()),'passed':live['passed'] and rasters==2 and all(c['ink_mae']<5 for c in crops) and float(error[mask].mean())<3,'source_hashes':{n:fa.sha(p/n) for n in ['artwork-native.ai','artwork.pdf','design-spec.json']}}
    (p/'artwork-native-validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');return r
