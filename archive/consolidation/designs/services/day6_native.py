"""Day 6 native Illustrator route for the D1 stand surfaces (review finding F7, prompt §2.2).

Every emitted surface package already carries artwork.pdf, artwork.svg and the
PDF-compatible .ai. This module adds the NATIVE file: editable Illustrator
objects built directly from design-graph.json — a gradient-filled FIELD
rectangle, the vector brand device as even-odd compound paths clipped to the
face, the rules, per-glyph live point text in the pinned faces, and the
approved vector logo — then validates the saved bytes against artwork.pdf.
Type never travels through PDF import (Day 5: that route outlines Arabic).
Face-local graph coordinates are millimetres from the upper left; Illustrator
script coordinates are points from the artboard's lower left, y up.
"""
from pathlib import Path
from collections import Counter
import json,math,shutil,tempfile,time,xml.etree.ElementTree as ET
import fitz,numpy as np
from . import fidelity_assets as fa
from apps.ire.handoff.illustrator_exec import run_jsx

ROOT=fa.ROOT/'docs/audit/day-6/stand/surfaces'
SURFACES=['header.front','riser.3.front','riser.2.front','lip.front','riser.1.front','side.left','side.right']
MM=72/25.4
RENDER_DPI=600
INK_MAE_LIMIT=3.
CROP_MAE_LIMIT=5.
STOP_TOLERANCE={'ramp_point':.5,'channel':1.}
CROP_PAD_MM=.5
BUILD_TIMEOUT_S=900
REVIEW_TIMEOUT_S=600
LOGO_NAME='APPROVED VECTOR LOGO'
ROUTE=('Direct native objects from design-graph.json: gradient FIELD rectangle, even-odd compound-path DEVICE inside an '
       'artboard-sized clipping group (the continuous strip is clipped per face), RULES rectangles, per-glyph live point '
       'text (size 100 then matrix x10, the Day 4/5 method; recorded default-size fallback if the size setter errors), '
       'the approved vector LOGO duplicated from the pinned SVG; saved pdfCompatible, re-opened for the census.')
MEANING='Native transport/editable-object check only; fidelity, critic and production review remain separate instruments.'

CENSUS_JS=r'''function rgbOf(c){return (c&&c.typename==='RGBColor')?[c.red,c.green,c.blue]:null;}
function census(d){var rows=[],i,j;
for(i=0;i<d.textFrames.length;i++){var t=d.textFrames[i],chars=[];for(j=0;j<t.characters.length;j++){var ca=t.characters[j].characterAttributes;chars.push({text:t.characters[j].contents,font:ca.textFont.name,size:ca.size,horizontal_scale:ca.horizontalScale,vertical_scale:ca.verticalScale});}
rows.push({name:t.name,text:t.contents,characters:chars,bounds:t.visibleBounds,hidden:t.hidden,opacity:t.opacity,layer:t.layer.name,layer_visible:t.layer.visible});}
var layers=[];for(i=0;i<d.layers.length;i++){var L=d.layers[i];layers.push({name:L.name,visible:L.visible,page_items:L.pageItems.length,path_items:L.pathItems.length,compound_paths:L.compoundPathItems.length,groups:L.groupItems.length,text_frames:L.textFrames.length});}
var gradient=null;for(i=0;i<d.pathItems.length;i++){var p=d.pathItems[i];if(p.name==='FIELD'&&p.fillColor.typename==='GradientColor'){var gc=p.fillColor,stops=[];for(j=0;j<gc.gradient.gradientStops.length;j++){var s=gc.gradient.gradientStops[j];stops.push({ramp_point:s.rampPoint,mid_point:s.midPoint,srgb:rgbOf(s.color)});}gradient={type:String(gc.gradient.type),name:gc.gradient.name,stops:stops,origin:gc.origin,angle:gc.angle,length:gc.length,bounds:p.geometricBounds};break;}}
var compounds=[];for(i=0;i<d.compoundPathItems.length;i++){var c=d.compoundPathItems[i];var first=c.pathItems.length?c.pathItems[0]:null;compounds.push({name:c.name,subpaths:c.pathItems.length,evenodd:first?first.evenodd:null,srgb:first?rgbOf(first.fillColor):null,layer:c.layer.name,bounds:c.geometricBounds});}
var groups=[];for(i=0;i<d.groupItems.length;i++){var g=d.groupItems[i];groups.push({name:g.name,clipped:g.clipped,page_items:g.pageItems.length,layer:g.layer.name,bounds:g.visibleBounds});}
var rules=[];for(i=0;i<d.pathItems.length;i++){var r=d.pathItems[i];if(r.layer.name==='RULES')rules.push({name:r.name,srgb:rgbOf(r.fillColor),bounds:r.geometricBounds});}
return {frames:rows,text_frames:d.textFrames.length,layers:layers,gradient:gradient,compound_paths:compounds,groups:groups,rules:rules,rasters:d.rasterItems.length,placed:d.placedItems.length,paths:d.pathItems.length,artboards:d.artboards.length,artboard:d.artboards[0].artboardRect,colour_space:String(d.documentColorSpace)};}
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function js(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(js(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+js(v[k]));return '{'+a.join(',')+'}';}
'''

BUILD_JS=r'''(function(){var D=__DATA__,doc=null,mark=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,R={stage:'start',saved:false,reopened:false,size_fallback_glyphs:0};
__CENSUS__
function colour(rgb){var c=new RGBColor();c.red=rgb[0];c.green=rgb[1];c.blue=rgb[2];return c;}
function pt(xy){return [xy[0]*D.mm,(D.height_mm-xy[1])*D.mm];}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
R.stage='document';doc=app.documents.add(DocumentColorSpace.RGB,D.w,D.h);doc.artboards[0].artboardRect=[0,D.h,D.w,0];
R.stage='field';var fieldLayer=doc.layers[0];fieldLayer.name='FIELD';
if(D.field){var grad=doc.gradients.add();grad.name='D1 FIELD';grad.type=GradientType.LINEAR;while(grad.gradientStops.length<D.field.stops.length)grad.gradientStops.add();
for(var i=0;i<D.field.stops.length;i++){var st=grad.gradientStops[i];st.rampPoint=D.field.stops[i].offset*100;st.midPoint=50;st.color=colour(D.field.stops[i].srgb);}
var rect=fieldLayer.pathItems.rectangle(D.h,0,D.w,D.h);rect.name='FIELD';rect.stroked=false;rect.filled=true;
var gc=new GradientColor();gc.gradient=grad;var ga=pt(D.field.start_mm),gb=pt(D.field.end_mm);var ang=Math.atan2(gb[1]-ga[1],gb[0]-ga[0])*180/Math.PI,len=Math.sqrt((gb[0]-ga[0])*(gb[0]-ga[0])+(gb[1]-ga[1])*(gb[1]-ga[1]));R.field_set={origin:ga,angle:ang,length:len};rect.fillColor=gc;var fc=rect.fillColor;R.field_readback_default={origin:fc.origin,angle:fc.angle,length:fc.length};fc.origin=ga;fc.angle=ang;fc.length=len;rect.fillColor=fc;var rb=rect.fillColor;R.field_readback_after_reassign={origin:rb.origin,angle:rb.angle,length:rb.length};if(Math.abs(rb.origin[0]-ga[0])>.5||Math.abs(rb.origin[1]-ga[1])>.5||Math.abs(rb.angle-ang)>.5||Math.abs(rb.length-len)>.5){R.stage='field.transform';var s=len/rb.length,th=(ang-rb.angle)*Math.PI/180,ca=s*Math.cos(th),sa=s*Math.sin(th),p0=rb.origin;var gm=app.getIdentityMatrix();gm.mValueA=ca;gm.mValueB=sa;gm.mValueC=-sa;gm.mValueD=ca;gm.mValueTX=ga[0]-(ca*p0[0]-sa*p0[1]);gm.mValueTY=ga[1]-(sa*p0[0]+ca*p0[1]);rect.transform(gm,false,false,true,false,1,Transformation.DOCUMENTORIGIN);var rb2=rect.fillColor;R.field_readback_after_transform={origin:rb2.origin,angle:rb2.angle,length:rb2.length};R.field_method='gradient-only matrix transform from the default vector (re-assignment was ignored)';}else{R.field_method='GradientColor vector re-assigned after fill';}}
R.stage='device';var deviceLayer=doc.layers.add();deviceLayer.name='DEVICE';
if(D.device_roles.length){var clipGroup=deviceLayer.groupItems.add();clipGroup.name='DEVICE (clipped to face)';
for(var r=0;r<D.device_roles.length;r++){var role=D.device_roles[r];R.stage='device.'+role.role;var cp=clipGroup.compoundPathItems.add();cp.name=role.role;
for(var k=0;k<role.paths.length;k++){var pts=role.paths[k],arr=[];for(var m=0;m<pts.length;m++)arr.push(pt(pts[m]));var sp=cp.pathItems.add();sp.setEntirePath(arr);sp.closed=true;sp.stroked=false;sp.filled=true;sp.fillColor=colour(role.colour_srgb);sp.evenodd=true;}}
R.stage='device.clip';var clip=clipGroup.pathItems.rectangle(D.h,0,D.w,D.h);clip.name='FACE CLIP';clip.filled=false;clip.stroked=false;clip.clipping=true;clipGroup.clipped=true;}
R.stage='rules';var rulesLayer=doc.layers.add();rulesLayer.name='RULES';
for(var i=0;i<D.rules.length;i++){var e=D.rules[i],bb=e.bbox_mm;var rr=rulesLayer.pathItems.rectangle((D.height_mm-bb[1])*D.mm,bb[0]*D.mm,(bb[2]-bb[0])*D.mm,(bb[3]-bb[1])*D.mm);rr.name=e.id;rr.stroked=false;rr.filled=true;rr.fillColor=colour(e.colour_srgb);}
R.stage='type';var typeLayer=doc.layers.add();typeLayer.name='LIVE TYPE';doc.activeLayer=typeLayer;
for(var i=0;i<D.lines.length;i++){var line=D.lines[i],group=typeLayer.groupItems.add();group.name=line.id;
for(var j=0;j<line.runs.length;j++){R.current_glyph=line.id+'-'+j;var run=line.runs[j];R.stage='type.frame';var tf=doc.textFrames.pointText([0,0]);tf.contents=run.text;tf.name=line.id+'-'+j;var at=tf.textRange.characterAttributes;var size0;
R.stage='type.size';try{at.size=100;size0=100;}catch(sizeError){R.size_setter_error=String(sizeError);R.size_fallback_glyphs++;size0=at.size;}
R.stage='type.font';at.textFont=app.textFonts.getByName(D.fonts[run.font_role]);R.stage='type.colour';at.fillColor=colour(line.colour);tf.move(group,ElementPlacement.PLACEATEND);
R.stage='type.matrix';var mat=app.getIdentityMatrix();mat.mValueA=run.scale_x_mm_per_1000pt_unit*D.mm*1000/size0;mat.mValueD=run.scale_y_mm_per_1000pt_unit*D.mm*1000/size0;mat.mValueTX=run.x_mm*D.mm;mat.mValueTY=run.baseline_z_mm*D.mm;tf.transform(mat,true,true,true,true,1,Transformation.DOCUMENTORIGIN);}}
R.stage='logo';var logoLayer=doc.layers.add();logoLayer.name='LOGO';
if(D.logo){mark=app.open(new File(D.logo.file));var items=[];for(var j=0;j<mark.pageItems.length;j++){var it=mark.pageItems[j];if(it.parent.typename==='Layer')items.push(it);}R.logo_top_level_items=items.length;
var grp=mark.groupItems.add();for(var j=0;j<items.length;j++)items[j].moveToBeginning(grp);var clone=grp.duplicate(doc,ElementPlacement.PLACEATBEGINNING);mark.close(SaveOptions.DONOTSAVECHANGES);mark=null;doc.activate();clone.move(logoLayer,ElementPlacement.PLACEATBEGINNING);
var lb=D.logo.bbox_mm;clone.width=(lb[2]-lb[0])*D.mm;clone.height=(lb[3]-lb[1])*D.mm;clone.position=[lb[0]*D.mm,(D.height_mm-lb[1])*D.mm];clone.name='APPROVED VECTOR LOGO';R.logo_bounds=clone.visibleBounds;}
R.stage='census';R.built_census=census(doc);
R.stage='save';var options=new IllustratorSaveOptions();options.pdfCompatible=true;doc.saveAs(new File(D.out),options);R.saved=true;
R.stage='reopen';doc.close(SaveOptions.DONOTSAVECHANGES);doc=null;doc=app.open(new File(D.out));R.reopened_census=census(doc);R.reopened=true;R.stage='done';
}catch(e){R.error=String(e);R.error_stage=R.stage;}
finally{if(mark){try{mark.close(SaveOptions.DONOTSAVECHANGES);}catch(e2){R.mark_close_error=String(e2);}}if(doc){try{doc.close(SaveOptions.DONOTSAVECHANGES);}catch(e3){R.doc_close_error=String(e3);}}if(prior){try{prior.activate();}catch(e4){R.prior_activate_error=String(e4);}}app.userInteractionLevel=old;}
var f=new File(D.census);f.encoding='UTF-8';f.open('w');f.write(js(R));f.close();return js({saved:R.saved,reopened:R.reopened,error:R.error,stage:R.stage});})();'''

INSPECT_JS=r'''(function(){var D=__DATA__,doc=null,prior=app.documents.length?app.activeDocument:null,old=app.userInteractionLevel,R={stage:'start',reopened:false};
__CENSUS__
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;R.stage='open';doc=app.open(new File(D.input));R.stage='census';R.reopened_census=census(doc);R.reopened=true;R.stage='done';}
catch(e){R.error=String(e);R.error_stage=R.stage;}
finally{if(doc){try{doc.close(SaveOptions.DONOTSAVECHANGES);}catch(e2){R.doc_close_error=String(e2);}}if(prior){try{prior.activate();}catch(e3){R.prior_activate_error=String(e3);}}app.userInteractionLevel=old;}
var f=new File(D.census);f.encoding='UTF-8';f.open('w');f.write(js(R));f.close();return js({reopened:R.reopened,error:R.error,stage:R.stage});})();'''


def to_points(xy_mm,height_mm):
    """Face coordinates (mm from the upper left) -> Illustrator points (lower-left origin, y up)."""
    return [xy_mm[0]*MM,(height_mm-xy_mm[1])*MM]


def gradient_vector(field,height_mm):
    a=to_points(field['start_mm'],height_mm);b=to_points(field['end_mm'],height_mm)
    return {'origin':a,'angle':math.degrees(math.atan2(b[1]-a[1],b[0]-a[0])),'length':math.hypot(b[0]-a[0],b[1]-a[1])}


def flat_to_topleft(flat_bbox_mm,width_mm,height_mm):
    """Bottle convention [x from centre, z from bottom] -> surface convention [x0,y0,x1,y1] from the upper left."""
    a,z0,b,z1=flat_bbox_mm
    return [a+width_mm/2,height_mm-z1,b+width_mm/2,height_mm-z0]


def pixel_window(bbox_mm,shape,*,dpi=RENDER_DPI,pad_mm=CROP_PAD_MM):
    """Upper-left bbox [x0,y0,x1,y1] mm -> (row0,row1,col0,col1) in a top-down raster; no vertical flip."""
    k=dpi/25.4;a,b,c,d=bbox_mm
    col0=max(0,int((a-pad_mm)*k));col1=min(shape[1],int((c+pad_mm)*k)+1)
    row0=max(0,int((b-pad_mm)*k));row1=min(shape[0],int((d+pad_mm)*k)+1)
    return row0,row1,col0,col1


def expected_glyphs(spec):
    return Counter((run['text'],spec['fonts'][run['font_role']]['postscript']) for line in spec['graph']['lines'] for run in line['runs'])


def found_glyphs(census):
    return Counter((ch['text'],ch['font']) for frame in census['frames'] for ch in frame['characters'])


def compare_glyphs(expected,found):
    missing=sorted(((t,f),n) for (t,f),n in (expected-found).items());unexpected=sorted(((t,f),n) for (t,f),n in (found-expected).items())
    return {'expected_count':sum(expected.values()),'found_count':sum(found.values()),'matched':expected==found,
            'missing':[{'text':t,'font':f,'count':n} for (t,f),n in missing],'unexpected':[{'text':t,'font':f,'count':n} for (t,f),n in unexpected]}


def compare_gradient(field,found):
    expected=[{'ramp_point':s['offset']*100,'srgb':s['srgb']} for s in field['stops']]
    result={'expected_stops':expected,'found':found,'matched':False}
    if found is None:
        result['reason']='no FIELD path carrying a GradientColor was read back';return result
    stops=sorted(found['stops'],key=lambda s:s['ramp_point'])
    if len(stops)!=len(expected):
        result['reason']=f'{len(stops)} stops read back, {len(expected)} expected';return result
    ramp=max(abs(s['ramp_point']-e['ramp_point']) for s,e in zip(stops,expected))
    channel=max(abs(a-b) for s,e in zip(stops,expected) for a,b in zip(s['srgb'],e['srgb']))
    result.update(max_ramp_point_error=ramp,max_channel_error=channel,tolerance=STOP_TOLERANCE,linear=found['type'].endswith('LINEAR'),
                  matched=ramp<=STOP_TOLERANCE['ramp_point'] and channel<=STOP_TOLERANCE['channel'] and found['type'].endswith('LINEAR'))
    return result


def critical_regions(graph):
    """Upper-left mm boxes for every element, every copy line and the device's on-face extent."""
    w,h=graph['width_mm'],graph['height_mm'];regions=[{'element':e['id'],'bbox_mm':e['bbox_mm']} for e in graph['elements']]
    regions+=[{'element':line['id'],'bbox_mm':line['measured_bbox_mm']} for line in graph['lines']]
    for role in graph['device_roles']:
        pts=np.array([p for path in role['paths'] for p in path['points_mm']],float)
        a,b=np.maximum(pts.min(axis=0),0);c,d=np.minimum(pts.max(axis=0),[w,h])
        if c>a and d>b:regions.append({'element':'device.'+role['role'],'bbox_mm':[float(a),float(b),float(c),float(d)]})
    return regions


def census_checks(spec,census):
    """Pure structural checks on a re-opened census against the design spec."""
    graph=spec['graph'];details={}
    details['glyphs']=compare_glyphs(expected_glyphs(spec),found_glyphs(census))
    expected_fonts=sorted({spec['fonts'][run['font_role']]['postscript'] for line in graph['lines'] for run in line['runs']})
    found_fonts=sorted({ch['font'] for frame in census['frames'] for ch in frame['characters']})
    details['fonts']={'expected':expected_fonts,'found':found_fonts,'matched':expected_fonts==found_fonts}
    details['type_visibility']={'frames':len(census['frames']),'all_visible':all((not f['hidden']) and f['opacity']>=99.9 and f['layer_visible'] for f in census['frames'])}
    checks={'fonts_matched':details['fonts']['matched'],'glyph_multiset_matched':details['glyphs']['matched'],'type_visible':details['type_visibility']['all_visible'],
            'rasters_zero':census['rasters']==0 and census['placed']==0,'paths_present':census['paths']>0,'artboards_one':census['artboards']==1}
    if graph['field'] is not None:
        details['gradient']=compare_gradient(graph['field'],census['gradient']);checks['gradient_stops_matched']=details['gradient']['matched']
    expected_subpaths={role['role']:len(role['paths']) for role in graph['device_roles']}
    device_compounds=[c for c in census['compound_paths'] if c['layer']=='DEVICE']
    found_subpaths={c['name']:c['subpaths'] for c in device_compounds}
    evenodd=all(c['evenodd'] is True for c in device_compounds)
    details['device']={'expected_subpaths':expected_subpaths,'found_subpaths':found_subpaths,'evenodd':evenodd,
                       'clip':'artboard-sized clipping group; the continuous front strip is clipped per face' if expected_subpaths else 'no device on this face'}
    if expected_subpaths:
        clipped=any(g['name']=='DEVICE (clipped to face)' and g['clipped'] for g in census['groups'])
        checks['device_subpaths_matched']=expected_subpaths==found_subpaths and evenodd;checks['device_clipped_to_face']=clipped;details['device']['clipped_group']=clipped
    if any(e['id']=='logo' for e in graph['elements']):
        checks['logo_present']=any(g['name']==LOGO_NAME for g in census['groups'])
    rules=[e for e in graph['elements'] if e['id'].endswith('rule')]
    if rules:
        checks['rules_present']=sorted(r['name'] for r in census['rules'])==sorted(e['id'] for e in rules)
    details['layers']=[L['name'] for L in census['layers']]
    return checks,details


def _render(path,dpi):
    with fitz.open(path) as doc:
        pix=doc[0].get_pixmap(dpi=dpi,alpha=True);rgba=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4)
        return rgba[:,:,:3].astype(float)+128*(1-rgba[:,:,3:4]/255),rgba[:,:,3]>0


def render_compare(folder,graph,*,dpi=RENDER_DPI):
    folder=Path(folder);reference,mask=_render(folder/'artwork.pdf',dpi);native,_=_render(folder/'artwork-native.ai',dpi)
    visual={'dpi':dpi,'background':'neutral 128 behind any transparency','reference':'artwork.pdf','candidate':'artwork-native.ai PDF-compatible stream',
            'reference_shape':list(reference.shape[:2]),'candidate_shape':list(native.shape[:2]),'shape_equal':reference.shape==native.shape,
            'ink_mean_limit':INK_MAE_LIMIT,'critical_crop_limit':CROP_MAE_LIMIT}
    if not visual['shape_equal']:return visual
    error=np.abs(reference-native);crops=[]
    for region in critical_regions(graph):
        r0,r1,c0,c1=pixel_window(region['bbox_mm'],mask.shape,dpi=dpi);local=error[r0:r1,c0:c1];lm=mask[r0:r1,c0:c1]
        if not lm.any():raise ValueError(f'Critical crop {region["element"]} holds no reference ink; it cannot be scored.')
        crops.append({'element':region['element'],'bbox_mm':region['bbox_mm'],'ink_mean_absolute_error':float(local[lm].mean())})
    visual.update(ink_mean_absolute_error=float(error[mask].mean()),page_mean_absolute_error=float(error.mean()),p99_absolute_error=float(np.quantile(error,.99)),critical_crops=crops)
    return visual


def validate(folder,report):
    folder=Path(folder).resolve();spec=json.loads((folder/'design-spec.json').read_text());graph=spec['graph']
    result={'surface_id':spec['surface_id'],'route':ROUTE,'executed':report['executed'],'saved':bool(report['saved']) if 'saved' in report else False,
            'reopened':bool(report['reopened']) if 'reopened' in report else False,'illustrator_stage':report['stage'] if 'stage' in report else None}
    for key in ('error','error_stage','reason','size_setter_error','size_fallback_glyphs','logo_top_level_items','field_set','field_readback_default','field_readback_after_reassign','field_readback_after_transform','field_method'):
        if key in report:result[key]=report[key]
    checks={}
    if result['reopened']:
        checks,details=census_checks(spec,report['reopened_census']);result.update(details)
        result['census_summary']={k:report['reopened_census'][k] for k in ('text_frames','paths','rasters','placed','artboards','colour_space')}
    else:
        result['census_summary']=None
    if (folder/'artwork-native.ai').exists() and result['saved']:
        visual=render_compare(folder,graph);result['visual']=visual
        checks['render_shape_equal']=visual['shape_equal']
        if visual['shape_equal']:
            checks['ink_mae_within_limit']=visual['ink_mean_absolute_error']<INK_MAE_LIMIT
            checks['critical_crops_within_limit']=all(c['ink_mean_absolute_error']<CROP_MAE_LIMIT for c in visual['critical_crops'])
    else:
        result['visual']=None
    result['checks']=checks
    failed=[name for name,ok in checks.items() if not ok]
    if not result['executed']:failed.insert(0,'illustrator_not_executed')
    if not result['saved']:failed.insert(0,'native_not_saved')
    if not result['reopened']:failed.insert(0,'native_not_reopened')
    result['passed']=not failed;result['failed_checks']=failed
    result['copy_lines']=len(graph['lines'])
    if not graph['lines']:result['live_type_note']='No copy on this face: the live-type checks hold trivially (zero expected glyphs, zero text frames).'
    result['source_hashes']={n:fa.sha(folder/n) for n in ('artwork-native.ai','artwork.pdf','design-graph.json','design-spec.json','artwork-native.jsx') if (folder/n).exists()}
    result['meaning']=MEANING
    (folder/'artwork-native-validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def check_fonts(spec):
    installed=Path.home()/'Library/Fonts'
    for role,record in spec['fonts'].items():
        target=installed/record['filename']
        if not target.exists():raise FileNotFoundError(f'Pinned face {record["filename"]} is not installed in {installed}.')
        if fa.sha(target)!=record['sha256']:raise ValueError(f'Installed {record["filename"]} differs from the pinned bytes ({role}).')


def native_logo(folder,element):
    """The pinned package logo recoloured for this face; Illustrator opens it as a document."""
    root=ET.parse(Path(folder)/'assets/bbrose-logo.svg').getroot();x0,y0,x1,y1=element['bbox_mm']
    root.attrib.update(x='0',y='0',width=str(x1-x0),height=str(y1-y0),preserveAspectRatio='none')
    colour='#'+''.join(f'{round(v):02x}' for v in element['colour_srgb'])
    for p in root.iter():
        if p.tag.endswith(('path','polygon','rect','circle','ellipse')):p.set('fill',colour)
    target=Path(folder)/'native-logo.svg';target.write_bytes(ET.tostring(root));return target


def payload(folder,spec):
    folder=Path(folder).resolve();graph=spec['graph'];w,h=graph['width_mm'],graph['height_mm']
    logos=[e for e in graph['elements'] if e['id']=='logo']
    data={'surface_id':spec['surface_id'],'w':w*MM,'h':h*MM,'mm':MM,'width_mm':w,'height_mm':h,'field':graph['field'],
          'device_roles':[{'role':r['role'],'colour_srgb':r['colour_srgb'],'paths':[p['points_mm'] for p in r['paths']]} for r in graph['device_roles']],
          'rules':[{'id':e['id'],'bbox_mm':e['bbox_mm'],'colour_srgb':e['colour_srgb']} for e in graph['elements'] if e['id'].endswith('rule')],
          'lines':[{'id':l['id'],'colour':l['colour'],'runs':l['runs']} for l in graph['lines']],
          'fonts':{role:spec['fonts'][role]['postscript'] for role in spec['fonts']},
          'logo':{'file':str(native_logo(folder,logos[0])),'bbox_mm':logos[0]['bbox_mm']} if logos else None,
          'out':str(folder/'artwork-native.ai'),'census':str(folder/'artwork-native-census.json')}
    return data


def jsx_source(data):
    return BUILD_JS.replace('__CENSUS__',CENSUS_JS).replace('__DATA__',json.dumps(data))


def archive_previous_attempt(folder):
    folder=Path(folder);names=['artwork-native.ai','artwork-native.jsx','artwork-native-census.json','artwork-native-validation.json']
    present=[n for n in names if (folder/n).exists()]
    if not present:return None
    target=folder/'native-attempts'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());target.mkdir(parents=True,exist_ok=False)
    for n in present:shutil.move(str(folder/n),str(target/n))
    return target


def build(folder,*,timeout_s=BUILD_TIMEOUT_S):
    folder=Path(folder).resolve();spec=json.loads((folder/'design-spec.json').read_text());check_fonts(spec)
    archived=archive_previous_attempt(folder)
    script=folder/'artwork-native.jsx';script.write_text(jsx_source(payload(folder,spec)))
    started=time.time();execution=run_jsx(str(script),timeout_s=timeout_s);elapsed=time.time()-started
    census=folder/'artwork-native-census.json'
    report=json.loads(census.read_text()) if census.exists() else {'saved':False,'reopened':False}
    report['executed']=execution['executed']
    if not execution['executed']:report['reason']=execution['reason']
    report['illustrator_seconds']=elapsed
    if archived is not None:report['previous_attempt_archived_to']=str(archived.relative_to(folder))
    result=validate(folder,report);result['illustrator_seconds']=elapsed
    (folder/'artwork-native-validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def verify_existing(folder,*,timeout_s=REVIEW_TIMEOUT_S):
    """Re-open an owned copy of the saved native file for a fresh census; never touches a user document."""
    folder=Path(folder).resolve()
    with tempfile.TemporaryDirectory(prefix='bbrose-day6-native-review-') as tmp:
        owned=Path(tmp)/'owned-review-copy.ai';shutil.copyfile(folder/'artwork-native.ai',owned);census=Path(tmp)/'census.json'
        script=Path(tmp)/'inspect.jsx';script.write_text(INSPECT_JS.replace('__CENSUS__',CENSUS_JS).replace('__DATA__',json.dumps({'input':str(owned),'census':str(census)})))
        execution=run_jsx(str(script),timeout_s=timeout_s)
        report=json.loads(census.read_text()) if census.exists() else {'reopened':False}
    report['executed']=execution['executed'];report['saved']=(folder/'artwork-native.ai').exists()
    if not execution['executed']:report['reason']=execution['reason']
    report['method']='reopened_existing_native'
    result=validate(folder,report);result['method']='reopened_existing_native'
    (folder/'artwork-native-validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def build_all(surfaces=SURFACES,*,timeout_s=BUILD_TIMEOUT_S):
    results={}
    for identity in surfaces:
        result=build(ROOT/identity,timeout_s=timeout_s);results[identity]=result
        print(identity,'passed' if result['passed'] else 'FAILED',result['failed_checks'],result['error'] if 'error' in result else '',flush=True)
    return results
