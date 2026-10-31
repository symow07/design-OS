"""Owner review sheets, real-size artwork and explicitly approximate render views."""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import day5_master as dm,fidelity_master as fm,fidelity_assets as fa
from .day4_proofs import setup,words,heading,bar,image_on,render_pdf
ROOT=dm.ROOT

def critic_record():
    r={'reviewer':'Independent read-only visual advisor; actual master/native crops inspected','creative_dimensions':dict(colour=8,hierarchy=8,negative_space=8,pattern_illustration=5,typography=7,shelf_impact=7,premium=6,distinctiveness=7,trend=7,beauty=7),'creative_mean':7.0,'fidelity_mean':8.4,'critical_illustration':5,'passed':False,'review_state':'designer_review','flags':['Amber fragments remain at top-right, middle-right and lower terminal on neutral grey.','Flat cream interior and irregular edges differ from original.','Natural Cairo width+2.956%; exported160px versus155px yields+3.226%, still outside pixel instrument.'],'corrected':['Rectangular shoulder/heel material patch removed; measured shell retained.','Native approved logo includes registered symbol; local logo comparison added.'],'not_claimed':['Physical2m shelf test','Creative acceptance','Calibrated optical rendering','Supplier production approval'],'sources':{n:fa.sha(ROOT/'master'/n) for n in ['projected-master.png','artwork.pdf','artwork-native.ai','fidelity-check.json']}}
    (ROOT/'master/critic.json').write_text(json.dumps(r,indent=2)+'\n');return r

def bottle_sheet():
    setup();p=ROOT/'master';out=p/'comparison-at-100-percent.pdf';c=Canvas(str(out),pagesize=(210*mm,297*mm));m=json.loads((p/'fidelity-check.json').read_text());proof=m['two_ink'];cairo=m['arabic_geometric_measurement']
    import subprocess
    from PIL import ImageOps
    from .cairo_measured import FONT,COPY
    for label,font,variation in [('noto',fm.FONTS['arabic'],None),('cairo300',FONT,'wght=300,slnt=0')]:
        raw=p/(label+'-padded-source.png')
        command=['/opt/homebrew/bin/hb-view',str(font),COPY,'--direction=rtl','--language=ar','--script=arab','--font-size=200','--margin=50','--ink','--foreground=f8f6f5','--background=none','--output-format=png','--output-file='+str(raw)]
        if variation:command.append('--variations='+variation)
        subprocess.run(command,check=True,capture_output=True)
        im=Image.open(raw).convert('RGBA');im=im.crop(im.getchannel('A').getbbox())
        im=im.resize((round(im.width/im.height*100),100),Image.Resampling.LANCZOS)
        ImageOps.expand(im,8,(128,128,128,255)).save(p/(label+'-padded-4x.png'))
    heading(c,'SUN REPAIR / revision 3','DESIGNER REVIEW - day continues under D-D5-1')
    W,H=1024*fa.XS,1536*fa.YS
    for x,file,label in [(5,fa.CONCEPT,'Concept147'),(75,p/'projected-master.png','R3 additive presentation proof')]:
        image_on(c,file,x,128,W,H);words(c,x+10,121,label,8)
    c.setFillColorRGB(.502,.502,.502);c.rect(157*mm,139*mm,fa.WIDTH*mm,fa.HEIGHT*mm,fill=1,stroke=0);image_on(c,p/'artwork.png',157,139,fa.WIDTH,fa.HEIGHT);words(c,157,121,'Two-ink editable preview',8)
    lines=['One scale:108mm overall comparison convention; height datum remains unknown.','Flat PDF/SVG/native use normal over of the two editable ink separations.','The middle proof uses linear-light B*(1-F-S)+cream*F+shadow*S, plus live type.','These differ mathematically; neither is a calibrated physical overprint proof.','Cream process/spot coverage + deep-amber shadow ink + opaque white live type.','Owner method, shoulder conformity, film edge, opacity and press profile unresolved.','Creative mean7.0/10; fidelity8.4/10; critical illustration5/10 - REVIEW.','The generated isolation was rejected: enlarged/moved stroke; grey not exact128.']
    for i,text in enumerate(lines):words(c,14,106-i*8,text,8)
    bar(c,14,29);c.showPage()
    heading(c,'Two inks / the unchanged acceptance bar','300PPI flat grid; both images blurred in linear light at sigma0.08mm (0.9449px)')
    rows=[('Ground held-out ring',f"medianDE{proof['background']['ring_median_deltaE2000']:.3f} / limit1.5 - PASS"),('Deterministic recomposition','31.36% withinDE2 / required99% - FAIL'),('Deterministic grey fringe','289 flagged pixels outside frozen shadow support - FAIL'),('Day4 negative','68.74% withinDE2;7453 fringe pixels - FAIL'),('Single-ink Day5 negative','71.29% withinDE2;5342 fringe pixels - FAIL'),('Image fallback vs original','7.39% withinDE2;117 fringe pixels - REJECTED')]
    for i,(label,value) in enumerate(rows):words(c,14,254-i*10,label,8);words(c,75,254-i*10,value,7)
    words(c,14,184,'Instrument correction: physical print cannot carry source pixel grain.',8)
    words(c,14,176,'Same code, frozen support and thresholds apply to both retained negatives.',8)
    boxes=[('Tip',(389,0,539,150)),('Inner bend',(389,350,539,500)),('Lower return',(389,650,539,800))]
    for j,(name,box) in enumerate(boxes):
        x=16+j*64;words(c,x,164,name+' / 4x physical crop',8)
        for row,(source,caption) in enumerate([('two_ink-amber-300ppi.png','Clean amber proof'),('two_ink-grey-300ppi.png','Neutral grey proof')]):
            crop=Image.open(dm.INK/source).crop(box);path=p/(name.lower().replace(' ','-')+'-'+str(row)+'.png');crop.save(path);y=105-row*67;image_on(c,path,x,y,50.8,50.8);words(c,x,y-6,caption,7)
    words(c,14,25,'Held-out ring excluded from both separable fit and Poisson boundary data.',8)
    words(c,14,17,'Frozen own-shadow support is not expanded to excuse cream-edge remnants.',8);c.showPage()
    heading(c,'Arabic / heaviest fitting Cairo instance','ARABIC_SCALE_4_PERCENT withdrawn: a licensed fitting face is now applied')
    # Actual new live-type export, projected back to original concept coordinates.
    rgba=fa.project(fm.render_artwork(p/'live-type-logo.pdf'));crop=rgba[1037:1082,340:525];alpha=crop[:,:,3:4]/255;rgb=(crop[:,:,:3]*alpha+128*(1-alpha)).astype(np.uint8);chosen=p/'cairo-selected-4x.png';Image.fromarray(rgb).resize((740,180),Image.Resampling.NEAREST).save(chosen)
    for x,file,label in [(10,p/'noto-padded-4x.png','Noto / natural proportion'),(84,p/'cairo300-padded-4x.png','Cairo300 / uniform fit'),(139,chosen,'Cairo340.17 / applied')]:
        # All are source-pixel crops at4x physical scale; preserve their own aspect.
        im=Image.open(file);w=im.width*fa.XS;h=im.height*fa.YS
        c.setFillColorRGB(.502,.502,.502);c.rect(x*mm,220*mm,w*mm,18*mm,fill=1,stroke=0)
        image_on(c,file,x,229-h/2,w,h);words(c,x,244,label,7)
    for i,text in enumerate([f"Natural shaped ink: {cairo['width_at_25px']:.4f} x25px, width+{cairo['delta_width_percent']:.4f}%.",'Bisection300..400,0.01-weight precision; no independent width squeeze.','Actual source-grid export:160x25px versus155x25px: width+3.226%,height0%.','The pixel check remains REVIEW; continuous font geometry does not waive it.','Cairo has lower stroke contrast than Noto; original face is unidentified.','Live per-glyph objects retain shaped glyphs; automatic line reflow is limited.']):words(c,14,205-i*9,text,8)
    inventory=json.loads((ROOT/'arabic-font-inventory.json').read_text());best={}
    for row in inventory['candidates']:
        family=row['family']
        if family not in best or row['delta_width_percent']<best[family]['delta_width_percent']:best[family]=row
    words(c,14,139,'Earlier named-face samples / width at25px; chosen instance above',9)
    for i,(name,row) in enumerate(best.items()):
        if i>8:break
        words(c,14,127-i*9,f"{name}: {row['width_at_measured_height_px']:.2f}px; width delta{row['delta_width_percent']:.2f}%",8)
    words(c,14,36,'Full font inventory, hashes, shaping rows and bisection history accompany the proof.',8);bar(c,14,23);c.save();render_pdf(out)
    return out

def render_sheet():
    setup();folder=ROOT/'render';out=folder/'render-review.pdf';c=Canvas(str(out),pagesize=(210*mm,297*mm))
    for view in ['front','median','three-quarter','plan-front']:
        heading(c,'Twelve-bottle stand / '+view,'Blender4.5.12 LTS - deterministic material approximation')
        image_on(c,folder/'published'/f'{view}.png',15,28,180,240.03)
        words(c,14,23,'Scene bar represents50mm; scaled perspective, image is not life-size.',7)
        bar(c,14,13);words(c,80,13,'Print calibration only:100%, disable Fit.',7);c.showPage()
    c.save();render_pdf(out);return out
