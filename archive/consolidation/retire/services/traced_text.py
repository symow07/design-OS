"""TRACED_TEXT: visible live copy and independent OCR of embedded raster planes."""
from pathlib import Path
from collections import Counter
import base64,hashlib,io,json,re,subprocess,tempfile,unicodedata,xml.etree.ElementTree as ET
import fitz,numpy as np
from PIL import Image,ImageOps
from . import fidelity_assets as fa,fidelity_master as fm
MM=72/25.4

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())

def face(name):return re.sub(r'^[A-Z]{6}\+','',name)

def neutral(pix):
    a=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)
    return a[:,:,:3].astype(float)+128*(1-a[:,:,3:4]/255) if pix.n==4 else a.astype(float)

def expected_lines(spec, font_directory=None):
    fonts=spec.get('fonts',{});result=[]
    from fontTools.ttLib import TTFont
    cmaps={}
    for role,record in fonts.items():
        path=Path(font_directory)/record['filename'] if font_directory else fm.FONTS[role]
        if fa.sha(path)!=record['sha256']:raise ValueError('Recorded text face changed.')
        with TTFont(path) as ft:cmaps[role]=ft.getBestCmap()
    for line in spec['graph']['lines']:
        runs=[]
        for run in line['runs']:
            role=run['font_role'];font=fonts[role].get('postscript') or fm.font_data(role)['postscript']
            aliases=[run['text']]
            # PDF editors may choose another Unicode alias for exactly the same
            # glyph. Accept only aliases proven by the pinned font's own cmap.
            if len(run['text'])==1:
                glyph=cmaps[role].get(ord(run['text']))
                aliases.extend(chr(code) for code,name in cmaps[role].items() if name==glyph)
            if run.get('shaped_glyph_name'):
                # Illustrator's ToUnicode restores standard Arabic presentation
                # forms for these same Cairo glyphs instead of retaining PUA aliases.
                glyph=run['shaped_glyph_name']
                if re.fullmatch(r'uni[0-9A-F]{4}',glyph):aliases.append(chr(int(glyph[3:],16)))
                elif glyph=='sad_noonar':aliases.append('\ufebb\ufee6')
            runs.append({'text':run['text'],'transport_texts':aliases,'font':font,'origin':[run['x_mm']*MM,(spec['graph']['height_mm']-run['baseline_z_mm'])*MM]})
        result.append({'id':line['id'],'logical_text':line['logical_text'],'runs':runs})
    return result

def pdf_live(path,lines):
    results=[]
    with fitz.open(path) as doc:
        page=doc[0];chars=[]
        for span in page.get_texttrace():
            for ch in span['chars']:
                chars.append({'text':chr(ch[0]),'font':face(span['font']),'origin':ch[2],'bbox':ch[3],'visible':span['type']==0 and span['opacity']>=.99})
        for line in lines:
            found=[];used=set()
            for run in line['runs']:
                options=[(i,c) for i,c in enumerate(chars) if i not in used and c['font']==run['font'] and c['visible'] and max(abs(a-b) for a,b in zip(c['origin'],run['origin']))<=.35]
                if ''.join(c['text'] for i,c in options) in run.get('transport_texts',[run['text']]):
                    for i,c in options:used.add(i)
                    merged=dict(options[0][1]);box=fitz.Rect(merged['bbox'])
                    for i,c in options[1:]:box|=fitz.Rect(c['bbox'])
                    merged['bbox']=list(box);found.append(merged)
            live=len(found)==len(line['runs']) and bool(found)
            contribution=0;bbox=None
            if live:
                bbox=fitz.Rect(found[0]['bbox'])
                for c in found[1:]:bbox|=fitz.Rect(c['bbox'])
                bbox=(bbox+(-.3,-.3,.3,.3))&page.rect
                if not bbox.is_empty:
                    before=neutral(page.get_pixmap(dpi=600,clip=bbox,alpha=True))
                    with fitz.open(stream=doc.tobytes(),filetype='pdf') as stripped:
                        stripped[0].add_redact_annot(bbox,fill=None,cross_out=False)
                        stripped[0].apply_redactions(images=0,graphics=0,text=0)
                        after=neutral(stripped[0].get_pixmap(dpi=600,clip=bbox,alpha=True))
                    if before.shape==after.shape:contribution=int(np.sum(np.max(np.abs(before-after),axis=2)>4))
            results.append({'id':line['id'],'expected_runs':len(line['runs']),'matched_visible_runs':len(found),'live_font_and_position':live,'visible_text_contribution_pixels':contribution,'bbox_points':list(bbox) if bbox else None,'passed':live and contribution>5})
    return {'artifact_sha256':fa.sha(path),'lines':results,'passed':all(x['passed'] for x in results),'instrument':'Actual glyph/font/origin/type0/opacity>=.99 and removal of live text changes its visible crop; paths and images retained.'}

def svg_live(path,spec):
    root=ET.parse(path).getroot();parents={child:parent for parent in root.iter() for child in parent};rows=[]
    def visible(e):
        while e is not None:
            style=e.get('style','').replace(' ','')
            if e.get('display')=='none' or e.get('visibility')=='hidden' or e.get('opacity')=='0' or any(x in style for x in ['display:none','visibility:hidden','opacity:0']):return False
            e=parents.get(e)
        return True
    for line in spec['graph']['lines']:
        group=next((x for x in root.iter() if x.get('id')==line['id']),None)
        texts=[x for x in group.iter() if x.tag.endswith('}text')] if group is not None else []
        expected=[(r['text'],spec['fonts'][r['font_role']].get('family') or fm.font_data(r['font_role'])['family']) for r in line['runs']]
        found=[(x.text,x.get('font-family')) for x in texts if visible(x) and 'matrix(0 ' not in x.get('transform','')]
        rows.append({'id':line['id'],'passed':expected==found and bool(found),'expected_runs':len(expected),'visible_runs':len(found)})
    style=''.join(x.text or '' for x in root.iter() if x.tag.endswith('}style'))
    hashes={hashlib.sha256(base64.b64decode(v)).hexdigest() for v in re.findall(r'base64,([A-Za-z0-9+/=]+)',style)}
    embedded=all(f['sha256'] in hashes for f in spec['fonts'].values())
    return {'artifact_sha256':fa.sha(path),'lines':rows,'font_bytes_pinned':embedded,'passed':embedded and all(r['passed'] for r in rows)}

def pdf_rasters(path):
    result=[]
    with fitz.open(path) as doc:
        seen=set()
        for row in doc[0].get_images(full=True):
            if row[0] in seen:continue
            seen.add(row[0]);pix=fitz.Pixmap(doc,row[0])
            if row[1]:pix=fitz.Pixmap(pix,fitz.Pixmap(doc,row[1]))
            if pix.colorspace and pix.colorspace.n!=3:pix=fitz.Pixmap(fitz.csRGB,pix)
            result.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA'))
    return result

def svg_rasters(path):
    root=ET.parse(path).getroot();out=[]
    for x in root.iter():
        if x.tag.endswith('}image'):
            href=x.get('href') or x.get('{http://www.w3.org/1999/xlink}href','')
            if not href.startswith('data:image/'):raise ValueError('Unresolved external raster must be checked before TRACED_TEXT can pass.')
            out.append(Image.open(io.BytesIO(base64.b64decode(href.split(',',1)[1]))).convert('RGBA'))
    return out

def ocr_layers(images,copy,*,tessdata=None):
    """Each actual embedded plane on3grounds plus alpha; language support mandatory."""
    langs='eng+ara' if any('\u0600'<=c<='\u06ff' for text in copy for c in text) else 'eng'
    base=['/opt/homebrew/bin/tesseract'];extra=['--tessdata-dir',str(tessdata)] if tessdata else []
    available=subprocess.run(base+['--list-langs']+extra,capture_output=True,text=True)
    missing=[l for l in langs.split('+') if l not in available.stdout.splitlines()]
    if missing:return {'state':'unverified','passed':False,'missing_languages':missing,'hits':[]}
    hits=[];observations=[]
    with tempfile.TemporaryDirectory(prefix='bbrose-ocr-') as temp:
        for i,rgba in enumerate(images):
            views=[]
            for ground in [0,128,255]:
                bg=Image.new('RGBA',rgba.size,(ground,)*3+(255,));views.append((str(ground),Image.alpha_composite(bg,rgba).convert('RGB')))
            views.append(('alpha',rgba.getchannel('A').convert('RGB')))
            for name,im in views:
                # Retain actual image scale; add a plain margin for OCR segmentation.
                margin=Image.new('RGB',(im.width+40,im.height+40),'white');margin.paste(im,(20,20));file=Path(temp)/f'{i}-{name}.png';margin.save(file)
                completed=subprocess.run(base+[str(file),'stdout','-l',langs,'--psm','11']+extra,capture_output=True,text=True,timeout=60)
                if completed.returncode:return {'state':'unverified','passed':False,'error':completed.stderr[:400],'hits':hits}
                text=completed.stdout;observations.append({'image':i,'ground':name,'text':text.strip()})
                for required in copy:
                    normalized=normalize(required)
                    if normalized and normalized in normalize(text):hits.append({'image':i,'ground':name,'copy':required})
            if 'ara' in langs:
                # Sparse segmentation misses the small joined Arabic control.
                # A second, disclosed raw-line pass uses the same alpha plane,
                # inverted and interpolated2x; no letters or pixels are invented.
                alpha=ImageOps.invert(rgba.getchannel('A'))
                alpha=ImageOps.expand(alpha.resize((alpha.width*2,alpha.height*2)),20,255)
                file=Path(temp)/f'{i}-alpha-arabic-line.png';alpha.save(file)
                completed=subprocess.run(base+[str(file),'stdout','-l','ara','--psm','13']+extra,capture_output=True,text=True,timeout=60)
                if completed.returncode:return {'state':'unverified','passed':False,'error':completed.stderr[:400],'hits':hits}
                text=completed.stdout;observations.append({'image':i,'ground':'inverted alpha2x, Arabic raw-line','text':text.strip()})
                for required in copy:
                    normalized=normalize(required)
                    if normalized and normalized in normalize(text):hits.append({'image':i,'ground':'inverted alpha2x, Arabic raw-line','copy':required})
    return {'state':'failed' if hits else 'clean','passed':not hits,'languages':langs,'hits':hits,'observations':observations,'engine':'Tesseract CLI; actual embedded raster pixels, no concept/reference images included'}

def inspect_bundle(folder,*,tessdata=None,ocr_controls_passed=False):
    folder=Path(folder);spec=json.loads((folder/'design-spec.json').read_text());lines=expected_lines(spec,folder/'assets');copy=[r['logical_text'] for r in lines];report={'code':'TRACED_TEXT','spec_hash':fm.digest(spec),'formats':{},'ocr_positive_controls_passed':ocr_controls_passed,'logo_exemption':'Approved vector BBROSE mark only; every other copy line must stay live.'}
    for key,file in [('pdf','artwork.pdf'),('svg','artwork.svg'),('native','artwork-native.ai')]:
        path=folder/file
        if not path.exists():report['formats'][key]={'passed':False,'state':'missing'};continue
        live=svg_live(path,spec) if key=='svg' else pdf_live(path,lines)
        rasters=svg_rasters(path) if key=='svg' else pdf_rasters(path)
        ocr=ocr_layers(rasters,copy,tessdata=tessdata)
        report['formats'][key]={'live':live,'raster_ocr':ocr,'passed':live['passed'] and ocr['passed'] and ocr_controls_passed}
    report['passed']=all(x['passed'] for x in report['formats'].values());report['state']='passed' if report['passed'] else 'failed_or_unverified'
    return report
