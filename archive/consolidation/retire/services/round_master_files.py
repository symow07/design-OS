"""Generic six-layer masters; native bridge extracted from HAYAT without changing it.

The actual Illustrator save/reopen census is separate from PDF compatibility.
No missing native execution is replaced by a simulated pass.
"""
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
from . import round_balm_master as legacy
from .round_files_export import FONT_PATHS, glyph_metrics, raster, rgb, set_layers, shaped
from .round_flow import write_json as dump

PT = 72 / 25.4
LAYERS = ('plate', 'type', 'mark', 'finish', 'die', 'guides')
FONT_PATHS = FONT_PATHS
shaped, glyph_metrics = shaped, glyph_metrics
set_layers, raster = set_layers, raster
rgb, sha = rgb, legacy.sha


def rel(path):
    return str(Path(path).resolve())


class Surface(legacy.SurfaceBuilder):
    def __init__(self, size_mm, title, trim_mm=None):
        self.size_mm, self.title = list(size_mm), title
        self.doc = fitz.open()
        self.ocg = {name: self.doc.add_ocg(name, on=name not in ('die', 'guides')) for name in LAYERS}
        for name, xref in self.ocg.items():
            state = 'OFF' if name in ('die', 'guides') else 'ON'
            self.doc.xref_set_key(xref, 'Usage', f'<</Print <</PrintState /{state}>> /Export <</ExportState /{state}>>>>')
        self.doc.xref_set_key(self.doc.pdf_catalog(), 'OCProperties/D/Locked',
            '[' + ' '.join(f'{self.ocg[name]} 0 R' for name in ('die', 'guides')) + ']')
        self.page = self.doc.new_page(width=size_mm[0]*PT, height=size_mm[1]*PT)
        self.page.set_trimbox(fitz.Rect(*[v*PT for v in trim_mm]) if trim_mm else self.page.rect)
        self.page.set_bleedbox(self.page.rect)
        self.fonts, self.rows, self.elements = dict(FONT_PATHS), [], []
        for name, path in self.fonts.items():
            self.page.insert_font(fontname=name, fontfile=str(path))

    def add_plate(self, path, box_mm, name='plate'):
        self.page.insert_image(fitz.Rect(*[v*PT for v in box_mm]), filename=str(path),
            keep_proportion=False, oc=self.ocg['plate'])
        self.elements.append({'name': name, 'layer': 'plate', 'kind': 'raster',
            'box_mm': list(box_mm), 'source': rel(path), 'sha256': sha(path)})

    def svg(self, path, box_mm, *, layer='mark', name=None, color=None, rotate=0):
        source = Path(path).read_text()
        if color:
            source = re.sub(r'#[0-9a-fA-F]{6}', color, source)
            source = re.sub(r'fill="(?:black|white)"', f'fill="{color}"', source)
        with fitz.open(stream=source.encode(), filetype='svg') as svg:
            with fitz.open(stream=svg.convert_to_pdf(), filetype='pdf') as document:
                self.page.show_pdf_page(fitz.Rect(*[v*PT for v in box_mm]), document, 0,
                    keep_proportion=True, rotate=rotate, oc=self.ocg[layer])
        self.elements.append({'name': name or Path(path).stem, 'layer': layer,
            'kind': 'vector', 'box_mm': list(box_mm), 'source': rel(path), 'sha256': sha(path)})

    def save(self, path, flat_path=None):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.set_metadata({'title': self.title, 'creator': 'Round master',
            'subject': 'Six print layers; native save and reopen measured separately.'})
        self.doc.save(str(path), garbage=3, deflate=True)
        self.doc.close()
        if flat_path:
            render_flat(path, flat_path)
        return {'file': str(path), 'sha256': sha(path), 'type': self.rows, 'elements': self.elements,
                'readback': read_back_ai(path, self.elements, self.rows)}


def render_flat(path, out, clip_mm=None, layers=('plate', 'type', 'mark', 'finish'), dpi=300):
    return legacy.render_flat(path, out, clip_mm=clip_mm, layers=layers, dpi=dpi)


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
            presence.append({'name':element['name'],'layer':element['layer'],'kind':element['kind'],'ink_share':round(ink,6),'present':ink>0 or (element['kind']=='raster' and bool(d[0].get_image_info())),'logical_text_present':has_copy(element['copy']) if element.get('copy') else None})
    checks={'six_named_layers':[r['name'] for r in layers]==list(LAYERS),'die_guides_locked_nonprinting':all(r['locked'] and not r['print_on'] for r in layers if r['name'] in ('die','guides')),'fonts_embedded':all(r['embedded'] for r in fonts),'live_text_glyphs':glyphs>0 if rows else True,'all_expected_elements':all(x['present'] and x['logical_text_present'] is not False for x in presence),'all_expected_copy':all(has_copy(x['copy']) for x in rows),'no_missing_glyphs':all(not x.get('missing_glyphs') for x in rows)}
    native_path=Path(path).parent/'native-checks'/(Path(path).stem+'.json')
    native=json.loads(native_path.read_text()) if native_path.exists() else {}
    native_valid=bool(native.get('holds') and native.get('final_sha256')==sha(path))
    return {'schema':'round_master_ai_readback/1','method':'Fresh PyMuPDF PDF parse; actual font streams, text glyph operators, OCG lock/Print usage, each expected element rastered on its own isolated layer. Not an Illustrator application open/save.','layers':layers,'fonts':fonts,'images':images,'extracted_text':texts,'actual_text':actual,'live_glyph_count':glyphs,'elements':presence,'checks':checks,'pdf_compatible_holds':all(checks.values()),'native_illustrator_validated':native_valid,'native_census':rel(native_path) if native_valid else None,'native_illustrator_note':'Actual Illustrator 30.0 native save: live text frames, correct fonts, embedded raster and six locked/printable layer states independently censused; matching final file hash.' if native_valid else 'PDF-compatible .ai; no matching successful actual Illustrator census for these exact bytes.'}

def native_roundtrip(path, area_frames=None):
    """Rebuild the six groups in the real Illustrator, then independently read back.

    Temporary layer PDFs are solely interchange inputs and removed with their
    temporary directory; the deliverable remains one PDF-compatible native .ai.
    """
    import tempfile
    from apps.ire.handoff.illustrator_exec import run_jsx
    path=Path(path);stem=path.stem;checkdir=path.parent/'native-checks';checkdir.mkdir(exist_ok=True)
    before_sha=sha(path)
    with fitz.open(path) as d:
        size=[d[0].rect.width,d[0].rect.height];trim_before=list(d[0].trimbox);before=raster(d,300)
        oldglyphs=sum(len(x['chars']) for x in d[0].get_texttrace());expected_rasters=len(d[0].get_image_info())
    with tempfile.TemporaryDirectory(prefix='round-master-native-') as td:
        td=Path(td);sources={}
        for layer in LAYERS:
            lp=td/f'{layer}.pdf'
            with fitz.open(path) as d:
                set_layers(d,{layer})
                d.xref_set_key(d[0].xref,'PieceInfo','null')
                d.xref_set_key(d.pdf_catalog(),'PieceInfo','null')
                d.set_metadata({'creator':'Round master layer interchange'})
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
            Image.fromarray(before).save('/tmp/round-master-native-before.png');Image.fromarray(after).save('/tmp/round-master-native-after.png')
            Path('/tmp/round-master-native-candidate.ai').write_bytes(dest.read_bytes())
            report['render_shape_match']=same_shape
            report['render_mean_absolute_error']=float(np.abs(after.astype(float)-before.astype(float)).mean()) if same_shape else None
            outside=np.ones(before.shape[:2],dtype=bool)
            for frame in area_frames or []:
                x0,y0,x1,y1=[round(v*300/25.4) for v in frame['box_mm']];outside[max(0,y0):y1,max(0,x0):x1]=False
            report['outside_copy_zone_render_mae']=float(np.abs(after.astype(float)-before.astype(float))[outside].mean()) if same_shape else None
            report['render_comparison_scope']='Full page at300dpi; declared full-copy area frames excluded from the preservation comparison and measured separately for overset.'
            report['input_live_glyphs']=oldglyphs
            report['checks']={'six_layers':sorted(x['name'] for x in report['layers'])==sorted(LAYERS),'die_guides_locked_nonprinting':all(x['locked'] and not x['printable'] for x in report['layers'] if x['name'] in ('die','guides')),'live_fonts_expected':all(c['text'].isspace() or c['font'] in ('DMSans-Regular','Almarai-Regular') for x in report['frames'] for c in x['characterFonts']),'fonts_embedded':all(x['embedded_bytes']>0 for x in report['native_pdf_fonts']),'live_type_present':report['native_pdf_live_glyphs']>0 if oldglyphs else True,'raster_preserved':report['rasters']==expected_rasters,'placed_assets_embedded':report['placed']==0,'same_dimensions':same_shape,'render_preserved':same_shape and report['outside_copy_zone_render_mae']<3,'full_drafts_on_type':all(x['layer']=='type' and x['kind']=='TextType.AREATEXT' for x in report['areaFrames']), 'full_drafts_retained':len(report['areaFrames'])==len(area_frames) and all(x['fullContents']==f['copy'] for x,f in zip(report['areaFrames'],area_frames))}
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

def _native_reopen_once(paths):
    """Read the saved final .ai files in Illustrator itself; no source document edits."""
    import tempfile
    from apps.ire.handoff.illustrator_exec import run_jsx
    paths=[Path(p) for p in paths]
    with tempfile.TemporaryDirectory(prefix='round-master-reopen-') as td:
        td=Path(td);result=td/'reopened.json';script=td/'read.jsx'
        js=r'''(function(){var paths=__PATHS__,out=[],old=app.userInteractionLevel,d=null;function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}function j(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(j(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+j(v[k]));return '{'+a.join(',')+'}';}function charEvidence(t){var a=[],contents=t.contents;for(var k=0;k<contents.length;k++){var text=contents.charAt(k);if(/\s/.test(text)){a.push({text:text,font:null,size:null,nonprintingWhitespace:true});continue;}var v=t.characters[k].characterAttributes;a.push({text:text,font:v.textFont.name,size:v.size});}return a;}function linesEvidence(t){var a=[];for(var k=0;k<t.lines.length;k++)a.push(t.lines[k].contents);return a;}app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;try{for(var p=0;p<paths.length;p++){var r={file:paths[p],layers:[],frames:[]};try{d=app.open(new File(paths[p]));app.redraw();for(var i=0;i<d.layers.length;i++){var l=d.layers[i];r.layers.push({name:l.name,locked:l.locked,printable:l.printable});}for(var i=0;i<d.textFrames.length;i++){var t=d.textFrames[i];r.frames.push({text:t.contents,fullContents:t.contents,visibleLines:linesEvidence(t),characterFonts:charEvidence(t),font:t.characters[0].characterAttributes.textFont.name,layer:t.layer.name,kind:String(t.kind)});}r.rasters=d.rasterItems.length;r.placed=d.placedItems.length;r.reopened=true;}catch(e){r.error=String(e);r.reopened=false;}finally{if(d)d.close(SaveOptions.DONOTSAVECHANGES);d=null;}out.push(r);}}finally{app.userInteractionLevel=old;}var f=new File(__OUT__);f.encoding='UTF-8';f.open('w');f.write(j(out));f.close();return j({files:out.length});})();'''
        script.write_text(js.replace('__PATHS__',json.dumps([str(p) for p in paths])).replace('__OUT__',json.dumps(str(result))))
        execution=run_jsx(str(script),timeout_s=180)
        rows=json.loads(result.read_text()) if result.exists() else []
    if len(rows)!=len(paths):raise ValueError('Incomplete saved-file reopen census')
    for p,r in zip(paths,rows):
        r['execution']=execution
        recpath=p.parent/'native-checks'/(p.stem+'.json');rec=json.loads(recpath.read_text())
        if not r.get('reopened'):
            rec['failed_reopen']=r;dump(recpath,rec)
            raise ValueError('Illustrator could not reopen '+p.name+': '+str(r))
        if not isinstance(rec.get('frames'),list) or not isinstance(r.get('frames'),list):raise ValueError('Missing saved/reopened native frame census')
        complete_character_evidence=all('characterFonts' in x for x in rec['frames'])
        if complete_character_evidence:
            def signature(frame):return (frame['text'],tuple((c['text'],c['font'],round(c['size'],4) if c['size'] is not None else None) for c in frame['characterFonts']))
            expected=sorted(signature(x) for x in rec['frames']);found=sorted(signature(x) for x in r['frames'])
        else:
            # Explicit compatibility for the unchanged Round1B wraps/labels.
            expected=sorted((x['text'],x['font']) for x in rec['frames']);found=sorted((x['text'],x['font']) for x in r['frames'])
        r['font_comparison_scope']='Every non-whitespace character: text, font, size; all whitespace retained in exact contents. Whitespace font query omitted because Illustrator30 crashes on a trailing RTL space.' if complete_character_evidence else 'Legacy unchanged file: text and original single-font frame census'
        r['checks']={'reopened':r['reopened'],'same_live_text_and_fonts':expected==found,'six_layers':sorted(x['name'] for x in r['layers'])==sorted(LAYERS),'die_guides_locked_nonprinting':all(x['locked'] and not x['printable'] for x in r['layers'] if x['name'] in ('die','guides')),'raster_embedded':r['rasters']==rec.get('expected_rasters',rec['rasters']) and r['placed']==0,'area_frames_on_type':all(t['layer']=='type' for t in r['frames'] if t.get('kind')=='TextType.AREATEXT'),'area_frame_count':sum(t.get('kind')=='TextType.AREATEXT' for t in r['frames'])==len(rec['areaFrames'])}
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
            boxes=[];digits=[];alifs=[];font_refs=set()
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
                if unicodedata.normalize('NFKC',chr(char))=='ا':alifs.append({'char':chr(char),'above_baseline_mm':y1*scale/PT,'ink_height_mm':box[3]-box[1]})
                if chr(char).isdigit():digits.append({'char':chr(char),'height_mm':box[3]-box[1],'ink_bottom_mm':box[3]})
            if not boxes:results.append({'name':row['name'],'measured':False});continue
            ib=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
            reference=glyph_metrics('H' if row['face']=='latin' else 'ا',row['face'])['box_em']
            results.append({'name':row['name'],'measured':True,'actual_pdf_size_pt':t['size'],'ink_box_mm':ib,'ink_height_mm':ib[3]-ib[1],'digits':digits,'actual_joined_alifs':alifs,'cap_reference_height_mm':(reference[3]-reference[1])*t['size']/PT,'cap_reference':'H' if row['face']=='latin' else 'ا','cap_reference_source':row['font_path'],'embedded_font_xrefs':sorted(font_refs),'method':'Actual final PDF span size/origin/glyph IDs; ink contours from embedded font bytes. Canonical H/alif reference from the hash-pinned licensed face; native point size measured, not requested.'})
    return results


def native_reopen_checks(paths):
    """A transient Illustrator MRAP gets one fresh read, never a simulated verdict."""
    paths=list(paths)
    try:return _native_reopen_once(paths)
    except ValueError as exc:
        if 'MRAP' not in str(exc):raise
        retained=[]
        for path in paths:
            record=Path(path).parent/'native-checks'/(Path(path).stem+'.json')
            retained.append(json.loads(record.read_text()))
        rows=_native_reopen_once(paths)
        for path,old in zip(paths,retained):
            record=Path(path).parent/'native-checks'/(Path(path).stem+'.json')
            current=json.loads(record.read_text());current['first_reopen_failure']=old.get('failed_reopen')
            dump(record,current)
        return rows
