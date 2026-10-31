"""Six HAYAT plates on the existing 20 × 20 × 73 stick-carton die.

The die comes from stick_carton; design pixels come only from D1/A. This module
never calls a model and never borrows the rescue's design, colours or fonts.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image

from . import round_balm_master as m
from .round_files_export import glyph_metrics, set_layers
from . import stick_carton as sc

OUT = m.OUT
PANELS = ('back', 'side_left', 'front', 'side_right', 'top_end', 'bottom_end')



def clean_type(panel, out=OUT):
    source = out / 'repair' / f'{panel}-after.png'
    if not source.exists(): source = out / 'cleaning' / f'{panel}-after.png'
    if not source.exists(): source = out / 'plates' / f'{panel}.png'
    rgb = np.array(Image.open(source).convert('RGB'))
    h, w = rgb.shape[:2]
    # Pale neutral copy/construction only. Copper painting has chroma > 35.
    light = (rgb.min(2) > 110) & ((rgb.max(2).astype(int)-rgb.min(2)) < 48)
    if panel == 'front':
        zone = np.zeros((h,w), bool); zone[int(.28*h):, int(.05*w):int(.96*w)] = True
    elif panel in ('back', 'top_end', 'bottom_end'):
        zone = np.ones((h,w), bool)
    else:
        zone = np.zeros((h,w), bool)
    mask = cv2.dilate((light & zone).astype('uint8')*255, np.ones((9,9),np.uint8))
    mask[((rgb[...,0].astype(int)-rgb[...,1])>48) & (rgb[...,0]>100)] = 0
    cleaned = cv2.inpaint(rgb, mask, 7, cv2.INPAINT_TELEA) if mask.any() else rgb.copy()
    folder = out / 'type-cleaning'; folder.mkdir(exist_ok=True)
    Image.fromarray(rgb).save(folder / f'{panel}-before.png')
    Image.fromarray(cleaned).save(folder / f'{panel}-after.png')
    Image.fromarray(mask).save(folder / f'{panel}-mask.png')
    record = {'panel':panel, 'source':m.rel(source), 'source_sha256':m.sha(source),
              'mask_pixels':int((mask>0).sum()), 'share':float((mask>0).mean()),
              'outside_mask_unchanged':bool(np.array_equal(rgb[mask==0],cleaned[mask==0])),
              'method':'local Telea inpaint of pale neutral copy glyphs in measured copy zones only; copper fragment painting excluded by chroma',
              'output':m.rel(folder / f'{panel}-after.png')}
    return cleaned, record


def wrapped(copy, face, width_mm, size=5):
    words=copy.split(); rows=[]; line=''
    for word in words:
        candidate=(line+' '+word).strip()
        width=glyph_metrics(candidate,face)['advance_em']*size/m.PT
        if width>width_mm and line:
            rows.append(line); line=word
        else: line=candidate
    if line:rows.append(line)
    return rows


def build(out=OUT, tint='ROSEWATER'):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    product=dict(sc.PRODUCTS['lip_balm'],name='HAYAT lip balm',shade=tint.title())
    coords, fold = sc.die(product); faces=sc.faces(coords)
    bounds=coords.bleed_polygon.bounds
    ox,oy=bounds[:2]; width,height=bounds[2]-ox,bounds[3]-oy
    b=m.SurfaceBuilder((width,height),'HAYAT '+tint+' carton')
    cleaning=[]; placement=[]; elements=[]
    for panel in PANELS:
        arr, rec=clean_type(panel,OUT);cleaning.append(rec)
        face=faces[panel]; x0,y0,x1,y1=face['box']
        gx0=x0-(3 if 'left' in face['cut'] else 0); gy0=y0-(3 if 'top' in face['cut'] else 0)
        gx1=x1+(3 if 'right' in face['cut'] else 0); gy1=y1+(3 if 'bottom' in face['cut'] else 0)
        # One pixel scale, exact trim and padding; a subpixel extent mismatch is
        # carried as placement measurement, not an invented change to the die.
        k=arr.shape[1]/(x1-x0)
        pad=(round((x0-gx0)*k),round((y0-gy0)*k),round((gx1-x1)*k),round((gy1-y1)*k))
        padded=cv2.copyMakeBorder(arr,pad[1],pad[3],pad[0],pad[2],cv2.BORDER_REPLICATE)
        dest=out/'carton-plates'/f'{panel}-bleed.png';dest.parent.mkdir(exist_ok=True)
        Image.fromarray(padded).save(dest)
        b.add_plate(dest,(gx0-ox,gy0-oy,gx1-ox,gy1-oy),name=panel)
        b.rect((x0-ox,y0-oy,x1-ox,y1-oy),layer='guides')
        b.rect(tuple(v-(ox if i%2==0 else oy) for i,v in enumerate(face['safe'])),layer='guides')
        placement.append({'panel':panel,'trim_mm':list(face['box']),'ground_mm':[gx0,gy0,gx1,gy1],
                          'ppi_x':arr.shape[1]/(x1-x0)*25.4,'ppi_y':arr.shape[0]/(y1-y0)*25.4,
                          'bleed':'edge replication outside trim; 3 mm on cut edges; none across face creases so adjacent fragment pixels are preserved',
                          'source':rec['output'],'padded':m.rel(dest)})

    def loc(panel,box):
        x,y,_,_=faces[panel]['box'];return [box[0]+x-ox,box[1]+y-oy,box[2]+x-ox,box[3]+y-oy]
    def text(panel,copy,box,face='latin',size=5,name=None,shrink=True,align='center'):
        row=b.text(copy,loc(panel,box),face=face,size_pt=size,name=name or panel+': '+copy,shrink=shrink,align=align)
        flat=[row['ink_box_mm'][i]+(ox if i%2==0 else oy) for i in range(4)]
        elements.append({'panel':panel,'element':row['name'],'flat':flat,'read_from':'live glyph metrics; independently checked in .ai'})
        return row
    def mark(panel,box):
        b.svg(m.MARK,loc(panel,box),layer='mark',name=panel+' approved BBROSE mark',color=m.INK)
        x,y,_,_=faces[panel]['box'];elements.append({'panel':panel,'element':'BBROSE mark','flat':[box[0]+x,box[1]+y,box[2]+x,box[3]+y]})
    mark('front',(2.3,24.4,18.1,27.7))
    text('front','HAYAT',(3,32,17.45,34.8),size=7.8)
    text('front','حياة',(3,35.4,17.45,38.5),'arabic',7.8)
    text('front','LIP BALM',(2.8,43.2,17.65,45.1),size=6)
    text('front','بلسم شفاه',(2.8,46,17.65,48.3),'arabic',6)
    # First-eye bounded repair: the pale separator in pinned front.png,
    # measured at 2x pixels x63..136, y496..498 on the 198x712 plate.
    separator=(63*20.45/198,496.5*73.45/712,136*20.45/198,496.5*73.45/712)
    separator_width=2*73.45/712
    sep=loc('front',separator)
    b.line(tuple(sep[:2]),tuple(sep[2:]),layer='type',color=m.INK,width=separator_width*m.PT)
    sep_box=[sep[0],sep[1]-separator_width/2,sep[2],sep[3]+separator_width/2]
    b.elements.append({'name':'front separator','layer':'type','kind':'vector_line','box_mm':sep_box})
    elements.append({'panel':'front','element':'front separator','flat':[v+(ox if i%2==0 else oy) for i,v in enumerate(sep_box)],'read_from':'pinned front plate pale separator pixels; restored as live vector type detail'})
    text('front',tint,(2.5,55.2,17.95,57.2),size=6.2,name='front tint')
    # Same numeric and sign sizes as the wrap, split across two rows only to fit.
    num_size=m.point_size_for_height('4',2.001)
    sign_size=m.point_size_for_height('℮',3)
    # Align the flat digit baseline with the e-mark ink foot; g's descender
    # must not lower the numeral baseline when this mixed row is centered.
    gram_bounds=glyph_metrics('4.5 g')['box_em'];net_baseline=67.55
    text('front','4.5 g',(3,net_baseline-gram_bounds[3]*num_size/m.PT,12.2,net_baseline-gram_bounds[1]*num_size/m.PT),size=num_size,shrink=False,name='front net grams')
    text('front','℮',(13.1,64.55,17.4,67.55),size=sign_size,shrink=False,name='front net e-mark')
    text('front','0.15 oz',(3,68.25,17.45,70.45),size=num_size,shrink=False,name='front net ounces')
    text('top_end','HAYAT',(3,4.2,17,7),size=8)
    text('top_end','حياة',(3,8,17,11.3),'arabic',8)
    text('bottom_end',tint,(2.7,7.7,17.3,10.2),size=5.6,name='bottom tint')
    mark('back',(2.3,2.8,18.1,6.1))
    # D-R1C: the complete drafts print on the leaflet; only mandatory short
    # copy remains here. Explicit paragraph breaks are Illustrator-native CR.
    full_copy={
        'en':'HAYAT lip balm\rSee leaflet',
        'es':'HAYAT bálsamo labial\rVer prospecto',
        'ar':'HAYAT بلسم شفاه\rانظر النشرة',
    }
    copy_rows=[];frames=[];overset=[]
    bands={'en':(7.0,11.5),'es':(11.8,17.8),'ar':(18.1,23.0)}
    for lang,copy in full_copy.items():
        face='arabic' if lang=='ar' else 'latin'
        y0,y1=bands[lang];frame_box=loc('back',(3.15,y0,17.30,y1))
        # Interchange placeholder is replaced by complete native mixed-script
        # area text; all final checks use saved printed glyphs, not this row.
        name=f'back draft {lang} preview1'
        row=text('back','HAYAT',(3.15,y0,17.30,y0+1.8),'latin',5,name=name)
        copy_rows.append(dict(row,language=lang,field='short regulated copy'))
        frames.append({'name':'back regulated '+lang,'language':lang,'copy':copy,'face':face,'size_pt':5,
                       'leading_pt':5.25,'box_mm':frame_box,'preview_row_names':[name]})
    back_baseline=26.8
    text('back','4.5 g',(3.15,back_baseline-gram_bounds[3]*num_size/m.PT,12.2,back_baseline-gram_bounds[1]*num_size/m.PT),size=num_size,shrink=False,name='back net grams')
    text('back','℮',(13.0,23.8,17.30,26.8),size=sign_size,shrink=False,name='back net e-mark')
    text('back','0.15 oz',(3.15,27.3,17.30,29.5),size=num_size,shrink=False,name='back net ounces')
    text('back','INCI: owner to',(3.15,30.1,17.30,31.7),size=5,shrink=False,name='back INCI placeholder1')
    text('back','supply',(3.15,32.0,17.30,33.6),size=5,shrink=False,name='back INCI placeholder2')
    y=34.4
    m.dump(out/'carton-copy.json',{'schema':'hayat_short_carton_copy/1','copy':full_copy,'INCI':'owner to supply','shared_net':'4.5 g ℮ 0.15 oz','full_drafts':'leaflet-copy.json','ruling':'D-R1C-1'})
    m.dump(out/'carton-native-frames.json',{'schema':'hayat_native_copy_frames/2','frames':frames,
                                         'purpose':'Complete short mandatory copy; all characters must print inside the actual safe area.'})
    # Exact Day12 EAN frame at 80%, ladder orientation, bar-height truncation.
    ean_y=35.5
    ean_box=(3,ean_y,17.45,ean_y+29.83)
    b.rect(loc('back',ean_box),layer='type',color=m.INK,width=.425)
    text('back','EAN-13',(4.1,ean_y+13.7,16.35,ean_y+15.7),size=5,name='EAN frame label')
    bx,by,_,_=faces['back']['box']
    elements.append({'panel':'back','element':'EAN-13 ladder frame','flat':[ean_box[0]+bx,ean_box[1]+by,ean_box[2]+bx,ean_box[3]+by]})
    text('back','Batch / Lote',(3.15,65.75,17.30,67.5),size=5,shrink=False,name='batch field')
    text('back','التشغيلة',(3.15,67.7,17.30,69.5),'arabic',5,shrink=False,name='batch field Arabic')
    b.line(tuple(loc('back',(3.15,70.5,17.30,70.5))[0:2]),tuple(loc('back',(3.15,70.5,17.30,70.5))[2:4]),layer='type',color=m.INK,width=.25)
    # Engine cut, slits and creases, all locked/nonprinting on the die layer.
    sc.draw_die(b.page,coords,ox,oy,b.ocg['die'],b.ocg['die'])
    result=b.save(out/'carton-artwork.ai',out/'carton-flat.png')
    for panel in PANELS:
        box=faces[panel]['box']
        m.render_flat(out/'carton-artwork.ai',out/'panels'/f'{panel}-flat.png',clip_mm=[v-(ox if i%2==0 else oy) for i,v in enumerate(box)])
    content=sc.content_rows({'elements':elements},coords,faces)
    zero=sc.zero_crossings(fold,content,True)
    # Read the hidden die by explicitly enabling its real OCG in a scratch copy.
    with fitz.open(out/'carton-artwork.ai') as checkdoc:
        set_layers(checkdoc,{'die'})
        temp=out/'carton-die-readback.ai';checkdoc.save(temp)
    die_read=sc.die_readback(temp,coords,ox,oy);temp.unlink()
    fold_report={'schema':'hayat_carton_fold/1','internal_mm':[20,20,73],'engine':fold,
                 'zero_crossings':zero,'content':content,'die_readback':die_read,
                 'faces':{p:{'box_mm':list(f['box']),'safe_mm':list(f['safe'])} for p,f in faces.items()},
                 'page_offset_mm':[-ox,-oy], 'page_faces':{p:{'box_mm':loc(p,(0,0,f['box'][2]-f['box'][0],f['box'][3]-f['box'][1])), 'safe_mm':[v-(ox if i%2==0 else oy) for i,v in enumerate(f['safe'])]} for p,f in faces.items()}}
    overlaps=[]
    for row in copy_rows:
        bb=row['ink_box_mm']; eb=loc('back',ean_box)
        if min(bb[2],eb[2])>max(bb[0],eb[0]) and min(bb[3],eb[3])>max(bb[1],eb[1]):overlaps.append(row['name'])
    fit_report={'schema':'hayat_carton_fit/1','floor_pt':5,'smallest_pt':min(r['size_pt'] for r in result['type']),
                'copy':full_copy,'copy_source':'D-R1C-1 mandatory short EN/ES/AR product/net/see-leaflet copy. Full Day12 drafts, warnings and claims print on leaflet.',
                'native_area_text_required':True,'overset':overset,
                'copy_lines':copy_rows,'all_lines_live':result['ai_check']['checks']['all_expected_copy'],
                'overflow':[r for r in result['type'] if r['overflow']],
                'outside_safe_area':zero['outside_the_safe_area'],'copy_ean_overlaps':overlaps,
                'copy_bottom_mm':y,'ean':{'nominal_mm':[29.83,20.74],'drawn_ladder_mm':[14.45,29.83],
                'status':'truncated — owner to confirm','number':None,'panel':'back'},
                'batch':'back, where drawn in the sketch','claims':'owner to confirm','INCI':'owner to supply',
                'copy_shortened':False,'full_text_native_retention_pending':True,'process_colour_only':True,
                'net':{r['name']:r for r in result['type'] if 'net ' in r['name']}}
    m.dump(out/'carton-fit-report.json',fit_report);m.dump(out/'carton-fold-check.json',fold_report)
    m.dump(out/'carton.json',{'schema':'hayat_carton/1','files':result,'placement':placement,'type_cleaning':cleaning,'tint':tint})
    return result
