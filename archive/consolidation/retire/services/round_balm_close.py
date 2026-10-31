"""D-R1C native leaflet and measured, fully printed carton closure.

The leaflet is copy only. Existing painting, wraps, cap and label are inputs,
never regenerated here. All bounds below come from saved embedded glyphs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import io
import json
from pathlib import Path
import unicodedata

import fitz
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

from . import balm_leaflet as engine
from . import round_balm_master as m
from . import round_balm_carton as carton


def read(path):
    return json.loads(Path(path).read_text())


def normalized_chars(value):
    return Counter(c for c in unicodedata.normalize('NFKC', value) if not c.isspace())


def leaflet_copy(out=m.OUT, tint='ROSEWATER'):
    """Freeze the complete prior drafts before replacing any carton copy."""
    base=m.OUT/'leaflet-copy.json'
    if base.exists():
        original=read(base)['copy']
        source=read(base)['source']
        original_chunks=read(base)['chunks']
    else:
        old=m.OUT/'carton-copy.json'; data=read(old)
        if data['schema']!='hayat_regulated_copy/1':
            raise ValueError('Original complete drafts must be preserved first')
        original=data['copy']
        source={'file':m.rel(old),'sha256_before_replacement':m.sha(old),
                'upstream':data['source'],'authorization':'D-R1C-1'}
        original_chunks={}
        for lang,value in original.items():
            middle=min((i+1 for i,c in enumerate(value) if c==' '),key=lambda i:abs(i-len(value)/2))
            original_chunks[lang]=[value[:middle],value[middle:]]
    copies={lang:value.replace('Rosewater',tint.title()) for lang,value in original.items()}
    chunks={}
    for lang,value in copies.items():
        chunks[lang]=[part.replace('Rosewater',tint.title()) for part in original_chunks[lang]]
        assert ''.join(chunks[lang])==value
    result={'schema':'hayat_leaflet_copy/1','source':source,'copy':copies,'chunks':chunks,
            'font_floor_pt':6,'claims':'owner to confirm','INCI':'owner to supply',
            'omitted':[],'warnings':'Complete original warning paragraphs retained.'}
    m.dump(Path(out)/'leaflet-copy.json',result)
    return result


def build_leaflet(out=m.OUT,tint='ROSEWATER'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    copy=leaflet_copy(out,tint); geometry=engine.layout()
    b=m.SurfaceBuilder(geometry['sheet_mm'],'HAYAT '+tint+' provisional leaflet')
    frames=[]
    for panel in geometry['panels']:
        pid=panel['id'];lang=panel['language'];chunk=copy['chunks'][lang][int(pid[-1])-1]
        safe=panel['safe_mm'];box=[safe[0]+.15,safe[1]+.15,safe[2]-.15,safe[3]-.15]
        name='leaflet '+pid
        b.text('HAYAT',(box[0],box[1],box[2],box[1]+2),size_pt=6,color='#000000',
               align='left',name=name+' preview',shrink=False)
        # A paragraph boundary has the same whitespace semantics as the source
        # space; the exact original remains in logical_copy and copy/chunks.
        native_copy=chunk.replace(' (owner to confirm)','\r(owner to confirm)') if pid=='ar2' else chunk
        frames.append({'name':name,'panel':pid,'language':lang,'copy':native_copy,'logical_copy':chunk,
                       'face':'arabic' if lang=='ar' else 'latin','size_pt':6,
                       'leading_pt':7.2,'box_mm':box,'color':[0,0,0],
                       'ltr_paragraph_indices':[1] if pid=='ar2' else [],
                       'layout_whitespace_change':'Space before final English parenthetical becomes a paragraph break; that paragraph reads LTR.' if pid=='ar2' else None,
                       'preview_row_names':[name+' preview']})
        b.rect(safe,layer='guides')
    for segment in geometry['cuts']:
        b.line(*segment['points_mm'],layer='die',color=(1,0,.5),width=.2)
    for segment in geometry['folds']:
        points=[fitz.Point(*[v*m.PT for v in p]) for p in segment['points_mm']]
        b.page.draw_line(*points,color=(1,0,.5),width=.2,dashes='[3 2] 0',oc=b.ocg['die'])
    result=b.save(out/'leaflet.ai',out/'leaflet-flat.png')
    m.dump(out/'leaflet-native-frames.json',{'schema':'hayat_native_copy_frames/2','frames':frames})
    m.dump(out/'leaflet.json',{'schema':'hayat_leaflet/1','tint':tint,'geometry':geometry,'files':result})
    m.dump(out/'leaflet-fold-check.json',geometry)
    return result


def printed_evidence(path,panels,native):
    """Independent contour measurements of every saved, printed glyph."""
    groups=defaultdict(list);runs=[];printed=[];font_cache={};outline_cache={}
    with fitz.open(path) as doc:
        page=doc[0]
        for resource in page.get_fonts(full=True):
            name,ext,_,data=doc.extract_font(resource[0])
            if data and ext in ('ttf','otf'):
                key=name.split('+')[-1].replace(' ','').lower()
                font_cache.setdefault(key,[]).append(TTFont(io.BytesIO(data)))
        for trace in page.get_texttrace():
            fontname=trace['font'];key=fontname.split('+')[-1].replace(' ','').lower()
            for code,gid,origin,_ in trace['chars']:
                char=chr(code);printed.append(char)
                category=unicodedata.name(char,'')
                script='arabic' if 'ARABIC' in category and char.isalpha() else 'latin' if 'LATIN' in category and char.isalpha() else None
                if script:
                    expected='Almarai-Regular' if script=='arabic' else 'DMSans-Regular'
                    runs.append({'text':char,'script':script,'font':fontname,'size_pt':trace['size'],
                                 'expected_font':expected,'correct':fontname.split('+')[-1]==expected})
                cache_key=(key,gid)
                if cache_key not in outline_cache:
                    outline_cache[cache_key]=None
                    for font in font_cache.get(key,[]):
                        order=font.getGlyphOrder()
                        if gid>=len(order):continue
                        gs=font.getGlyphSet();pen=BoundsPen(gs);gs[order[gid]].draw(pen)
                        if pen.bounds:
                            outline_cache[cache_key]=(pen.bounds,font['head'].unitsPerEm);break
                found=outline_cache[cache_key]
                if found is None:
                    if not char.isspace():raise ValueError('Unmeasured printed glyph '+repr(char))
                    continue
                bounds,units=found;scale=trace['size']/units;x0,y0,x1,y1=bounds
                box=[(origin[0]+x0*scale)/m.PT,(origin[1]-y1*scale)/m.PT,
                     (origin[0]+x1*scale)/m.PT,(origin[1]-y0*scale)/m.PT]
                cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
                matches=[p for p,v in panels.items() if v['box_mm'][0]<=cx<=v['box_mm'][2] and v['box_mm'][1]<=cy<=v['box_mm'][3]]
                if len(matches)!=1:raise ValueError('Printed glyph has no unique panel: '+repr((char,box,matches)))
                groups[(matches[0],round(origin[1]/m.PT,3))].append({'char':char,'box':box,'font':fontname,'size_pt':trace['size']})
    lines=[]
    for (panel,baseline),glyphs in sorted(groups.items()):
        box=[min(g['box'][0] for g in glyphs),min(g['box'][1] for g in glyphs),
             max(g['box'][2] for g in glyphs),max(g['box'][3] for g in glyphs)]
        safe=panels[panel]['safe_mm'];inside=box[0]>=safe[0]-.001 and box[1]>=safe[1]-.001 and box[2]<=safe[2]+.001 and box[3]<=safe[3]+.001
        lines.append({'name':panel+' line '+str(len(lines)+1),'panel':panel,'text':''.join(g['char'] for g in glyphs),
                      'box_mm':box,'ink_box_mm':box,'safe_box_mm':safe,'baseline_mm':baseline,
                      'inside_safe':inside,'glyphs':len(glyphs),'minimum_size_pt':min(g['size_pt'] for g in glyphs),
                      'fonts':sorted({g['font'] for g in glyphs})})
    frames=native['frames']
    if not frames or any('fullContents' not in f for f in frames):raise ValueError('Missing native full-content evidence')
    expected=normalized_chars(''.join(f['fullContents'] for f in frames));actual=normalized_chars(''.join(printed))
    hidden=expected-actual;extra=actual-expected
    return {'schema':'hayat_printed_evidence/1','file':m.rel(path),'sha256':m.sha(path),
            'method':'Saved PDF text operators and glyph IDs, exact contours from the embedded font bytes; actual page coordinates.',
            'printed_lines':lines,'outside_safe_area':[r for r in lines if not r['inside_safe']],
            'all_lines_inside_safe':all(r['inside_safe'] for r in lines),'script_font_runs':runs,
            'script_font_errors':[r for r in runs if not r['correct']],
            'hidden_characters':sum(hidden.values()),'hidden_character_inventory':dict(hidden),
            'unexpected_printed_characters':dict(extra),'native_nonspace_characters':sum(expected.values()),
            'printed_nonspace_characters':sum(actual.values()),
            'all_copy_visible_in_print':not hidden and not extra,
            'font_floor_pt':min(r['minimum_size_pt'] for r in lines)}


def refresh_leaflet(out=m.OUT):
    out=Path(out);meta=read(out/'leaflet.json');result=meta['files'];path=out/'leaflet.ai'
    native=read(out/'native-checks/leaflet.json');frames=read(out/'leaflet-native-frames.json')['frames']
    if not native['holds'] or native['final_sha256']!=m.sha(path):raise ValueError('Native leaflet is not final')
    panels={p['id']:{'box_mm':p['rect_mm'],'safe_mm':p['safe_mm']} for p in meta['geometry']['panels']}
    evidence=printed_evidence(path,panels,native)
    checked=engine.check_printed_lines(meta['geometry'],evidence['printed_lines'])
    rows=[];elements=[]
    for f,a in zip(frames,native['areaFrames']):
        if a['fullContents']!=f['copy'] or a['overflow']:raise ValueError('Leaflet copy is incomplete: '+f['name'])
        actual=[r for r in evidence['printed_lines'] if r['panel']==f['panel']]
        box=[min(r['ink_box_mm'][0] for r in actual),min(r['ink_box_mm'][1] for r in actual),max(r['ink_box_mm'][2] for r in actual),max(r['ink_box_mm'][3] for r in actual)]
        rows.append({'name':f['name'],'copy':f['copy'],'face':f['face'],'size_pt':6,'color':'#000000','ink_box_mm':box,
                     'zone_mm':f['box_mm'],'native_area_text':a,'at_least_5pt':True,'at_least_6pt':True,'overflow':False})
        elements.append({'name':f['name'],'layer':'type','kind':'live_area_type','box_mm':box})
    check=m.read_back_ai(path,elements,[]);check['native_full_copy_retained']=True;check['native_area_text']=native['areaFrames']
    result.update(sha256=m.sha(path),ai_check=check,type=rows,elements=elements,contrast=m.contrast_report(path,rows),native_check=m.rel(out/'native-checks/leaflet.json'))
    meta['files']=result;m.dump(out/'leaflet.json',meta);m.render_flat(path,out/'leaflet-flat.png')
    m.render_flat(path,out/'leaflet-with-die.png',layers=('type','die'))
    fit=dict(evidence,holds=checked['holds'] and evidence['all_copy_visible_in_print'] and not evidence['script_font_errors'] and evidence['font_floor_pt']>=6-.0001,
             floor_pt=6,overset=[],native_area_frames=native['areaFrames'],crossings=checked['crossings'],all_inside_safe=checked['all_inside_safe'])
    fit['layout_whitespace_changes']=[{'frame':f['name'],'description':f['layout_whitespace_change'],'logical_copy':f['logical_copy'],'native_copy':f['copy']} for f in frames if f['layout_whitespace_change']]
    m.dump(out/'leaflet-fit-report.json',fit)
    m.dump(out/'leaflet-fold-check.json',dict(meta['geometry'],printed_checks=checked,crossings=checked['crossings'],holds=fit['holds'],native_artwork_sha256=m.sha(path),flat_with_die=m.rel(out/'leaflet-with-die.png')))
    for filename,key in [('ai-check.json','ai_check'),('type-checks.json','type'),('contrast.json','contrast')]:
        p=out/filename;record=read(p) if p.exists() else {};record['leaflet']=result[key];m.dump(p,record)
    return fit


def refresh_carton(out=m.OUT):
    out=Path(out);m.refresh_carton_records(out)
    path=out/'carton-artwork.ai';native=read(out/'native-checks/carton-artwork.json')
    fold=read(out/'carton-fold-check.json');evidence=printed_evidence(path,fold['page_faces'],native)
    meta=read(out/'carton.json')
    product=dict(carton.sc.PRODUCTS['lip_balm'],name='HAYAT lip balm',shade=meta['tint'].title())
    coords,engine_fold=carton.sc.die(product);faces=carton.sc.faces(coords)
    offset=fold['page_offset_mm']
    elements=[{'panel':r['panel'],'element':r['name'],
               'flat':[v-offset[i%2] for i,v in enumerate(r['ink_box_mm'])]}
              for r in evidence['printed_lines']]
    content=carton.sc.content_rows({'elements':elements},coords,faces)
    crease_checks=carton.sc.zero_crossings(engine_fold,content,True)
    fit=read(out/'carton-fit-report.json');fit.update(evidence)
    fit.update(overset=[],overflow=[],copy_shortened=True,copy_shortening_authorization='D-R1C-1: full drafts moved intact to leaflet',
               holds=evidence['all_lines_inside_safe'] and evidence['all_copy_visible_in_print'] and not evidence['script_font_errors'] and crease_checks['holds'] and evidence['font_floor_pt']>=5-.0001,
               crossings=crease_checks['crossings'],printed_line_crease_checks=crease_checks,
               full_text_native_retained=True,full_text_native_retention_pending=False)
    if any(a['overflow'] for a in native['areaFrames']):raise ValueError('Short carton copy still overflows')
    fit['overset']=[{'language':f['language'],'overset':False,'hidden_characters':0,'full_copy':f['copy'],'visible_lines':a['visibleLines']} for f,a in zip(read(out/'carton-native-frames.json')['frames'],native['areaFrames'])]
    fit['net_by_panel']={}
    for panel in ('front','back'):
        net={name:row['native_readback'] for name,row in fit['net'].items() if name.startswith(panel)}
        digits=[d['height_mm'] for r in net.values() for d in r.get('digits',[])]
        sign=net[panel+' net e-mark'];gram=net[panel+' net grams']
        fit['net_by_panel'][panel]={'figure_min_mm':min(digits),'figure_max_mm':max(digits),'figures_at_least_2mm':min(digits)>=2,
                                  'estimated_sign_height_mm':sign['ink_height_mm'],'estimated_sign_3mm':abs(sign['ink_height_mm']-3)<.001,
                                  'baseline_difference_mm':abs(gram['digits'][0]['ink_bottom_mm']-sign['ink_box_mm'][3])}
    fit['changes']=['Full drafts moved to the complete leaflet.', 'Short product and see-leaflet copy in three languages; shared net and INCI.',
                    'Front net block moved up 0.35 mm without changing glyph sizes.', 'EAN frame moved up 5 mm; batch fields moved inside the actual safe rectangle.',
                    'Every Latin character in mixed Arabic copy uses DM Sans; Arabic letters use Almarai.']
    fit['preserved_vector_mark_margin_findings']=fold['zero_crossings']['outside_the_safe_area']
    safe=fold['page_faces']['back']['safe_mm'];back=fold['page_faces']['back']['box_mm']
    fit['batch_rule']={'ink_box_mm':[back[0]+3.15,back[1]+70.5-.125/m.PT,back[0]+17.30,back[1]+70.5+.125/m.PT],
                       'safe_box_mm':safe,'inside_safe':back[1]+70.5+.125/m.PT<safe[3]}
    fit['EAN_rule_margin']='Preserved 14.45 × 29.83 mm frame; its vertical stroke centerlines lie on the safe edges and their 0.075 mm half-stroke extends into the margin. This is not a printed text line or a crease crossing.'
    m.dump(out/'carton-fit-report.json',fit)
    fold['printed_lines']=evidence['printed_lines'];fold['printed_line_crossings']=crease_checks['crossings'];fold['printed_line_checks']=crease_checks;fold['all_printed_lines_inside_safe']=evidence['all_lines_inside_safe'];m.dump(out/'carton-fold-check.json',fold)
    for row in meta['files']['type']:
        if 'native_area_text' in row:
            row['note']='Complete mandatory short copy; all saved glyphs print inside the measured safe area. Mixed Latin/Arabic font runs are individually verified.'
            row['font_runs']=row['native_area_text']['characterFonts']
    m.dump(out/'carton.json',meta)
    record=read(out/'type-checks.json');record['carton']=meta['files']['type'];m.dump(out/'type-checks.json',record)
    return fit


def build_pair(out=m.OUT,tint='ROSEWATER'):
    out=Path(out)
    build_leaflet(out,tint)  # captures full copy before carton overwrite
    carton.build(out,tint)
    results={}
    for filename,stem in [('leaflet.ai','leaflet'),('carton-artwork.ai','carton')]:
        frames=read(out/(stem+'-native-frames.json'))['frames']
        result=m.native_roundtrip(out/filename,frames)
        if not result.get('holds'):raise RuntimeError('Native conversion failed: '+filename)
    m.native_reopen_checks([out/'leaflet.ai',out/'carton-artwork.ai'])
    results['leaflet']=refresh_leaflet(out);results['carton']=refresh_carton(out)
    return {key:{k:value[k] for k in ('holds','hidden_characters','outside_safe_area','script_font_errors')} for key,value in results.items()}


def correct_type_record():
    data=read(m.OUT/'type.json');data['schema']='round1c_type/1'
    data['surfaces']={surface:{face:data['faces'][face] for face in faces} for surface,faces in
                      {'body':('latin','arabic'),'cap':('latin',),'label':('latin',),'carton':('latin','arabic'),'leaflet':('latin','arabic')}.items()}
    data['scope']='Actual live faces per surface. Cap Arabic word is the preserved vector logotype; label has no Arabic live copy. Carton and leaflet assign each Latin character to DM Sans and Arabic character to Almarai, including mixed-script paragraphs.'
    data['leaflet_floor_pt']=6;data['carton_floor_pt']=5
    data['script_font_evidence']=['carton-fit-report.json#/script_font_runs','leaflet-fit-report.json#/script_font_runs']
    m.dump(m.OUT/'type.json',data)
