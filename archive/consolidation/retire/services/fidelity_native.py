from pathlib import Path
import json
from apps.pipeline.services import fidelity_master as fm
from apps.ire.handoff.illustrator_exec import run_jsx
from reportlab.lib.units import mm
import shutil
import fitz
import numpy as np
from collections import Counter


def build(bundle):
    for font in fm.FONTS.values():
        target=Path.home()/'Library/Fonts'/font.name
        if not target.exists():shutil.copyfile(font,target)
        elif target.read_bytes()!=font.read_bytes():raise ValueError('Installed font conflicts with licensed pin.')
    p=Path(bundle).resolve();spec=json.loads((p/'design-spec.json').read_text());g=spec['graph']
    logo=next(e for e in g['elements'] if e['id']=='logo');root=fm._logo_svg(logo);root.attrib.update(x='0',y='0');(p/'native-logo.svg').write_bytes(fm.ET.tostring(root))
    D={'w':fm.fa.WIDTH*mm,'h':fm.fa.HEIGHT*mm,'mm':mm,'lines':g['lines'],'fonts':{r:fm.font_data(r)['postscript'] for r in fm.FONTS},'raster':str(p/'assets/swoosh-flat.png'),'logo':str(p/'native-logo.svg'),'box':logo['flat_bbox_mm'],'rules':[e for e in g['elements'] if e['id'].endswith('_rule')],'out':str(p/'artwork-native.ai'),'pdf':str(p/'artwork-native-check.pdf'),'census':str(p/'artwork-native-census.json')}
    js=r'''(function(){var D=__DATA__,doc=null,mark=null,old=app.userInteractionLevel,report={};
    function quote(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
    function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return quote(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(quote(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
    function colour(rgb){var c=new RGBColor();c.red=rgb[0];c.green=rgb[1];c.blue=rgb[2];return c;}
    try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.documents.add(DocumentColorSpace.RGB,D.w,D.h);doc.artboards[0].artboardRect=[0,D.h,D.w,0];
    report.stage='raster';var rasterLayer=doc.layers[0];rasterLayer.name='SWOOSH';var placed=doc.placedItems.add();placed.file=new File(D.raster);placed.position=[0,D.h];placed.width=D.w;placed.height=D.h;placed.embed();app.redraw();
    report.stage='type';var layer=doc.layers.add();layer.name='LIVE TYPE';
    for(var i=0;i<D.lines.length;i++){var line=D.lines[i],group=layer.groupItems.add();group.name=line.logical_text;
    for(var j=0;j<line.runs.length;j++){report.currentGlyph=line.id+'-'+j;var r=line.runs[j],tf=doc.textFrames.pointText([0,0]);tf.contents=r.text;tf.name=line.id+'-'+j;var at=tf.textRange.characterAttributes;report.stage='type.size';at.size=100;report.stage='type.font';at.textFont=app.textFonts.getByName(D.fonts[r.font_role]);report.stage='type.colour';at.fillColor=colour(line.colour);tf.move(group,ElementPlacement.PLACEATEND);
    var mat=app.getIdentityMatrix();mat.mValueA=r.scale_x_mm_per_1000pt_unit*D.mm*10;mat.mValueD=r.scale_y_mm_per_1000pt_unit*D.mm*10;mat.mValueTX=r.x_mm*D.mm;mat.mValueTY=r.baseline_z_mm*D.mm;tf.transform(mat,true,true,true,true,1,Transformation.DOCUMENTORIGIN);}}
    report.stage='rules';layer=doc.layers.add();layer.name='RULES';for(var i=0;i<D.rules.length;i++){var e=D.rules[i],b=e.flat_bbox_mm;var q=layer.pathItems.rectangle(b[3]*D.mm,(b[0]+D.w/D.mm/2)*D.mm,(b[2]-b[0])*D.mm,(b[3]-b[1])*D.mm);q.stroked=false;q.filled=true;q.fillColor=colour(e.colour.srgb_255);q.name=e.id;}
    report.stage='logo';mark=app.open(new File(D.logo));var items=[];for(var j=0;j<mark.pageItems.length;j++){var item=mark.pageItems[j];if(item.parent.typename==='Layer')items.push(item);}var grp=mark.groupItems.add();for(var j=0;j<items.length;j++)items[j].moveToBeginning(grp);var clone=grp.duplicate(doc,ElementPlacement.PLACEATBEGINNING);mark.close(SaveOptions.DONOTSAVECHANGES);mark=null;doc.activate();
    var b=D.box;clone.width=(b[2]-b[0])*D.mm;clone.height=(b[3]-b[1])*D.mm;clone.position=[(b[0]+D.w/D.mm/2)*D.mm,b[3]*D.mm];clone.name='APPROVED VECTOR LOGO';
    report.stage='census';report.frames=[];for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i],a=t.textRange.characterAttributes;report.frames.push({text:t.contents,font:a.textFont.name,size:a.size,bounds:t.visibleBounds});}
    report.artboards=doc.artboards.length;report.paths=doc.pathItems.length;report.rasters=doc.rasterItems.length;
    report.stage='save';var options=new IllustratorSaveOptions();options.pdfCompatible=true;doc.saveAs(new File(D.out),options);var po=new PDFSaveOptions();po.preserveEditability=false;doc.saveAs(new File(D.pdf),po);report.saved=true;
    }catch(e){report.saved=false;report.error=String(e);}finally{if(mark)mark.close(SaveOptions.DONOTSAVECHANGES);if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);app.userInteractionLevel=old;}
    var file=new File(D.census);file.encoding='UTF-8';file.open('w');file.write(json(report));file.close();return json({saved:report.saved,error:report.error});})();'''
    (p/'artwork-native.jsx').write_text(js.replace('__DATA__',json.dumps(D)))
    executed=run_jsx(str(p/'artwork-native.jsx'))
    report=json.loads((p/'artwork-native-census.json').read_text()) if executed.get('executed') and (p/'artwork-native-census.json').exists() else executed
    report['executed']=executed.get('executed',False)
    return verify_transport(p,report)


def verify_transport(p,report):
    p=Path(p);spec=fm.validate_spec(json.loads((p/'design-spec.json').read_text()))
    if report.get('saved') or report.get('reopened'):
        runs=[dict(r,name=line['id']+'-'+str(i)) for line in spec['graph']['lines'] for i,r in enumerate(line['runs'])]
        expected=Counter((r['text'],fm.font_data(r['font_role'])['postscript']) for r in runs)
        report['expected_glyph_count']=len(runs)
        report['live_glyphs_match']=expected==Counter((f['text'],f['font']) for f in report['frames'])
        report['expected_fonts']=sorted({font for text,font in expected});report['found_fonts']=sorted({f['font'] for f in report['frames']})
        report['fonts_matched']=report['expected_fonts']==report['found_fonts']
        arrays=[];mask=None
        for name in ('artwork.pdf','artwork-native.ai'):
            with fitz.open(p/name) as doc:
                pix=doc[0].get_pixmap(dpi=600,alpha=True);rgba=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4)
                arrays.append(rgba[:,:,:3].astype(float)+128*(1-rgba[:,:,3:4]/255))
                if mask is None:mask=rgba[:,:,3]>0
        if arrays[0].shape==arrays[1].shape:
            err=np.abs(arrays[0]-arrays[1]);crops=[]
            for element in spec['graph']['elements']:
                if element['id']=='swoosh':continue
                a,b,c,d=element['flat_bbox_mm'];k=600/25.4
                x0=max(0,int((a+fm.fa.WIDTH/2-.5)*k));x1=min(mask.shape[1],int((c+fm.fa.WIDTH/2+.5)*k)+1)
                y0=max(0,int((fm.fa.HEIGHT-d-.5)*k));y1=min(mask.shape[0],int((fm.fa.HEIGHT-b+.5)*k)+1)
                local=err[y0:y1,x0:x1];lm=mask[y0:y1,x0:x1]
                crops.append({'element':element['id'],'ink_mean_absolute_error':float(local[lm].mean()) if lm.any() else 255.})
            report['visual']={'dpi':600,'background':'neutral128; white ink included','source':'actual native AI PDF-compatible content','shape_equal':True,'ink_mean_absolute_error':float(err[mask].mean()),'page_mean_absolute_error':float(err.mean()),'critical_crops':crops,'critical_crop_limit':5.,'ink_mean_limit':3.}
        else:report['visual']={'shape_equal':False,'dpi':600}
        report['passed']=bool(report['fonts_matched'] and report['live_glyphs_match'] and report['artboards']==1 and report['rasters']==1 and report['paths']>0 and report['visual'].get('shape_equal') and report['visual']['ink_mean_absolute_error']<3 and all(c['ink_mean_absolute_error']<5 for c in report['visual']['critical_crops']))
    else:report['passed']=False
    report['source_hashes']={n:fm.fa.sha(p/n) for n in ('artwork-native.ai','artwork.pdf','design-graph.json','design-spec.json','assets/swoosh-flat.png') if (p/n).exists()}
    report['meaning']='Native transport/editable-object check only; fidelity/production review remains separate.'
    (p/'artwork-native-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


def validate_existing(bundle):
    import tempfile
    p=Path(bundle).resolve()
    previous=p/'artwork-native-validation.json'
    if previous.exists() and not json.loads(previous.read_text()).get('passed'):
        shutil.copyfile(previous,p/'native-regeneration-failure.json')
    with tempfile.TemporaryDirectory(prefix='bbrose-native-review-') as tmp:
        owned=Path(tmp)/'owned-review-copy.ai';shutil.copyfile(p/'artwork-native.ai',owned)
        output=Path(tmp)/'census.json'
        # The copy avoids changing or closing a pre-existing user document.
        code=r'''(function(){var doc=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,report={};
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.open(new File(__INPUT__));report.frames=[];for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i],a=t.textRange.characterAttributes;report.frames.push({name:t.name,text:t.contents,font:a.textFont.name,size:a.size,bounds:t.visibleBounds});}report.artboards=doc.artboards.length;report.paths=doc.pathItems.length;report.rasters=doc.rasterItems.length;report.reopened=true;}
catch(e){report.reopened=false;report.error=String(e);}finally{if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);if(prior)prior.activate();app.userInteractionLevel=old;}
var f=new File(__OUTPUT__);f.encoding='UTF-8';f.open('w');f.write(json(report));f.close();return json({reopened:report.reopened});})();'''
        script=Path(tmp)/'inspect.jsx';script.write_text(code.replace('__INPUT__',json.dumps(str(owned))).replace('__OUTPUT__',json.dumps(str(output))))
        result=run_jsx(str(script));report=json.loads(output.read_text()) if result.get('executed') and output.exists() else result
    report['executed']=result.get('executed',False);report['method']='reopened_existing_native';report['regeneration_status']='MRAP at first glyph size setter; retained previously built AI re-opened without attribute writes'
    return verify_transport(p,report)


def repair_logo_transport(bundle, *, validate=None, verify=None):
    """Correct the vector import omission on an owned copy; never modify live type."""
    import tempfile
    p=Path(bundle).resolve();spec=(validate or fm.validate_spec)(json.loads((p/'design-spec.json').read_text()))
    logo=next(e for e in spec['graph']['elements'] if e['id']=='logo')
    retained=p/'native-before-logo-transport-fix.ai'
    if not retained.exists():shutil.copyfile(p/'artwork-native.ai',retained)
    shutil.copyfile(p/'artwork-native-validation.json',p/'native-before-logo-transport-validation.json')
    with tempfile.TemporaryDirectory(prefix='bbrose-native-logo-') as tmp:
        owned=Path(tmp)/'owned-copy.ai';shutil.copyfile(retained,owned)
        output=Path(tmp)/'corrected.ai';status=Path(tmp)/'status.txt'
        data={'input':str(owned),'output':str(output),'logo':str(p/'native-logo.svg'),'box':logo['flat_bbox_mm'],'width':fm.fa.WIDTH,'mm':mm,'status':str(status)}
        code=r'''(function(){var D=__DATA__,doc=null,mark=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,result='';
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.open(new File(D.input));var removed=0;for(var i=doc.groupItems.length-1;i>=0;i--){if(doc.groupItems[i].name==='APPROVED VECTOR LOGO'){doc.groupItems[i].remove();removed++;}}if(removed!==1)throw new Error('Expected exactly one named logo, found '+removed);
mark=app.open(new File(D.logo));var items=[];for(var i=0;i<mark.pageItems.length;i++){var item=mark.pageItems[i];if(item.parent.typename==='Layer')items.push(item);}if(items.length!==3)throw new Error('Expected main group plus registration ring and R, found '+items.length);var grp=mark.groupItems.add();for(var i=0;i<items.length;i++)items[i].moveToBeginning(grp);var clone=grp.duplicate(doc,ElementPlacement.PLACEATBEGINNING);mark.close(SaveOptions.DONOTSAVECHANGES);mark=null;doc.activate();var b=D.box;clone.width=(b[2]-b[0])*D.mm;clone.height=(b[3]-b[1])*D.mm;clone.position=[(b[0]+D.width/2)*D.mm,b[3]*D.mm];clone.name='APPROVED VECTOR LOGO';var options=new IllustratorSaveOptions();options.pdfCompatible=true;doc.saveAs(new File(D.output),options);result='saved';}
catch(e){result=String(e);}finally{if(mark)mark.close(SaveOptions.DONOTSAVECHANGES);if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);if(prior)prior.activate();app.userInteractionLevel=old;}var f=new File(D.status);f.open('w');f.write(result);f.close();return result;})();'''
        script=Path(tmp)/'repair.jsx';script.write_text(code.replace('__DATA__',json.dumps(data)))
        execution=run_jsx(str(script))
        if not execution.get('executed') or not status.exists() or status.read_text()!='saved':
            raise RuntimeError(status.read_text() if status.exists() else str(execution))
        shutil.copyfile(output,p/'artwork-native.ai')
    result=(verify or validate_existing)(p)
    result['export_correction']='Snapshot imported top-level vector items before grouping; restored registration ring/R and exact full-logo scale.'
    result['retained_before_sha256']=fm.fa.sha(retained)
    (p/'artwork-native-validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result
