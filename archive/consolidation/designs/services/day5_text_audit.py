"""Reproducible TRACED_TEXT audit including actual-size OCR controls."""
from pathlib import Path
import json,shutil,subprocess
import fitz,numpy as np
from PIL import Image
from . import traced_text as tt,day5_master as dm,fidelity_assets as fa,fidelity_master as fm

def run():
    root=dm.ROOT/'text-audit';root.mkdir(exist_ok=True);data=root/'tessdata';data.mkdir(exist_ok=True)
    for language,source in [('eng',Path('/opt/homebrew/share/tessdata/eng.traineddata')),('ara',dm.ROOT/'ocr/ara.traineddata')]:
        target=data/(language+'.traineddata')
        if not target.exists():target.symlink_to(source)
    # Positive controls are emitted live copy at300PPI, then intentionally baked.
    # Individual lines use their actual artwork size; OCR failure keeps the gate pending.
    controls=[]
    with fitz.open(dm.ROOT/'master/live-type-logo.pdf') as doc:
        expected=tt.expected_lines(json.loads((dm.ROOT/'master/design-spec.json').read_text()),dm.ROOT/'master/assets')
        live=tt.pdf_live(dm.ROOT/'master/live-type-logo.pdf',expected)
        for line,result in zip(expected,live['lines']):
            if line['id'] not in ['SUN','arabic']:continue
            clip=fitz.Rect(result['bbox_points']);pix=doc[0].get_pixmap(dpi=300,clip=clip,alpha=True)
            rgba=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4).copy();alpha=rgba[:,:,3:4].astype(float)
            rgba[:,:,:3]=np.clip(rgba[:,:,:3].astype(float)*255/np.maximum(alpha,1),0,255)
            im=Image.fromarray(rgba);im.save(root/(line['id']+'-baked-positive-300ppi.png'))
            result=tt.ocr_layers([im],[line['logical_text']],tessdata=data)
            controls.append({'id':line['id'],'copy':line['logical_text'],'ppi':300,'detected':bool(result.get('hits')),'result':result})
    passed=all(c['detected'] for c in controls) and len(controls)==2
    reports={}
    for name,folder in [('revision2',fa.ROOT/'docs/audit/day-4/master'),('revision3',dm.ROOT/'master')]:
        reports[name]=tt.inspect_bundle(folder,tessdata=data,ocr_controls_passed=passed)
    source=fa.ROOT/'docs/audit/day-4/stand-family/surfaces';binding=json.loads((source/'surface-bindings.json').read_text());stand=[]
    for s in binding['surfaces']:
        pdf=source/(s['surface_id']+'.pdf');ocr=tt.ocr_layers(tt.pdf_rasters(pdf),s['required_copy'],tessdata=data) if s['required_copy'] else {'passed':True,'state':'no required copy'}
        # Historical stand has noSVG/native versions: cannot satisfy all-format contract.
        stand.append({'surface_id':s['surface_id'],'pdf_sha256':fa.sha(pdf),'required_copy':s['required_copy'],'pdf_raster_ocr':ocr,'svg':'missing','native_ai':'missing','passed':False,'reason':'Historical surfaces havePDF/PNG only; missing editable formats. Header also contains clipped bottle text from logo-form import; global text counts are not acceptance.'})
    report={'code':'TRACED_TEXT','positive_controls':controls,'positive_controls_passed':passed,'bundles':reports,'day4_stand_surfaces':stand,'historical_stand_passed':False,'state':'passed' if passed and reports['revision3']['passed'] else 'failed_or_unverified','exclusions':'Concept reference images are presentation sources, never artwork rasters. Approved vector logo exempt from live-text law.','tesseract_version':subprocess.check_output(['/opt/homebrew/bin/tesseract','--version'],text=True).splitlines()[0]}
    (root/'TRACED_TEXT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
