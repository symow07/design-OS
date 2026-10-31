"""Build the review packet from retained artifacts; failed candidates are history."""
from pathlib import Path
import json,shutil,zipfile,textwrap,mimetypes
import fitz
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import day5_master as dm,fidelity_master as fm,fidelity_assets as fa
from .concept_quality import evaluate,DIMENSIONS
from .day4_proofs import setup,words,bar,image_on,render_pdf
ROOT=dm.ROOT

def candidates():
    directions=json.loads((ROOT/'concept-inputs-current/directions.json').read_text())
    attempts={'D1':'attempt-3','D2':'attempt-1','D3':'attempt-2'}
    human={'D1':['Eight bottles: two rows of four; required third row absent.'],
           'D2':[], 'D3':[]}
    notes={'D1':'Count8; incomplete critic contract; missing third row. No further D1 repair allowed.',
           'D2':'Raw mean7.1; missing required repair keeps review pending. Geometry widening/count changes and unsupported regulatory claims in critic are not adopted.',
           'D3':'Mean7.2; stars removed,12bottles retained. Header spacing, distinctiveness and premium finish remain below threshold. No further image attempt allowed.'}
    rows=[]
    for direction in directions['directions']:
        name=direction['id'];base=f'concepts/{name}/{attempts[name]}'
        review=json.loads((ROOT/base/'critic.json').read_text());verdict=evaluate(review['payload'])
        if review['image_sha256']!=fa.sha(ROOT/base/'image.png'):raise ValueError('Saved review belongs to different image bytes.')
        dimensions=review['payload'].get('dimensions',{})
        if not isinstance(dimensions,dict):dimensions={}
        scores=[dimensions[k]['score'] for k in DIMENSIONS if k in dimensions]
        mean=round(sum(scores)/len(scores),2) if len(scores)==10 else None
        rows.append({'id':name,'name':direction['name'],'story':direction['story'],'attempt':attempts[name],
          'image':base+'/image.png','image_sha256':fa.sha(ROOT/base/'image.png'),
          'critic':base+'/critic.json','critic_sha256':fa.sha(ROOT/base/'critic.json'),
          'mean':mean,'state':'rejected' if human[name] else verdict['review_status'],
          'eligible':verdict['passed'] and not human[name],'human_hard_failures':human[name],
          'flag_summary':notes[name],'house_references':['069 / ZYG404-E','043 / YB-1118','048 / YB-1123'],
          'copy_approximate':True,'dimensions_image_verified':False})
    return rows

def paragraph(c,x,y,text,width=90,size=10,leading=5):
    for line in textwrap.wrap(text,width):
        words(c,x,y,line,size);y-=leading
    return y

def pick_sheet(rows):
    setup();out=ROOT/'pick-sheet.pdf';c=Canvas(str(out),pagesize=(1000*mm,594*mm))
    words(c,22,565,'SUN REPAIR / DAY5 PICK SHEET',28)
    accepted=[r for r in rows if r['eligible']]
    words(c,22,547,'Eligible choices: '+str(len(accepted)),17)
    if not accepted:
        paragraph(c,22,531,'No candidate meets the unchanged mean8/10 bar. The image round is complete. No choice or creative acceptance is implied. Rejected and pending pictures are on the next page as review history.',100,13,7)
    for i,row in enumerate(accepted):
        image_on(c,ROOT/row['image'],22+i*200,170,180,270)
        words(c,22+i*200,155,row['id']+' / '+row['name'],14)
    image_on(c,ROOT/'render/published/front.png',300,160,180,240.03)
    image_on(c,ROOT/'master/projected-master.png',550,200,1024*fa.XS,1536*fa.YS)
    words(c,300,145,'Current deterministic approximation / Day4 stand artwork',12)
    words(c,550,185,'Bottle revision3 / designer review',12)
    paragraph(c,22,105,'The next page compares three requested directions, all in review history. Their complete picture frames share322mm height without stretching or cropping. This is a comparison convention, not verified physical scale for generated objects. The bottle is at its108mm overall convention; the deterministic view is a scaled perspective.',130,12,7)
    words(c,22,63,'Real-size authority: bottle comparison PDF and family construction PDF; print100%, disable Fit.',12)
    bar(c,22,40);c.showPage()
    words(c,22,565,'REVIEW HISTORY / NOT ELIGIBLE CHOICES',27)
    words(c,22,548,'Three requested concepts. Each full picture frame322mm high; generated objects are not verified1:1.',12)
    for i,row in enumerate(rows):
        x=22+i*230;im=Image.open(ROOT/row['image']);w=322*im.width/im.height
        # Complete image retained; no deletion, duplication or paint-over of bottles.
        image_on(c,ROOT/row['image'],x,190,w,322)
        score='score unavailable' if row['mean'] is None else str(row['mean'])+'/10'
        words(c,x,175,row['id']+' / '+row['name']+' / '+score,14)
        y=paragraph(c,x,164,row['story'],56,10,5)
        y=paragraph(c,x,y-4,row['flag_summary'],56,9,5)
        paragraph(c,x,y-4,'House069,043,048: consumer-artwork principles only; no product or copy substitution.',56,9,5)
    image_on(c,ROOT/'master/projected-master.png',760,290,1024*fa.XS,1536*fa.YS)
    image_on(c,ROOT/'render/published/front.png',760,48,150,200.025)
    words(c,760,425,'Pinned bottle / actual-size convention',10)
    words(c,760,35,'Current model / scaled perspective',10)
    words(c,22,45,'Trend sources and dated principles: trend-brief.md. Every paid image and raw critique remains retained.',11)
    bar(c,22,27);c.save();render_pdf(out);return out

def build():
    rows=candidates();pick_sheet(rows);master=ROOT/'master';spec=json.loads((master/'design-spec.json').read_text());dm.validate_spec(spec)
    if not (master/'concept-reference.png').exists():shutil.copyfile(fa.CONCEPT,master/'concept-reference.png')
    text=json.loads((ROOT/'text-audit/TRACED_TEXT.json').read_text());native=json.loads((master/'artwork-native-validation.json').read_text())
    with fitz.open(master/'artwork.pdf') as doc:
        page=doc[0];dimensions=[page.rect.width/mm,page.rect.height/mm]
        font_names=[f[3] for f in doc.get_page_fonts(0)]
        rasters=len(page.get_images())
    expected=[spec['graph']['width_mm'],spec['graph']['height_mm']]
    preflight={'product_spec_hash':fm.digest(spec),'dimensions_mm':dimensions,'expected_mm':expected,
      'dimensions_passed':all(abs(a-b)<.001 for a,b in zip(dimensions,expected)),
      'pdf_fonts':font_names,'raster_ink_planes':rasters,'native_transport_passed':native['passed'],
      'traced_text_revision3_passed':text['bundles']['revision3']['passed'],
      'review_state':'designer_review','production_ready':False,
      'limitations':['RGB review proof; no press profile or supplier approval.','Linear additive appearance proof is not a calibrated physical overprint.','Swoosh recomposition/fringe and exported Arabic pixel width fail.','Per-glyph live text limits line reflow.','Day4 stand surfacePDF/PNG lacks SVG/nativeAI; TRACED_TEXTfails that historical package.'],
      'files':{str(p.relative_to(master)):fa.sha(p) for p in master.rglob('*') if p.is_file() and p.name!='preflight.json' and not p.name.startswith('native-before')}}
    (master/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
    construction=ROOT/'construction';construction.mkdir(exist_ok=True)
    shutil.copyfile(ROOT.parent/'day-4/stand-family/construction.pdf',construction/'family-at-100-percent.pdf')
    # Only final owned artifacts and provenance go into the review archive.
    package=ROOT/'day5-review-package.zip'
    members=[p for p in master.rglob('*') if p.is_file() and not p.name.startswith('native-before')]
    members += [ROOT/'pick-sheet.pdf',ROOT/'trend-brief.md',ROOT/'render/render-review.pdf',ROOT/'render/determinism.json',ROOT/'text-audit/TRACED_TEXT.json',construction/'family-at-100-percent.pdf']
    members += list((ROOT/'render/published').glob('*.png'))
    members += [p for p in (ROOT/'render/portable').rglob('*') if p.is_file()]
    members += [ROOT/'reproduction.md',ROOT/'spend.json',ROOT/'openai-price-evidence.json']
    for row in rows:members.extend([ROOT/row['image'],ROOT/row['critic']])
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(set(members)):z.write(path,path.relative_to(ROOT))
    paths={'concept':'master/concept-reference.png','projection':'master/projected-master.png','flat':'master/artwork.png',
      'proof':'master/comparison-at-100-percent.pdf','preflight':'master/preflight.json','text':'text-audit/TRACED_TEXT.json',
      'front':'render/published/front.png','render':'render/render-review.pdf','construction':'construction/family-at-100-percent.pdf',
      'pick':'pick-sheet.pdf','package':package.name}
    paths.update({row['id']:row['image'] for row in rows})
    record={'schema':'day5_publication/1','product_spec_hash':fm.digest(spec),'assembly_sha256':fa.sha(ROOT.parent/'day-4/stand-family/assembly-spec.json'),
      'candidates':rows,'review_state':'designer_review','downloads':{role:{'path':path,'sha256':fa.sha(ROOT/path),'mime':mimetypes.guess_type(path)[0] or 'application/octet-stream'} for role,path in paths.items()}}
    (ROOT/'publication.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record
