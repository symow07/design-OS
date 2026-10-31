"""Preservation master stages. Product geometry and copy come only from frozen inputs."""
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import shutil
import unicodedata
import zipfile

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw

from . import round_flow as flow
from . import round_product as product
from . import lid_master as metrics
from .round_files_faces import delta_e00, srgb_to_lab
from . import round_master_files as files
from .round_calls import sha

BLEED = 3.0
CANVAS = (1536, 1024)
MARK = flow.REPO / 'bbrose_design_os/docs/brand/mark/bbrose-logo.svg'
ARABIC = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufeff]')


def read(path):
    return json.loads(Path(path).read_text())


def pinned(path, expected):
    if sha(path) != expected:
        raise ValueError('A pinned master input changed: ' + str(path))
    return Path(path)


def input_snapshot(record):
    from .round_master_flow import digest
    if record.pick.get('merge'):
        raise ValueError('This pick has a merge instruction; its preserved fragment must be mapped before a master can start.')
    source = flow.round_root(record)
    ident = record.pick['id']
    if not re.fullmatch(r'[A-Z][0-9]+(?:/[AB])?', ident):
        raise ValueError('Invalid picked artwork identity')
    folder = source / ('developments/' if '/' in ident else 'sketches/') / ident
    picture, crop, sheet = folder / 'picture.png', folder / 'crop.json', source / 'sheet.json'
    # Existing publication, not a fresh digest, binds the owner's actual picked design.
    from apps.dashboard.product_round_views import publication
    published=publication(record)
    relative=str(picture.relative_to(source))
    if relative not in published['files']:
        raise ValueError('The picked image is not in the owner publication')
    pinned(picture,published['files'][relative])
    for path in (crop,sheet):
        relpath=str(path.relative_to(source))
        if relpath in published['files']:pinned(path,published['files'][relpath])
    brief = deepcopy(record.product_brief)
    classification = 'owner intake COPY/INSTRUCTION roles'
    if not product.typed_content(brief):
        roles = {key: product.DEFAULT_COPY_ROLES[key] if key in product.DEFAULT_COPY_ROLES else 'INSTRUCTION'
                 for key in brief['copy']}
        brief = product.classify_intake(brief, roles)
        classification = 'Explicit day-two snapshot of legacy fields using the established COPY/INSTRUCTION contract; original unchanged.'
    panels, _ = product.engine_panels(brief)
    if any(p['id'] in ('carton','leaflet') for p in panels):
        raise ValueError('Panel names carton and leaflet are reserved for assembled files; use a face name.')
    geometry = read(sheet)
    crops = read(crop)['panels']
    if set(crops) != {p['id'] for p in panels} or set(geometry['panels']) != set(crops):
        raise ValueError('Pick, brief and engine must name exactly the same panels')
    for panel in panels:
        key = panel['id']
        expected = [panel['width_mm'], panel['height_mm']]
        if any(abs(a-b) > .000001 for a,b in zip(expected, crops[key]['mm'])):
            raise ValueError('The picked panel proportions differ from the engine: ' + key)
    approval = read(MARK.parent / 'approval.json')
    pinned(MARK, approval['master_sha256'])
    return {'schema': 'round_master_inputs/1', 'pick': deepcopy(record.pick), 'brief': brief,
        'original_brief_sha256': digest(record.product_brief), 'classification': classification,
        'copy': product.printed_copy(brief), 'panels': panels,
        'source': str(folder.relative_to(source)), 'picture_sha256': sha(picture),
        'crop_sha256': sha(crop), 'sheet_sha256': sha(sheet), 'mark_sha256': sha(MARK),
        'preservation': 'Picked sketch is the design; only listed media, type, print and material differences.',
        'budget_usd': 15}


def panels(ctx):
    from apps.ire import font_pool
    inputs = ctx.build.inputs
    source = flow.round_root(ctx.round)
    folder = source / inputs['source']
    sheet = read(pinned(source / 'sheet.json', inputs['sheet_sha256']))
    crop = read(pinned(folder / 'crop.json', inputs['crop_sha256']))
    picture = pinned(folder / 'picture.png', inputs['picture_sha256'])
    shutil.copyfile(picture, ctx.root / 'sketch.png')
    granted = font_pool.files_of('granted')
    fonts = {}
    for script, path in files.FONT_PATHS.items():
        digest = sha(path)
        if digest not in granted:
            raise ValueError('Master font is outside the GRANTED pool: ' + script)
        fonts[script] = {'path': str(path), 'sha256': digest, 'grant': granted[digest]}
    flow.write_json(ctx.root / 'inputs.json', inputs)
    flow.write_json(ctx.root / 'fonts.json', fonts)
    result = []
    with Image.open(picture) as image:
        for definition in inputs['panels']:
            key = definition['id']
            box = crop['panels'][key]['box_px']
            panel = image.convert('RGB').crop(box)
            dest = ctx.root / 'panels' / key
            dest.mkdir(parents=True, exist_ok=True)
            panel.save(dest / 'sketch.png')
            # Preserve the exact old source pixels; placement millimetres never follow pixel rounding.
            with Image.open(pinned(folder / crop['panels'][key]['file'], crop['panels'][key]['sha256'])) as old:
                if not np.array_equal(np.asarray(panel), np.asarray(old.convert('RGB'))):
                    raise ValueError('Source crop does not match the picked sheet: ' + key)
            up = cv2.resize(np.asarray(panel), None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
            Image.fromarray(up).save(dest / 'upscale.png')
            record = dict(definition, source_box_px=box, source_px=list(panel.size),
                source_sha256=sha(dest / 'sketch.png'), upscale_sha256=sha(dest / 'upscale.png'),
                sheet=sheet['panels'][key], exact_mm=[definition['width_mm'], definition['height_mm']],
                source_ppi=min(panel.width/definition['width_mm'], panel.height/definition['height_mm'])*25.4)
            flow.write_json(dest / 'panel.json', record)
            result.append(record)
    return {'panels': result, 'fonts': fonts, 'source_unchanged': sha(picture) == inputs['picture_sha256']}


def panel_records(ctx):
    records=[read(ctx.root/'panels'/p['id']/'panel.json') for p in ctx.build.inputs['panels']]
    for row in records:
        folder=ctx.root/'panels'/row['id']
        pinned(folder/'sketch.png',row['source_sha256']);pinned(folder/'upscale.png',row['upscale_sha256'])
    saved=ctx.build.steps['panels']['result']
    if saved and saved['panels']!=records:raise ValueError('Recorded panel geometry or source pins changed')
    return records


def canvas(source, mask_source=None):
    source = source.convert('RGB')
    scale = min((CANVAS[0]-32)/source.width, (CANVAS[1]-32)/source.height)
    size = (max(1, round(source.width*scale)), max(1, round(source.height*scale)))
    x, y = (CANVAS[0]-size[0])//2, (CANVAS[1]-size[1])//2
    box = (x,y,x+size[0],y+size[1])
    image = Image.new('RGB', CANVAS, 'white')
    image.paste(source.resize(size, Image.Resampling.LANCZOS), (x,y))
    mask = Image.new('RGBA', CANVAS, (255,255,255,255))
    if mask_source is None:
        mask.paste((255,255,255,0), box)
    else:
        alpha = Image.new('L', CANVAS, 255)
        local = mask_source.convert('L').resize(size, Image.Resampling.NEAREST)
        alpha.paste(Image.fromarray(255-np.asarray(local)), (x,y))
        mask.putalpha(alpha)
    return image, mask, list(box)


def fidelity(reference, candidate):
    original = np.asarray(reference.convert('RGB'))
    compare = np.asarray(candidate.convert('RGB').resize(reference.size, Image.Resampling.LANCZOS))
    delta = delta_e00(srgb_to_lab(original), srgb_to_lab(compare))
    mean = float(delta.mean())
    similarity = metrics.ssim(metrics.luma(original), metrics.luma(compare))
    return {'de00_mean': mean, 'ssim': similarity, 'accepted': bool(mean <= 1.5 and similarity >= .97),
            'comparison': 'candidate downsampled to original crop; before authorized type/material differences',
            'thresholds': {'de00_mean_max': 1.5, 'ssim_min': .97}}


def detail(ctx):
    rows = []
    for panel in panel_records(ctx):
        folder = ctx.root / 'panels' / panel['id']
        checkpoint = folder / 'detail.json'
        if checkpoint.exists():
            result = read(checkpoint)
            pinned(folder / result['selected'], result['selected_sha256'])
            rows.append(result)
            continue
        source = Image.open(folder / 'sketch.png').convert('RGB')
        image, mask, box = canvas(source)
        image.save(folder / 'detail-input.png'); mask.save(folder / 'detail-mask.png')
        ctx.masked_edit('detail/' + panel['id'],
            'Preservation detail pass of the single supplied flat panel crop. Only remake fine detail inside the '
            'transparent mask at this full resolution. EXACT composition, colours, every texture and diagonal, '
            'type positions, proportions and existing material. No new elements, words, lighting, scene or mockup. '
            'Do not change outside the mask. This is the picked design, never redesign it.',
            folder / 'detail-call', target=folder/'detail-input.png', mask=folder/'detail-mask.png')
        candidate = Image.open(folder / 'detail-call/raw.png').convert('RGB').crop(box)
        candidate.save(folder / 'detail-candidate.png')
        result = fidelity(source, candidate)
        selected = 'detail-candidate.png' if result['accepted'] else 'upscale.png'
        result.update(panel=panel['id'], selected=selected, selected_sha256=sha(folder/selected),
                      source_sha256=panel['source_sha256'], full_canvas_box_px=box,
                      rejection='Retained exact 2× upscale' if not result['accepted'] else '')
        flow.write_json(checkpoint, result)
        rows.append(result)
    return {'panels': rows}


def valid_box(box):
    return (isinstance(box, list) and len(box)==4 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)


def validate_layout(payload, ids, copy):
    if not isinstance(payload, dict) or set(payload) != {'panels'} or not isinstance(payload['panels'],dict) or set(payload['panels']) != set(ids):
        raise ValueError('Layout must name every supplied panel exactly once')
    for key, panel in payload['panels'].items():
        if not isinstance(panel,dict) or set(panel) != {'text','erase','marks','geometry','notes'} or any(not isinstance(panel[k],list) for k in ('text','erase','marks','geometry')):
            raise ValueError('Layout requires text, erase, marks, geometry and notes')
        for box in panel['erase']:
            if not valid_box(box): raise ValueError('Invalid lettering removal box')
        for row in panel['text']:
            if (not isinstance(row,dict) or set(row) != {'field','text','box','color'} or row['field'] not in copy or not isinstance(row['text'],str) or not row['text'].strip()
                    or row['text'] not in copy[row['field']] or not valid_box(row['box'])
                    or not product.HEX.fullmatch(row['color'])):
                raise ValueError('Printed words must be literal COPY substrings in measured boxes')
        for row in panel['marks']:
            if (set(row) != {'kind','box','rotation','color'} or row['kind'] not in ('logo','emblem')
                    or not valid_box(row['box']) or row['rotation'] not in (0,90,180,270)
                    or not product.HEX.fullmatch(row['color'])):
                raise ValueError('Invalid approved mark placement')
        for row in panel['geometry']:
            if (set(row) != {'points','width_mm','color','closed'} or not 2 <= len(row['points']) <= 64
                    or not .02 <= row['width_mm'] <= 3 or not product.HEX.fullmatch(row['color'])
                    or any(len(p)!=2 or any(not isinstance(v,(int,float)) or not 0<=v<=1 for v in p) for p in row['points'])):
                raise ValueError('Invalid measured vector geometry')
    return payload


def objects(ctx):
    result = {}
    for panel in ctx.build.inputs['panels']:
        kind = 'carton' if panel.get('engine_face') else 'cap' if panel['surface']=='gold_metal' else 'body'
        result.setdefault(kind, []).append(panel['id'])
    return result


def layout(ctx):
    combined = {}
    allowed = ctx.build.inputs['copy']
    for kind, ids in objects(ctx).items():
        dest = ctx.root / 'layout' / (kind + '-call.json')
        prompt = ('Measure the visible picked flat artwork for preservation. Return JSON only: '
            '{"panels": {panel_id: {"text":[{"field":"copy.product","text":"literal substring",'
            '"box":[left,top,right,bottom],"color":"#RRGGBB"}],"erase":[[left,top,right,bottom]],'
            '"marks":[{"kind":"logo or emblem","box":[left,top,right,bottom],"rotation":0,"color":"#RRGGBB"}],'
            '"geometry":[{"points":[[x,y],[x,y]],"width_mm":0.1,"color":"#RRGGBB","closed":false}],"notes":"..."}}}. '
            'All coordinates normalized 0..1 within EACH crop, excluding no edges. Measure exact original ink boxes. '
            'Every word, logo, emblem, simple diagonal/line/star must leave the raster: erase boxes list ALL word/logo '
            'areas INCLUDING accidentally printed instructions. Geometry identifies only the actual line geometry, '
            'never frost/grain/pictures. Preserve positions, scale, colour. One text item per visible line. '
            'Every text must be an EXACT case-sensitive substring of its COPY field; reconstruct misspellings using '
            'that field at the original position. Do not invent absent words, marks or cap engraving. '
            'COPY values are the sole source of printed words; INSTRUCTION text is erased and never typeset. '
            'Brand is the approved logo vector (kind logo); a separate round house sign is kind emblem. '
            'Blank gold material carries empty lists. On clear acrylic the frost becomes white/frost print and '
            'diagonals rose-gold vectors on clear; material is not a pink ink rectangle. '
            'Panel dimensions: ' + json.dumps({p['id']:p['exact_mm'] for p in panel_records(ctx) if p['id'] in ids}) +
            '\nCOPY only: ' + json.dumps(allowed, ensure_ascii=False))
        result = ctx.text_call('check/layout-' + kind, prompt, dest,
            images=[(key, ctx.root/'panels'/key/'sketch.png') for key in ids], ceiling=1.5)
        try:
            validated = validate_layout(result['payload'], ids, allowed)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            ctx.reject_result(dest, str(exc)); raise
        combined.update(validated['panels'])
    required=[key for key in ('copy.product','copy.net','copy.back_en','copy.back_es','copy.back_ar','copy.batch') if key in allowed]
    for field in required:
        # A spaced slash separates language/line alternatives in COPY. It need
        # not become ink when the picked design places those words on separate
        # lines. Punctuation within a value (e.g. A/B) remains required.
        literal=re.sub(r'(?<=\s)/(?=\s)', '', allowed[field])
        expected=Counter(c for c in unicodedata.normalize('NFKC',literal) if not c.isspace())
        actual=Counter(c for panel in combined.values() for row in panel['text'] if row['field']==field for c in unicodedata.normalize('NFKC',row['text']) if not c.isspace())
        if expected-actual:
            ctx.reject_result(ctx.root/'layout'/('carton-call.json' if 'carton' in objects(ctx) else 'body-call.json'), 'Required COPY missing: '+field)
            raise ValueError('Required COPY missing from measured layout: '+field)
    flow.write_json(ctx.root / 'layout.json', combined)
    return {'panels': list(combined), 'source': 'Measured from the picked panels; COPY-only text validation'}


def box_pixels(box, size):
    return [round(v * size[i%2]) for i,v in enumerate(box)]


def removal_mask(plan, size):
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    for box in plan['erase'] + [row['box'] for row in plan['marks']] + [row['box'] for row in plan['text']]:
        x0,y0,x1,y1 = box_pixels(box,size)
        draw.rectangle((max(0,x0-2),max(0,y0-2),min(size[0]-1,x1+2),min(size[1]-1,y1+2)),fill=255)
    return mask


def clear_separation(image, panel):
    """White ink coverage over the declared liquid; no liquid-coloured process plate."""
    rgb = np.asarray(image.convert('RGB'), dtype=float)
    shade = np.array([int(panel['liquid'][i:i+2],16) for i in (1,3,5)], dtype=float)
    white = 255 - shade
    alpha = np.clip(((rgb-shade)*white).sum(2)/(white@white),0,1)
    box, printed = panel['sheet']['box_px'], panel['sheet'].get('printable_box_px')
    keep = np.zeros(alpha.shape,dtype=bool)
    if printed is not None:
        x0=round((printed[0]-box[0])/(box[2]-box[0])*image.width)
        y0=round((printed[1]-box[1])/(box[3]-box[1])*image.height)
        x1=round((printed[2]-box[0])/(box[2]-box[0])*image.width)
        y1=round((printed[3]-box[1])/(box[3]-box[1])*image.height)
        keep[y0:y1,x0:x1]=True
    alpha[~keep]=0
    rgba=np.full((*alpha.shape,4),255,dtype=np.uint8)
    rgba[...,3]=np.round(alpha*255).astype(np.uint8)
    return Image.fromarray(rgba), {'substrate':'clear acrylic', 'printed_inks':['white/frost','rose-gold'],
        'liquid_is_printed':False, 'clear_pixel_share':float((alpha<.02)[keep].mean()) if keep.any() else 1.,
        'mean_frost_coverage':float(alpha[keep].mean()) if keep.any() else 0.,
        'method':'White/frost optical coverage relative to declared liquid; confined to engine print window. Eye reviews approximation.'}


def plates(ctx):
    plans=read(ctx.root/'layout.json'); result=[]
    for panel in panel_records(ctx):
        key=panel['id']; folder=ctx.root/'panels'/key; checkpoint=folder/'plate.json'
        if checkpoint.exists():
            value=read(checkpoint); pinned(folder/'plate.png',value['sha256']); result.append(value); continue
        plan=plans[key]; chosen=read(folder/'detail.json')['selected']
        original=Image.open(folder/chosen).convert('RGB'); mask=removal_mask(plan,original.size)
        if mask.getbbox() and panel['surface']!='gold_metal':
            image, edit_mask, box=canvas(original, mask)
            image.save(folder/'clean-input.png');edit_mask.save(folder/'clean-mask.png')
            ctx.masked_edit('clean/'+key,
                'Remove ONLY all lettering and logos inside the mask, continuing their immediate existing background '
                'texture seamlessly. Also remove accidentally printed instructions. No new words, symbols, changes '
                'of palette/composition or invented texture. Flat print artwork from this exact picked crop. '
                'Pixels outside the supplied mask must stay exactly unchanged. No scene or mockup.',
                folder/'clean-call',target=folder/'clean-input.png',mask=folder/'clean-mask.png')
            raw=Image.open(folder/'clean-call/raw.png').convert('RGB').crop(box).resize(original.size,Image.Resampling.LANCZOS)
            clean=Image.composite(raw,original,mask)
        else:
            clean=original.copy()
        mask.save(folder/'removal-mask.png');clean.save(folder/'clean.png')
        if panel['surface']=='clear_acrylic':
            panel['liquid']=ctx.brief['shades'][0]['hex']
            plate, material=clear_separation(clean,panel)
            difference='Frost is white/frost ink and diagonals rose-gold on clear acrylic; liquid colour is visible through open print, never pink fill.'
        elif panel['surface']=='gold_metal':
            plate=Image.new('RGBA',clean.size,(0,0,0,0))
            material={'substrate':'gold metal','raster_print':False,'marks':'engraving or foil vectors only'}
            difference='Gold is the physical cap, not a printed raster; only picked marks may be engraving or foil.'
        else:
            plate=clean.convert('RGBA'); material={'substrate':panel['surface'],'preserved_picture':True}
            difference='Printed words/logo removed locally and rebuilt as live COPY type/approved vector; die from engine.'
        plate.save(folder/'plate.png')
        # All local material/type operations are listed after the independent detail measurement.
        record={'panel':key,'sha256':sha(folder/'plate.png'),'material':material,
                'allowed_differences':[difference], 'removed_boxes':plan['erase'],
                'outside_removal_mask_unchanged':bool(np.array_equal(np.asarray(clean)[np.asarray(mask)==0],np.asarray(original)[np.asarray(mask)==0]))}
        flow.write_json(checkpoint,record);result.append(record)
    flow.write_json(ctx.root/'allowed-differences.json',result)
    return {'panels':result}


def script_runs(text):
    """Keep Arabic words joined across spaces; only actual Latin runs change font."""
    result=[]
    for index,ch in enumerate(text):
        if ch.isspace():
            following=next((c for c in text[index+1:] if not c.isspace()), '')
            script=result[-1][0] if result else ('arabic' if ARABIC.fullmatch(following) else 'latin')
        else:
            script='arabic' if ARABIC.fullmatch(ch) else 'estimated' if ch=='℮' else 'latin'
        if result and result[-1][0]==script:
            result[-1]=(script,result[-1][1]+ch)
        else:result.append((script,ch))
    return result


def add_copy(surface, row, box, *, small_body=False, floor=5, fixed_size=None):
    text=row['text']; runs=script_runs(text); sizes=[]
    for script,words in runs:
        face='arabic' if script=='arabic' else 'latin'
        metric=files.glyph_metrics(words,face)
        if metric['missing']:raise ValueError('Granted face lacks printed glyphs: '+repr(metric['missing']))
        height=metric['box_em'][3]-metric['box_em'][1]
        size=fixed_size if fixed_size is not None else max(floor,(box[3]-box[1])*files.PT/max(height,.5))
        if small_body and words.strip():
            cap=files.glyph_metrics('ا' if face=='arabic' else 'H',face)['box_em'][3]
            size=max(size,2.5*files.PT/cap)
        if script=='estimated':size=3*files.PT/height
        sizes.append((face,words,size,metric['advance_em']*size/files.PT))
    total=sum(run[3] for run in sizes); x=(box[0]+box[2]-total)/2
    if any(script=='arabic' for script,_ in runs) and not re.search('[A-Za-z]',text):sizes=list(reversed(sizes))
    for face,words,size,width in sizes:
        if not words.strip():x+=width;continue
        target=[x,box[1],x+max(width,.01),box[3]]
        emitted=surface.text(words,target,face=face,size_pt=size,color=row['color'],shrink=False,
                             name=row['field']+':'+str(len(surface.rows)))
        emitted.update(copy_field=row['field'],sketch_box_mm=box,small_body=small_body,
                       estimated_sign='℮' in words,intended_floor_pt=floor)
        x+=width


def approved_emblem(folder):
    """Crop only the emblem subpath from the approved master; never retrace it."""
    import xml.etree.ElementTree as ET
    root=ET.fromstring(MARK.read_bytes())
    paths=[node for node in root.iter() if node.tag.endswith('path')]
    # The approved asset's first subpath is the house emblem (lid_master.LOGO_PARTS).
    target=paths[0]
    for parent in root.iter():
        for node in list(parent):
            if node.tag.endswith('path') and node is not target: parent.remove(node)
    # Get its bounds by parsing the unchanged path in the approved coordinate system.
    metrics.logo_paths()  # verifies the approved source digest before extracting a subpath
    # SVG rendering preserves path transforms; its intrinsic bounds are measured from the vector page.
    source=ET.tostring(root)
    with fitz.open(stream=source,filetype='svg') as svg:
        with fitz.open(stream=svg.convert_to_pdf(),filetype='pdf') as pdf:
            boxes=[d['rect'] for d in pdf[0].get_drawings() if d['fill'] is not None]
            box=fitz.Rect(boxes[0])
            for b in boxes[1:]:box|=b
            view=[float(v) for v in root.attrib['viewBox'].split()]
            sx=view[2]/pdf[0].rect.width;sy=view[3]/pdf[0].rect.height
            root.set('viewBox',f'{view[0]+box.x0*sx} {view[1]+box.y0*sy} {box.width*sx} {box.height*sy}')
            root.set('width',str(box.width*sx));root.set('height',str(box.height*sy))
    dest=folder/'approved-emblem.svg';dest.write_bytes(ET.tostring(root));return dest


def geometry_mask(plan, panel, size):
    mask=Image.new('L',size,0);draw=ImageDraw.Draw(mask)
    for item in plan['geometry']:
        points=[(round(p[0]*size[0]),round(p[1]*size[1])) for p in item['points']]
        if item['closed']:points.append(points[0])
        width=max(1,round(item['width_mm']*size[0]/panel['width_mm']))+2
        draw.line(points,fill=255,width=width)
    return mask


def compose(surface, ctx, panel, offset, *, bleed=True, separation=None):
    if separation not in (None,'white-frost','rose-gold') or (separation and panel['surface']!='clear_acrylic'):
        raise ValueError('Ink separations apply only to clear acrylic')
    key=panel['id'];folder=ctx.root/'panels'/key;plan=read(ctx.root/'layout.json')[key]
    width,height=panel['exact_mm'];ox,oy=offset
    plate=Image.open(folder/'plate.png').convert('RGBA')
    # Geometry is moved into a vector finish layer; the local raster strokes are removed.
    gm=geometry_mask(plan,panel,plate.size)
    if gm.getbbox() and panel['surface']!='gold_metal':
        data=np.asarray(plate).copy();mask=np.asarray(gm)
        if panel['surface']=='clear_acrylic':
            data[...,3][mask>0]=0
        else:
            data[...,:3]=cv2.inpaint(data[...,:3],mask,3,cv2.INPAINT_TELEA)
        plate=Image.fromarray(data)
        gm.save(folder/'geometry-removal-mask.png')
        flow.write_json(folder/'geometry-removal.json',{'source_sha256':sha(folder/'plate.png'),'changed_pixels':int((np.asarray(gm)>0).sum()),'reason':'Picked geometric strokes rebuilt as vectors; only their recorded mask changes.'})
    if separation=='white-frost':
        # Positive monochrome plate: black means ink, white means no ink.
        # Derive from the SAME geometry-cleared alpha as the visual master.
        plate=Image.fromarray(255-np.asarray(plate)[...,3])
    if panel['surface']!='gold_metal' and separation!='rose-gold':
        if bleed:
            left,top,right,bottom=(BLEED,)*4 if bleed is True else bleed
            lp,rp=[round(v*plate.width/width) for v in (left,right)]
            tp,bp=[round(v*plate.height/height) for v in (top,bottom)]
            pixels=np.asarray(plate)
            arr=np.pad(pixels,((tp,bp),(lp,rp))+((0,0),)*(pixels.ndim-2),mode='edge')
            drawn=folder/((separation+'-' if separation else '')+'print-bleed.png');Image.fromarray(arr).save(drawn)
            surface.add_plate(drawn,[ox-left,oy-top,ox+width+right,oy+height+bottom],key+' picture')
        else:
            drawn=folder/((separation+'-' if separation else '')+'print.png');plate.save(drawn)
            surface.add_plate(drawn,[ox,oy,ox+width,oy+height],key+' picture')
    if separation=='white-frost':return surface
    def mm_box(box):return [ox+box[0]*width,oy+box[1]*height,ox+box[2]*width,oy+box[3]*height]
    for row in plan['text']:
        inkrow=dict(row,color='#C9977F') if panel['surface']=='clear_acrylic' else row
        if separation=='rose-gold':inkrow=dict(inkrow,color='#000000')
        add_copy(surface,inkrow,mm_box(row['box']),small_body=panel['surface'] in ('clear_acrylic','gold_metal') and width<=20)
    for item in plan['marks']:
        mark=MARK if item['kind']=='logo' else approved_emblem(folder)
        surface.svg(mark,mm_box(item['box']),layer='finish' if panel['surface']=='gold_metal' else 'mark',
                    name=key+' '+item['kind'],color='#000000' if separation else '#C9977F' if panel['surface']=='clear_acrylic' else item['color'],rotate=item['rotation'])
    for item in plan['geometry']:
        pts=[(ox+p[0]*width,oy+p[1]*height) for p in item['points']]
        if item['closed']:pts.append(pts[0])
        color='#C9977F' if panel['surface']=='clear_acrylic' else item['color']
        if separation=='rose-gold':color='#000000'
        for a,b in zip(pts,pts[1:]):surface.line(a,b,layer='finish',color=color,width=item['width_mm']*files.PT)
    return surface


def measured_file(path, rows, elements, *, safe=None):
    record=files.read_back_ai(path,elements,rows)
    measured=files.measure_native_lines(path,rows)
    with fitz.open(path) as doc:
        # Read final glyph operators; source/preview boxes never establish a safe-area pass.
        spans=doc[0].get_texttrace()
        printed=[]
        for span in spans:
            for code,gid,origin,box in span['chars']:
                if not chr(code).isspace(): printed.append(chr(code))
        bounds=[{'text':''.join(chr(c[0]) for c in span['chars']),
                 'font':span['font'],'size_pt':span['size'],
                 'box_mm':[v/files.PT for v in span['bbox']],
                 'latin_in_arabic_face':bool(re.search('[A-Za-z]', ''.join(chr(c[0]) for c in span['chars'])) and 'almarai' in span['font'].lower())}
                for span in spans]
    normalize=lambda text:Counter(c for c in unicodedata.normalize('NFKC',text) if not c.isspace())
    expected=normalize(''.join(row['copy'] for row in rows));actual=normalize(''.join(printed))
    # PDF extraction can report shaped Arabic in visual order; character identity still must be exact.
    missing=expected-actual;extra=actual-expected
    findings={'printed_character_inventory':{'missing':dict(missing),'extra':dict(extra),'complete':not missing and not extra},
              'glyph_measurements':measured,'printed_spans':bounds,
              'nothing_under_5pt':all(span['size_pt']>=5-.001 for span in bounds),
              'latin_uses_latin_face':not any(span['latin_in_arabic_face'] for span in bounds),
              'safe_area':{'checked':safe is not None,'outside':[]},
              'contrast':files.legacy.contrast_report(path,rows),
              'report_only':'Measurements do not replace the designer’s eye.'}
    if safe is not None:
        actual_bounds=[{'name':m['name'],'box_mm':m['ink_box_mm'],'kind':'live_type'} for m in measured if m['measured']]
        actual_bounds += [{'name':e['name'],'box_mm':e['box_mm'],'kind':e['kind']} for e in elements if e['kind']=='vector']
        findings['safe_area']['unmeasured_lines']=[m for m in measured if not m['measured']]
        findings['safe_area']['outside']=[span for span in actual_bounds if not any(
            span['box_mm'][0]>=b[0]-.001 and span['box_mm'][1]>=b[1]-.001 and
            span['box_mm'][2]<=b[2]+.001 and span['box_mm'][3]<=b[3]+.001 for b in safe)]
    findings['cap_height_reports']=[{'name':row['name'],'required_mm':2.5,'measured':m}
        for row,m in zip(rows,measured) if row.get('small_body')]
    findings['estimated_sign_reports']=[{'name':row['name'],'required_mm':3,'measured':m}
        for row,m in zip(rows,measured) if row.get('estimated_sign')]
    record['measurements']=findings
    if not findings['nothing_under_5pt'] or not findings['latin_uses_latin_face'] or missing or extra:
        raise ValueError('Saved master lost copy, changed script fonts or printed type below 5 pt')
    if not record['checks']['all_expected_elements']:raise ValueError('Saved master lost an expected picture, mark or text element')
    if not all(r['embedded'] for r in record['fonts']):raise ValueError('Saved master contains an unembedded font')
    if set(r['name'] for r in record['layers'])!=set(files.LAYERS):raise ValueError('Saved master lost a layer')
    if not record['checks']['die_guides_locked_nonprinting']:raise ValueError('Die and guide locks were lost')
    return record


def native_save(ctx, surface, key, *, safe=None):
    folder=ctx.root/'files';folder.mkdir(exist_ok=True)
    path=folder/(key+'.ai')
    compat=surface.save(path)
    census=files.native_roundtrip(path)
    if not census['holds']:raise ValueError('Illustrator save did not preserve '+key+'; native evidence retained')
    reopened=files.native_reopen_checks([path])
    if not all(row['holds'] for row in reopened):raise ValueError('Illustrator reopen failed for '+key)
    report=measured_file(path,compat['type'],compat['elements'],safe=safe)
    report['native']=reopened[0]
    report['file']=key+'.ai';report['sha256']=sha(path);report['rows']=compat['type']
    with fitz.open(path) as document:trim=[v/files.PT for v in document[0].trimbox]
    files.render_flat(path,folder/(key+'.png'),clip_mm=trim)
    report['png_sha256']=sha(folder/(key+'.png'))
    flow.write_json(folder/(key+'.json'),report)
    return report


def proof_clear(ctx,panel):
    folder=ctx.root/'panels'/panel['id']; path=ctx.root/'files'/(panel['id']+'.ai')
    with fitz.open(path) as doc:
        files.set_layers(doc,{'plate','type','mark','finish'})
        # Reparse after optional-content changes; render transparency from the saved master.
        with fitz.open(stream=doc.tobytes(),filetype='pdf') as fresh:
            pix=fresh[0].get_pixmap(dpi=300,clip=fresh[0].trimbox,alpha=True)
            rgba=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4).copy()
            alpha=rgba[...,3:4].astype(float)
            rgba[...,:3]=np.minimum(255,np.divide(rgba[...,:3].astype(float)*255,alpha,out=np.zeros_like(rgba[...,:3],dtype=float),where=alpha>0)).round().astype(np.uint8)
            layer=Image.fromarray(rgba)
    proofs=[]
    for index,shade in enumerate(ctx.brief['shades']):
        background=Image.new('RGBA',layer.size,shade['hex']);background.alpha_composite(layer)
        target=folder/('clear-proof-'+str(index)+'.png');background.convert('RGB').save(target,dpi=(300,300))
        proofs.append({'shade':shade['name'],'hex':shade['hex'],'file':str(target.relative_to(ctx.root)),
                       'sha256':sha(target),'liquid_only_in_proof':True})
    return proofs


def leaflet(ctx):
    from .balm_leaflet import layout as leaflet_layout
    # The folding engine consumes dimensions, never a product-name dispatch.
    carton=ctx.brief.get('carton')
    if carton is None:
        dims=[max(25,min(p['width_mm'] for p in ctx.build.inputs['panels'])),20,
              max(50,max(p['height_mm'] for p in ctx.build.inputs['panels']))]
    else:dims=carton['inside_mm']
    geom=leaflet_layout(dims)
    w,h=geom['sheet_mm'];s=files.Surface([w+6,h+6],ctx.brief['name']+' leaflet',[3,3,w+3,h+3])
    copy=ctx.build.inputs['copy'];used=[];missing=[]
    # Full supplied drafts belong here. Never invent warnings/INCI/claims from instructions.
    for lang in ('en','es','ar'):
        keys=[key for key in copy if key.endswith('_'+lang) and ('leaflet' in key or 'warning' in key or 'regulated' in key)]
        if not keys:
            keys=[key for key in copy if key=='copy.back_'+lang]
            missing.append(lang+': no full leaflet draft supplied; only literal available copy retained')
        content='\n'.join(copy[key] for key in keys)
        if not content:continue
        from .round_balm_carton import wrapped
        face='arabic' if lang=='ar' else 'latin'
        panels=[next(p for p in geom['panels'] if p['id']==pid) for pid in geom['reading_order'][lang]]
        width=panels[0]['safe_mm'][2]-panels[0]['safe_mm'][0]
        lines=[]
        for key in keys:
            for paragraph in copy[key].splitlines():
                lines.extend((key,line) for line in wrapped(paragraph,face,width,size=6))
        capacity=math.floor((panels[0]['safe_mm'][3]-panels[0]['safe_mm'][1])/(6*1.3/files.PT))
        if len(lines)>capacity*len(panels):raise ValueError('Full leaflet COPY exceeds its fold-safe 6 pt capacity')
        for index,(key,line) in enumerate(lines):
            panel=panels[index//capacity];safe=panel['safe_mm'];y=safe[1]+(index%capacity)*6*1.3/files.PT
            add_copy(s,{'field':key,'text':line,'color':'#1C1C1C'},[safe[0]+3,y+3,safe[2]+3,y+3+6/files.PT],floor=6,fixed_size=6)
            used.append(key)
    for line in geom['cuts']:
        s.line(*[tuple(v+3 for v in point) for point in line['points_mm']],layer='die',color=(1,0,.5))
    for line in geom['folds']:
        s.line(*[tuple(v+3 for v in point) for point in line['points_mm']],layer='guides')
    flow.write_json(ctx.root/'leaflet-copy.json',{'printed_fields':sorted(set(used)),
        'missing_inputs':missing,'full_copy':{k:copy[k] for k in set(used)},'geometry':geom})
    safe=[[v+3 for v in p['safe_mm']] for p in geom['panels']]
    return native_save(ctx,s,'leaflet',safe=safe)


def build_files(ctx):
    folder=ctx.root/'files';folder.mkdir(exist_ok=True)
    reports={};proofs={};ink_plates={}
    for panel in panel_records(ctx):
        panel_key=panel['id']
        variants=[None]+(['white-frost','rose-gold'] if panel['surface']=='clear_acrylic' else [])
        for ink in variants:
            key=panel_key+('-'+ink if ink else '');checkpoint=folder/(key+'.json')
            if checkpoint.exists():
                report=read(checkpoint);pinned(folder/report['file'],report['sha256']);pinned(folder/(key+'.png'),report['png_sha256'])
            else:
                w,h=panel['exact_mm'];s=files.Surface([w+6,h+6],ctx.brief['name']+' '+panel['label']+(' '+ink+' ink coverage' if ink else ''),[3,3,w+3,h+3])
                compose(s,ctx,panel,(3,3),separation=ink)
                if panel.get('shape')=='circle':s.circle((3+w/2,3+h/2),min(w,h)/2,layer='die')
                else:s.rect([3,3,w+3,h+3],layer='die',color=(1,0,.5))
                inset=min(3,min(w,h)/6);safe=[3+inset,3+inset,w+3-inset,h+3-inset]
                s.rect(safe,layer='guides')
                report=native_save(ctx,s,key,safe=[safe])
            if ink:
                # Read the actual saved plate; proof colour alone is not an ink.
                with fitz.open(folder/(key+'.ai')) as document:
                    files.set_layers(document,{'plate','type','mark','finish'})
                    with fitz.open(stream=document.tobytes(),filetype='pdf') as saved:
                        pixels=files.raster(saved,300)
                        monochrome=bool(np.max(np.ptp(pixels.astype(int),axis=2))<=1)
                        if not monochrome:raise ValueError('Ink coverage plate contains process colour: '+key)
                        if ink=='rose-gold' and saved[0].get_image_info():raise ValueError('Rose-gold ink must contain live type and vectors only')
                        if ink=='white-frost' and any(t['chars'] for t in saved[0].get_texttrace()):raise ValueError('Frost ink must not duplicate live lettering')
                report['ink_plate']={'ink':ink,'panel':panel_key,'positive_monochrome':True,
                    'black_is_ink':True,'white_is_no_ink':True,'bleed_mm':3,'trim_mm':panel['exact_mm'],
                    'process_colour':False,'mean_coverage':float((255-pixels.astype(float)).mean()/255)}
                flow.write_json(checkpoint,report)
                ink_plates.setdefault(panel_key,{})[ink]={'file':report['file'],'sha256':report['sha256']}
            reports[key]=report
        if panel['surface']=='clear_acrylic':proofs[panel_key]=proof_clear(ctx,panel)
    if any(p.get('engine_face') for p in ctx.build.inputs['panels']):
        key='carton';checkpoint=folder/'carton.json'
        if checkpoint.exists():
            report=read(checkpoint);pinned(folder/report['file'],report['sha256']);pinned(folder/(key+'.png'),report['png_sha256'])
        else:
            from . import stick_carton
            _,coords=product.engine_panels(ctx.brief)
            x0,y0,x1,y1=coords.cut_polygon.bounds
            s=files.Surface([x1-x0+6,y1-y0+6],ctx.brief['name']+' carton',[3,3,x1-x0+3,y1-y0+3])
            for panel in panel_records(ctx):
                if panel.get('engine_face'):
                    box=panel['engine']['box'];ground=panel['engine']['ground']
                    margins=[box[0]-ground[0],box[1]-ground[1],ground[2]-box[2],ground[3]-box[3]]
                    compose(s,ctx,panel,(box[0]-x0+3,box[1]-y0+3),bleed=margins)
            stick_carton.draw_die(s.page,coords,x0-3,y0-3,s.ocg['die'],s.ocg['guides'])
            safe=[[b[0]-x0+3,b[1]-y0+3,b[2]-x0+3,b[3]-y0+3] for b in [p['engine']['safe'] for p in panel_records(ctx) if p.get('engine_face')]]
            report=native_save(ctx,s,key,safe=safe)
            report['die_readback']=stick_carton.die_readback(folder/'carton.ai',coords,x0-3,y0-3)
            report['cut_edge_bleed_mm']=3
            report['front_notch_keepout']=[]
            for definition in panel_records(ctx):
                if definition.get('engine_face') and definition['engine']['keep_out'] is not None:
                    keep=definition['engine']['keep_out'];cx=keep['cx']-x0+3;cy=keep['cy']-y0+3;r=keep['r_mm']
                    for span in report['measurements']['printed_spans']:
                        b=span['box_mm'];nx=max(b[0],min(cx,b[2]));ny=max(b[1],min(cy,b[3]))
                        if (nx-cx)**2+(ny-cy)**2<r*r:report['front_notch_keepout'].append(span)
            flow.write_json(folder/'carton.json',report)
        reports[key]=report
    if (folder/'leaflet.json').exists():
        reports['leaflet']=read(folder/'leaflet.json');pinned(folder/'leaflet.ai',reports['leaflet']['sha256'])
    else:reports['leaflet']=leaflet(ctx)
    flow.write_json(ctx.root/'clear-proofs.json',proofs)
    manifest={'schema':'round_master_ink_plates/1','plates':ink_plates,
        'instructions':'Clear faces: print the named positive monochrome plates at 1:1. Black is ink coverage; white is no ink. Use white/frost ink for white-frost and rose-gold ink or foil for rose-gold. Register both to the same engine die on clear acrylic. The unsuffixed clear-face file is the colour composite proof, not a process-colour print plate. Die and guides are locked and nonprinting. Other surfaces print from their unsuffixed layered masters.'}
    flow.write_json(ctx.root/'print-plates.json',manifest)
    flow.write_json(ctx.root/'files.json',{'objects':{k:{'ai':v['file'],'sha256':v['sha256']} for k,v in reports.items()},'clear_proofs':proofs,'ink_plates':ink_plates,'print_manifest_sha256':sha(ctx.root/'print-plates.json')})
    actual_size_pdf(ctx,list(reports))
    return {'files':list(reports),'clear_proofs':proofs,'preview':preview(ctx)}


def actual_size_pdf(ctx,keys):
    proof=fitz.open()
    for key in keys:
        with fitz.open(ctx.root/'files'/(key+'.ai')) as document:
            files.set_layers(document,{'plate','type','mark','finish'})
            with fitz.open(stream=document.tobytes(),filetype='pdf') as src:
                box=src[0].rect
                # Tile oversized objects at 1:1 on A3; never shrink to fit.
                aw,ah=(210,297) if box.width/files.PT<=190 and box.height/files.PT<=267 else (297,420)
                tw,th=(aw-20)*files.PT,(ah-30)*files.PT
                nx=max(1,math.ceil(box.width/tw));ny=max(1,math.ceil(box.height/th))
                for iy in range(ny):
                    for ix in range(nx):
                        clip=fitz.Rect(ix*tw,iy*th,min((ix+1)*tw+5*files.PT,box.width),min((iy+1)*th+5*files.PT,box.height))
                        page=proof.new_page(width=aw*files.PT,height=ah*files.PT)
                        target=fitz.Rect(10*files.PT,10*files.PT,10*files.PT+clip.width,10*files.PT+clip.height)
                        # Blank cap pages deliberately carry only crop marks and identification furniture.
                        if src[0].get_contents():page.show_pdf_page(target,src,0,clip=clip,keep_proportion=False)
                        page.insert_font(fontname='latin',fontfile=str(files.FONT_PATHS['latin']))
                        page.insert_text((10*files.PT,(ah-12)*files.PT),key+' | 1:1 | Print at actual size | '+str(ix+1)+','+str(iy+1),fontname='latin',fontsize=8)
                        page.draw_line((10*files.PT,(ah-8)*files.PT),(110*files.PT,(ah-8)*files.PT),width=.4)
                        for x,y in ((target.x0,target.y0),(target.x1,target.y1)):
                            page.draw_line((x-4,y),(x+4,y),width=.3);page.draw_line((x,y-4),(x,y+4),width=.3)
    proof.save(ctx.root/'actual-size.pdf',garbage=3,deflate=True);proof.close()


def eye_binding(ctx,kind,ids):
    from .round_master_flow import digest
    paths=[path for _,path in eye_images(ctx,kind,ids)]
    paths += [ctx.root/'files'/(key+'.json') for key in ids+(['leaflet'] if kind=='leaflet' else [])]
    paths += [ctx.root/'files'/(key+'-'+ink+'.json') for key in ids for ink in ('white-frost','rose-gold') if (ctx.root/'files'/(key+'-'+ink+'.json')).exists()]
    return digest({str(path.relative_to(ctx.root)):sha(path) for path in paths})


def validate_eye(payload):
    if (not isinstance(payload,dict) or set(payload)!={'verdict','reason','allowed_differences','issues','repair'}
            or payload['verdict'] not in ('pass','fail') or not isinstance(payload['reason'],str) or not payload['reason'].strip()
            or not isinstance(payload['allowed_differences'],list) or not isinstance(payload['issues'],list)
            or not isinstance(payload['repair'],list)):
        raise ValueError('The designer’s eye must return a complete, explicit verdict')
    return payload


def eye_images(ctx,kind,ids):
    images=[]
    for key in ids:
        images += [(key+' picked sketch',ctx.root/'panels'/key/'sketch.png'),
                   (key+' saved master at 300 PPI',ctx.root/'files'/(key+'.png'))]
        images.append((key+' raster print only: no words may remain',ctx.root/'panels'/key/'plate.png'))
        if (ctx.root/'panels'/key/'clear-proof-0.png').exists():
            images.append((key+' printed frost on clear over the liquid',ctx.root/'panels'/key/'clear-proof-0.png'))
            for ink in ('white-frost','rose-gold'):
                images.append((key+' '+ink+' ink coverage: black prints, white stays open',ctx.root/'files'/(key+'-'+ink+'.png')))
    if kind=='carton':images.append(('Assembled flat carton on engine geometry',ctx.root/'files/carton.png'))
    if kind=='leaflet':images.append(('Leaflet from literal supplied copy',ctx.root/'files/leaflet.png'))
    return images


def apply_eye_repair(ctx,kind,ids,repair):
    """At most one bounded, explicit repair, keeping every previous artifact."""
    intent=ctx.root/'repairs'/kind/'intent.json'
    if intent.exists():
        saved=read(intent);plans=saved['before'];repair=saved['repair']
    else:plans=read(ctx.root/'layout.json')
    proposed=deepcopy(plans)
    for action in repair:
        if not isinstance(action,dict) or action.get('panel') not in ids:
            raise ValueError('Eye repair named an unrelated panel')
        key=action['panel'];panel=next(p for p in panel_records(ctx) if p['id']==key)
        if action.get('kind')=='type_box' and set(action)=={'kind','panel','index','box'}:
            index=action['index'];box=action['box']
            if not isinstance(index,int) or not 0<=index<len(plans[key]['text']) or not valid_box(box):
                raise ValueError('Invalid type repair')
            old=plans[key]['text'][index]['box'];w,h=panel['exact_mm']
            if abs((box[0]+box[2]-old[0]-old[2])*w/2)>1 or abs((box[1]+box[3]-old[1]-old[3])*h/2)>1:
                raise ValueError('Type repair exceeds the preservation position allowance')
            if any(abs((box[i+2]-box[i])/(old[i+2]-old[i])-1)>.03 for i in (0,1)):
                raise ValueError('Type repair exceeds the preservation size allowance')
            proposed[key]['text'][index]['box']=box
        else:
            raise ValueError('Eye repair requires a code fix; no unlisted design change is applied')
    archive=ctx.root/'repairs'/kind/'before';archive.mkdir(parents=True,exist_ok=True)
    marker=archive/'layout.json'
    if not marker.exists():flow.write_json(marker,plans)
    if not intent.exists():flow.write_json(intent,{'before':plans,'proposed':proposed,'repair':repair})
    dependent=[key+'-'+ink for key in ids for ink in ('white-frost','rose-gold')]
    for key in list(ids)+dependent+(['carton'] if kind=='carton' else []):
        for suffix in ('.ai','.png','.json'):
            path=ctx.root/'files'/(key+suffix)
            if path.exists():
                target=archive/path.name
                if not target.exists():path.rename(target)
    flow.write_json(ctx.root/'layout.json',proposed)
    flow.write_json(ctx.root/'repairs'/kind/'applied.json',{'repair':repair,'maximum_repairs':1})
    build_files(ctx)


def eye(ctx):
    verdicts={}
    groups=dict(objects(ctx),leaflet=[])
    for kind,ids in groups.items():
        final=ctx.root/'eye'/(kind+'.json')
        if final.exists():
            verdict=read(final)
            if verdict['input_sha256']!=eye_binding(ctx,kind,ids):raise ValueError('The master changed after its eye verdict')
            verdicts[kind]=verdict;continue
        repair_path=ctx.root/'repairs'/kind/'intent.json'
        if repair_path.exists():apply_eye_repair(ctx,kind,ids,read(repair_path)['repair'])
        for revision in range(1 if repair_path.exists() else 0,2):
            dest=ctx.root/'eye'/(kind+'-r'+str(revision)+'-call.json')
            prompt=('You are the designer’s eye, the only creative gate. The picked sketch IS the design. '
                'Compare each saved master with its own crop; no redesign. Judge fidelity, craftsmanship, '
                'type at the original position/scale, all visible words live and sourced from COPY, approved '
                'vector logo, true materials. Clear bodies print white/frost plus rose-gold over clear, with '
                'the shade liquid showing through open print, never a pink ink rectangle. Blank gold caps '
                'stay blank; any existing marks are engraving/foil vectors. Carton mandatory copy stays, '
                'regulated full drafts belong on leaflet. Missing supplied drafts are explicitly reported, never invented. '
                'Measured checks are reports to you, not a numeric aesthetic gate. Return JSON only with exactly '
                'verdict (pass or fail), reason (complete explanation), allowed_differences (list), issues (list), '
                'repair (list). One repair maximum. If a small type position/size repair resolves the issue, '
                'repair item is {kind:"type_box",panel:"id",index:0,box:[left,top,right,bottom]} in normalized '
                'panel coordinates, within 1mm position and 3% size of the existing measured box. Otherwise repair:[] '
                'and a complete fail reason. Do not request unlisted changes. This is '+kind+', revision '+str(revision)+'.\n'
                'Listed differences: '+json.dumps(read(ctx.root/'allowed-differences.json'),ensure_ascii=False)+'\n'
                'COPY: '+json.dumps(ctx.build.inputs['copy'],ensure_ascii=False)+'\n'
                'Leaflet source limitations: '+json.dumps(read(ctx.root/'leaflet-copy.json')['missing_inputs'])+'\n'
                'Measurements: '+json.dumps({key:read(ctx.root/'files'/(key+'.json'))['measurements'] for key in ids+(['leaflet'] if kind=='leaflet' else [])},ensure_ascii=False))
            result=ctx.text_call('eye/'+kind+'/r'+str(revision),prompt,dest,
                                images=eye_images(ctx,kind,ids),max_tokens=12288,ceiling=3.0)
            try:verdict=validate_eye(result['payload'])
            except (ValueError,TypeError,KeyError) as exc:ctx.reject_result(dest,str(exc));raise
            if revision==0 and verdict['verdict']=='fail' and verdict['repair']:
                apply_eye_repair(ctx,kind,ids,verdict['repair'])
                continue
            verdict['repairs_used']=revision
            verdict['input_sha256']=eye_binding(ctx,kind,ids)
            flow.write_json(final,verdict);verdicts[kind]=verdict
            break
    result={'objects':verdicts,'accepted':all(v['verdict']=='pass' for v in verdicts.values()),
            'gate':'designer’s eye','jury_is_gate':False}
    result['preview']=preview(ctx,result)
    flow.write_json(ctx.root/'eye.json',result)
    return result


def jury(ctx):
    dest=ctx.root/'jury-call.json'
    images=[]
    for kind,ids in objects(ctx).items():images.extend(eye_images(ctx,kind,ids))
    images.append(('Leaflet',ctx.root/'files/leaflet.png'))
    result=ctx.text_call('jury/master',
        'One jury record only, never a gate or a redesign request. Assess this owner-picked '+ctx.brief['name']+
        ' master against its original sketch and product truth. Would this belong to a $1B prestige house, '
        'and does its invention arise from this product’s own truth? Return JSON with record (nonempty text), '
        'strengths (list), concerns (list). No acceptance override. Eye verdict: '+json.dumps({k:v for k,v in read(ctx.root/'eye.json').items() if k!='preview'},ensure_ascii=False),
        dest,images=images,max_tokens=16384,ceiling=3.0)
    payload=result['payload']
    if not isinstance(payload,dict) or not isinstance(payload.get('record'),str) or not payload['record'].strip():
        ctx.reject_result(dest,'Missing complete jury record');raise ValueError('Incomplete jury record')
    flow.write_json(ctx.root/'jury.json',payload)
    return payload


def preview(ctx, verdict=None):
    from .round_calls import master_scoped_spend as scoped_spend
    panels=[];paths=[];inventory=read(ctx.root/'files.json')
    for panel in panel_records(ctx):
        key=panel['id'];mat=read(ctx.root/'panels'/key/'plate.json')
        row={'id':key,'label':panel['label'],'sketch':'panels/'+key+'/sketch.png',
             'master':'files/'+key+'.png','detail':read(ctx.root/'panels'/key/'detail.json'),
             'differences':mat['allowed_differences'],'clear_proofs':inventory['clear_proofs'].get(key,[])}
        panels.append(row);paths.extend([row['sketch'],row['master']]);paths.extend(p['file'] for p in row['clear_proofs'])
    paths.extend('files/'+key+'.png' for key in inventory['objects'])
    return {'panels':panels,'files':{path:sha(ctx.root/path) for path in paths},
            'eye':deepcopy(verdict),'spend':scoped_spend(ctx.build)}


def publish(ctx):
    from .round_calls import master_scoped_spend as scoped_spend
    spend=scoped_spend(ctx.build)
    if spend['held_usd'] or spend['accounted_usd']>float(ctx.build.budget_usd):
        raise ValueError('Master spend has an unresolved hold or exceeds its allowance')
    eye_record=read(ctx.root/'eye.json'); read(ctx.root/'jury.json')
    if not eye_record['accepted']:
        raise ValueError('The designer’s eye did not accept this master; findings are retained for review.')
    for kind,ids in dict(objects(ctx),leaflet=[]).items():
        if eye_record['objects'][kind]['input_sha256']!=eye_binding(ctx,kind,ids):raise ValueError('Eye verdict input changed before publication')
    inventory=read(ctx.root/'files.json');panels=[]
    pinned(ctx.root/'print-plates.json',inventory['print_manifest_sha256'])
    zip_path=ctx.root/'master-ai.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ctx.root/'print-plates.json',arcname='print-plates.json')
        for key,row in inventory['objects'].items():
            path=pinned(ctx.root/'files'/row['ai'],row['sha256'])
            report=read(ctx.root/'files'/(key+'.json'))
            pinned(ctx.root/'files'/(key+'.png'),report['png_sha256'])
            if report['native']['final_sha256']!=sha(path):raise ValueError('Native reopen evidence changed')
            if not report['native']['holds']:raise ValueError('Cannot publish a master without actual native reopen evidence')
            archive.write(path,arcname=path.name)
    png_zip=ctx.root/'flat-pngs.zip'
    with zipfile.ZipFile(png_zip,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for key in inventory['objects']:archive.write(ctx.root/'files'/(key+'.png'),arcname=key+'.png')
    for panel in panel_records(ctx):
        key=panel['id'];mat=read(ctx.root/'panels'/key/'plate.json')
        panels.append({'id':key,'label':panel['label'],'sketch':'panels/'+key+'/sketch.png',
            'master':'files/'+key+'.png','detail':read(ctx.root/'panels'/key/'detail.json'),
            'differences':mat['allowed_differences'],'clear_proofs':inventory['clear_proofs'].get(key,[])})
    flow.write_json(ctx.root/'spend.json',spend)
    download='/dashboard/rounds/'+str(ctx.round.pk)+'/master/files/master-ai.zip'
    events=[event for step in ctx.build.steps.values() for event in step['history']]
    lines=['# '+ctx.brief['name']+' — master', '',
        '- Owner pick: '+ctx.build.inputs['pick']['id']+'; all work through the app worker.',
        '- Stops: '+str(len(events))+'. Fixes and commits: [BREAKS.md](../BREAKS.md).',
        '- Detail: each crop edited at full resolution; rejected edits keep the exact 2× upscale.', '',
        '| Panel | ΔE00 mean | SSIM | Selected |','|---|---:|---:|---|']
    for panel in panels:
        d=panel['detail'];lines.append(f'| {panel["label"]} | {d["de00_mean"]:.5f} | {d["ssim"]:.5f} | '+('detail' if d['accepted'] else '2× crop')+' |')
    lines+=['',('- Clear body: white/frost ink plus rose-gold on transparent plates; shade colour is only in the separate liquid proof. Per-face measurements: allowed-differences.json.' if any(p['surface']=='clear_acrylic' for p in panel_records(ctx)) else '- Materials follow the product brief and each picked panel; see allowed-differences.json.'),
        ('- Gold cap: physical gold excluded from print; only existing vector marks, with blank caps preserved.' if any(p['surface']=='gold_metal' for p in panel_records(ctx)) else '- No gold-cap conversion applies to this product.'),
        '- Every file: native Illustrator saved and reopened, six layers, embedded fonts, live COPY type; die/guides locked.',
        ('- Clear-face printing: separate white/frost and rose-gold positive monochrome ink plates, 1:1; black is ink, white is open. See print-plates.json in the download. Colour composites are proofs.' if inventory['ink_plates'] else '- Print mapping is in print-plates.json in the download.'),
        '- Measurements (safe area, glyphs, contrast, cap and ℮ heights): files/*.json; reports do not replace the eye.',
        '- Eye: '+('pass' if eye_record['accepted'] else 'designer review — see object verdicts below')+'.']
    for kind,verdict in eye_record['objects'].items():
        lines.append('- '+kind+': '+verdict['verdict']+' — '+verdict['reason'].replace('\n',' '))
    lines+=['- Jury: called once, for the record in jury.json.',
        '- Leaflet input limitations: '+'; '.join(read(ctx.root/'leaflet-copy.json')['missing_inputs']),
        f'- Spend: ${spend["actual_usd"]:.6f} settled; ${spend["held_usd"]:.6f} held; $15 cap.',
        '- [Download layered Illustrator files]('+download+').',
        '- Other formats: 300 PPI flat PNGs and actual-size A4/A3 PDF on the master page.',
        '- The live result and this report are written by the worker; the builder did not execute a step.']
    if len(lines)>80:raise ValueError('Master report exceeds 80 lines')
    (ctx.root/'README.md').write_text('\n'.join(lines)+'\n')
    paths=['master-ai.zip','flat-pngs.zip','actual-size.pdf','README.md','eye.json','jury.json','spend.json','print-plates.json']
    for p in panels:
        paths.extend([p['sketch'],p['master']]);paths.extend(proof['file'] for proof in p['clear_proofs'])
    for key in inventory['objects']:paths.extend(['files/'+key+'.ai','files/'+key+'.png','files/'+key+'.json'])
    publication={'schema':'round_master_publication/1','panels':panels,'eye':eye_record,
                 'spend':spend,'download':'master-ai.zip','formats':['flat-pngs.zip','actual-size.pdf'],
                 'files':{path:sha(ctx.root/path) for path in paths}}
    flow.write_json(ctx.root/'publication.json',publication)
    return publication


def run_step(name,ctx):
    return {'panels':panels,'detail':detail,'layout':layout,'plates':plates,'files':build_files,
            'eye':eye,'jury':jury,'publish':publish}[name](ctx)
