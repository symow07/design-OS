"""Day 6 presentation: D1 picture | deterministic render | revision-3 bottle at one
page scale (1:2), the per-surface table with the measurement's deviation list,
header.front and riser.1.front at 1:1 with the 50 mm bar, and the four-view render
review. build() is re-runnable: the fidelity columns come from
surfaces/fidelity-summary.json when it exists and print 'fidelity: pending' otherwise."""
from pathlib import Path
import json
import fitz
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from . import fidelity_assets as fa,fidelity_master as fm,day6_scene as d6
from .day4_proofs import setup,words,heading,bar,image_on,render_pdf

ROOT=d6.ROOT;RENDER=d6.RENDER
D1=fa.ROOT/'docs/audit/day-5/concepts/D1/attempt-2/image.png'
BOTTLE=fa.ROOT/'docs/audit/day-5/master/projected-master.png'
FIDELITY=ROOT/'surfaces/fidelity-summary.json'   # surfaces revision 1; fidelity_path() resolves other revisions
CURRENT=d6.CURRENT_SURFACES_REVISION
FIDELITY_SCHEMA='day6_surface_fidelity_summary/1'
A3=(420,297);A4=(210,297);MM=72/25.4
SCALE=.5
SURFACES=['header.front','riser.3.front','riser.2.front','lip.front','riser.1.front','side.left','side.right']
PAGE_INDEX={'header.front':2,'riser.1.front':3}
NOTE_WIDTH=50


def lines(c,x,y,texts,size,step):
    for i,t in enumerate(texts):words(c,x,y-i*step,t,size)
    return y-len(texts)*step


def wrap(text,width):
    out=[];line=''
    for word in text.split():
        if len(line)+len(word)+1>width and line:out.append(line);line=word
        else:line=(line+' '+word).strip()
    return out+[line] if line else out


def scaled_bar(c,x,y,scale):
    length=50*scale;c.setStrokeColorRGB(.15,.2,.2);c.setLineWidth(.7);c.line(x*mm,y*mm,(x+length)*mm,y*mm)
    for end in (x,x+length):c.line(end*mm,(y-2)*mm,end*mm,(y+2)*mm)
    words(c,x,y-6,f'represents 50 mm at the 1:{1/scale:g} page scale ({length:g} mm printed)',7)


def picture_geometry(measurement,height_mm):
    """The pictured stand, header top to lip bottom, is scaled to the solved height."""
    header=next(f for f in measurement['faces'] if f['surface_id']=='header.front');lip=next(f for f in measurement['faces'] if f['surface_id']=='lip.front')
    top=header['source_box_px'][1];bottom=lip['source_box_px'][3];size=Image.open(D1).size
    return {'image_px':list(size),'stand_top_px':top,'stand_bottom_px':bottom,'stand_height_px':bottom-top,'px_per_mm':(bottom-top)/height_mm,'stand_height_mm':height_mm}


def render_geometry(manifest,cfg,header_mm):
    """The render is a perspective view: exact scale only in the camera aim plane (manifest field)."""
    field=manifest['camera']['front']['reference_plane_vertical_field_mm'];mm_per_px=field/cfg['resolution'][1];x0,y0,x1,y1=manifest['diagnostic_regions']['header.front']
    return {'aim_plane_field_mm':field,'mm_per_px':mm_per_px,'header_region_px':[x0,y0,x1,y1],'header_apparent_mm':(y1-y0-4)*mm_per_px,'header_nominal_mm':header_mm}


def fidelity_row(summary,surface_id):
    """The surface's row of a day6_surface_fidelity_summary/1 record, or None when absent."""
    if summary is None or 'schema' not in summary or summary['schema']!=FIDELITY_SCHEMA or 'rows' not in summary:return None
    rows=[r for r in summary['rows'] if isinstance(r,dict) and 'surface_id' in r and r['surface_id']==surface_id]
    return rows[0] if rows else None


def cell(row,verdict_key,detail_keys,fmt):
    """'PASS 0.19 mm' style cell from a row; absent keys print as '-', never a substitute value."""
    verdict=str(row[verdict_key]) if verdict_key in row else '-'
    details=[fmt[k].format(row[k]) for k in detail_keys if k in row and isinstance(row[k],(int,float)) and not isinstance(row[k],bool)]
    return ' '.join([verdict]+details)


FIDELITY_COLUMNS=[('placement',('placement_worst_offset_mm','placement_worst_size_percent'),{'placement_worst_offset_mm':'{:.2f}mm','placement_worst_size_percent':'{:.2f}%'}),
  ('ink_colour',('ink_delta_e_max',),{'ink_delta_e_max':'dE{:.2f}'}),('field',('field_delta_e_max','field_failing','field_total'),{'field_delta_e_max':'dE{:.1f}','field_failing':'{}','field_total':'/{}'}),
  ('gesture',('gesture_max_mm',),{'gesture_max_mm':'{:.2f}mm'}),('grammar',(),{}),('continuity',(),{})]


def fidelity_cells(summary,surface_id):
    """Fidelity columns for the table: pending when the summary is absent; B1's categories when present."""
    if summary is None:return ['fidelity: pending']*len(FIDELITY_COLUMNS)+['pending']
    row=fidelity_row(summary,surface_id)
    if row is None:
        if 'schema' in summary and summary['schema']==FIDELITY_SCHEMA:return ['no row']*len(FIDELITY_COLUMNS)+['no row']
        return ['schema?']*len(FIDELITY_COLUMNS)+['unrecognised schema']
    cells=[cell(row,key,detail,fmt).replace(' /','/') for key,detail,fmt in FIDELITY_COLUMNS]
    passed='-'
    if 'measured_fidelity_passed' in row:passed=('PASS' if row['measured_fidelity_passed'] else 'FAIL')
    return cells+[passed]


def fidelity_path(surfaces_revision):return d6.profile(surfaces_revision)['surfaces']/'fidelity-summary.json'


def summary_or_none(path):return json.loads(path.read_text()) if path.exists() else None


def inputs(surfaces_revision):
    pr=d6.profile(surfaces_revision);render=pr['render'];measurement=json.loads(d6.MEASUREMENT.read_text())
    if fa.sha(D1)!=measurement['source_sha256']:raise ValueError('The D1 picture bytes differ from the measurement source.')
    data={'revision':surfaces_revision,'render':render,'surfaces':pr['surfaces'],'measurement':measurement,'assembly':json.loads(pr['assembly'].read_text()),'bindings':json.loads((pr['surfaces']/'surface-bindings.json').read_text()),'cfg':json.loads((render/'scene-config.json').read_text()),
      'determinism':json.loads((render/'determinism.json').read_text()),'manifest':json.loads((render/'verified-run-1/scene-manifest.json').read_text()),'sightlines':json.loads((ROOT/'sightlines.json').read_text()),'census':json.loads((render/'actual-scene-census.json').read_text()),
      'checks':summary_or_none(render/'checks/checks.json'),'fidelity':summary_or_none(fidelity_path(surfaces_revision)),'superseded':None}
    # The revision-1 scene config predates the 'surfaces_revision' field; later configs carry it.
    config_revision=1
    if 'surfaces_revision' in data['cfg']:config_revision=data['cfg']['surfaces_revision']
    if data['assembly']['revision']!=pr['assembly_revision'] or data['determinism']['pins']['assembly_sha256']!=fa.sha(pr['assembly']) or config_revision!=surfaces_revision:raise ValueError('The render pins do not match this surfaces revision.')
    if surfaces_revision==2:
        one=d6.profile(1);data['superseded']={'revision':1,'bindings':json.loads((one['surfaces']/'surface-bindings.json').read_text()),'fidelity':summary_or_none(fidelity_path(1)),'render':one['render'],'correction':data['bindings']['correction']}
    return data


def verdict_word(passed):return 'PASS' if passed else 'FAIL'


def page_one(c,d):
    a=d['assembly'];m=d['measurement'];pic=picture_geometry(m,a['height_mm']);ren=render_geometry(d['manifest'],d['cfg'],a['header_height']);s=d['sightlines']['points'];det=d['determinism']
    heading(c,'SUN REPAIR / D1 "Amber Current" on the twelve-bottle stand',f"DESIGNER REVIEW - direction accepted (D-D6-1), no file accepted; surfaces revision {d['revision']}"+(' (corrected device pose; revision 1 retained as the superseded attempt)' if d['revision']==2 else ' (retained attempt, superseded by revision 2)')+'; one page scale 1:2 for all three panels',*A3)
    y0=50;w_pic=pic['image_px'][0]/pic['px_per_mm']*SCALE;h_pic=pic['image_px'][1]/pic['px_per_mm']*SCALE;x_pic=12
    w_ren=d['cfg']['resolution'][0]*ren['mm_per_px']*SCALE;h_ren=d['cfg']['resolution'][1]*ren['mm_per_px']*SCALE;x_ren=x_pic+w_pic+10
    bottle=Image.open(BOTTLE).size;w_bot=bottle[0]*fa.XS*SCALE;h_bot=bottle[1]*fa.YS*SCALE;x_bot=x_ren+w_ren+10
    image_on(c,D1,x_pic,y0,w_pic,h_pic);image_on(c,d['render']/'published/front.png',x_ren,y0,w_ren,h_ren);image_on(c,BOTTLE,x_bot,y0,w_bot,h_bot)
    lines(c,x_pic,y0-6,['AI concept picture - D1 attempt 2, full frame, no crop (sha '+m['source_sha256'][:12]+')',f"pictured stand, header top to lip bottom = {pic['stand_height_px']} px, scaled to {pic['stand_height_mm']} mm at 1:2",'eight bottles in the picture: artwork source only (D-D6-2), never geometry'],7,5.2)
    lines(c,x_ren,y0-6,['Deterministic material approximation - Blender 4.5.12 LTS front view, 32 samples, seed 0',f"{d['cfg']['resolution'][1]} px = {ren['aim_plane_field_mm']} mm in the camera aim plane at 1:2; perspective, not an elevation",f"header face here {ren['header_apparent_mm']*SCALE:.1f} mm vs {ren['header_nominal_mm']*SCALE:.0f} mm nominal; surfaces r{d['revision']}, bottle r3"],7,5.2)
    lines(c,x_bot,y0-6,['Bottle designer review - revision 3','projected master, 108 mm convention at 1:2','spec '+a['product_spec_hash'][:12]],7,5.2)
    checks=d['checks'];fid=d['fidelity']
    if checks is None:check_text='Checks: pending (render/checks/checks.json absent at build time).'
    else:
        h=checks['copy_edits']['header-edit'];b=checks['copy_edits']['bottle-edit'];neg='fails as required' if not checks['uv']['uv-mirrored-negative']['passed'] else 'PASSES - instrument defect'
        check_text=f"Checks {verdict_word(checks['passed'])}: header SUN->NEW {h['changed_pixels']} px changed, {h['outside_surface_pixels']} outside its region; bottle SUN->NEW {b['changed_pixels']} px, {b['outside_surface_pixels']} outside; UV positive {verdict_word(checks['uv']['uv-positive']['passed'])}; mirrored negative {neg}."
    fidelity_text='Fidelity summary: pending (builder B1); page 2 prints fidelity: pending.'
    if fid is not None:fidelity_text=f"Fidelity summary present: measured faces passed = {fid['measured_faces_passed']}; all categories passed = {fid['family_all_categories_passed']}; see page 2."
    notes=['ONE PAGE SCALE 1:2 for all three panels; both bars below.',f"Geometry {a['realised_envelope_mm'][0]} x {a['realised_envelope_mm'][1]} x {a['realised_envelope_mm'][2]} mm; rise {a['rise']}; seats {a['seats']}; header {a['header_height']}; Day 4 revision 2 geometry unchanged (plain rectangular header).",
      f"Assembly revision {a['revision']} ({det['pins']['assembly_sha256'][:12]}) pinned to bottle r3 and the seven D1 surfaces of revision {d['revision']} (bindings {a['artwork_binding']['bindings_sha256'][:12]}).",*superseded_notes(d),f"Sightlines D-D4-1: pass point 550/500 {verdict_word(s['pass_point']['result']['passed'])}; median 650/650 {verdict_word(s['median']['result']['passed'])}; secondary 350/500 {'certified' if s['secondary']['result']['passed'] else 'not certified'}; far advisory 550/800 {'certified' if s['far_advisory']['result']['passed'] else 'not certified'} (both reported, not certified); {'identical to Day 4 at every point.' if d['sightlines']['day4_comparison']['all_identical'] else 'DIFFERS FROM DAY 4 - see sightlines.json.'}",
      f"Render: two runs, decoded pixels {'identical' if det['decoded_pixels_identical'] else 'DIFFER'} for four views; saved-scene census {len(d['census']['bottle_roots'])} visible bottles.",check_text,fidelity_text,'Status: designer review; construction provisional, not fabrication approval; press profile unconfirmed; materials are an approximation, not supplier stock.']
    y=y0+h_ren-4
    for note in notes:y=lines(c,x_bot+w_bot+8,y,wrap(note,NOTE_WIDTH),6.8,4.6)-1.5
    bar(c,14,22);scaled_bar(c,110,22,SCALE);c.showPage()
    return {'picture':pic,'render':ren,'panel_mm':{'picture':[w_pic,h_pic],'render':[w_ren,h_ren],'bottle':[w_bot,h_bot]}}


def superseded_notes(d):
    sup=d['superseded']
    if sup is None:return []
    text='Revision 1 is retained as the superseded attempt (surfaces/, render/).'
    if sup['fidelity'] is not None and d['fidelity'] is not None:
        old=fidelity_row(sup['fidelity'],'header.front');new=fidelity_row(d['fidelity'],'header.front')
        if old is not None and new is not None:text=f"Revision 1 retained as the superseded attempt: header gesture {old['gesture_max_mm']:.2f} mm {old['gesture']} -> revision 2 {new['gesture_max_mm']:.2f} mm {new['gesture']}."
    return [text]


def superseded_block(c,d,y):
    sup=d['superseded']
    if sup is None:return y
    words(c,14,y,'Superseded attempt - surfaces revision 1 (docs/audit/day-6/stand/surfaces, render in render/), replaced by revision 2 on the measured centreline',8);y-=6
    for t in wrap('Correction (surface-bindings.json revision 2): '+sup['correction'],185):words(c,14,y,t,6.5);y-=4.6
    if sup['fidelity'] is None or d['fidelity'] is None:words(c,14,y,'fidelity comparison: pending (a fidelity-summary.json is absent)',6.5);return y-6
    rows=[]
    for sid in SURFACES:
        old=fidelity_row(sup['fidelity'],sid);new=fidelity_row(d['fidelity'],sid)
        if old is None or new is None or not isinstance(old['gesture_max_mm'],(int,float)) and not isinstance(old['field_delta_e_max'],(int,float)):continue
        rows.append(f"{sid}: gesture {cell(old,'gesture',('gesture_max_mm',),{'gesture_max_mm':'{:.2f}mm'})} -> {cell(new,'gesture',('gesture_max_mm',),{'gesture_max_mm':'{:.2f}mm'})}; field {cell(old,'field',('field_delta_e_max',),{'field_delta_e_max':'dE{:.1f}'})} -> {cell(new,'field',('field_delta_e_max',),{'field_delta_e_max':'dE{:.1f}'})}; measured fidelity {old['measured_fidelity_passed']} -> {new['measured_fidelity_passed']}")
    rows.append(f"measured faces passed: {sup['fidelity']['measured_faces_passed']} -> {d['fidelity']['measured_faces_passed']}; family all categories: {sup['fidelity']['family_all_categories_passed']} -> {d['fidelity']['family_all_categories_passed']}. Field-colour FAILs are unchanged by the pose correction and stay reported.")
    for t in rows:words(c,14,y,t,6.5);y-=4.6
    return y-2


def page_two(c,d):
    m=d['measurement'];b={s['surface_id']:s for s in d['bindings']['surfaces']};faces={f['surface_id']:f for f in m['faces']};fid=d['fidelity']
    heading(c,f"Per-surface table and deviation list / D1 mapped onto the real stand - surfaces revision {d['revision']}",f"status from concept-D1-measurement.json; source_status and hashes from {d['surfaces'].name}/surface-bindings.json; fidelity categories from {d['surfaces'].name}/fidelity-summary.json"+('' if fid is not None else ' (absent at build time: pending)'),*A3)
    y=262;cols=[(14,'surface'),(40,'size mm'),(58,'status (measurement)'),(136,'source_status (bindings)'),(214,'spec hash'),(236,'pdf sha'),(258,'placement'),(292,'ink'),(312,'field'),(340,'gesture'),(364,'grammar'),(380,'continuity'),(398,'measured')]
    for x,t in cols:words(c,x,y,t,6.5)
    y-=7
    for sid in SURFACES:
        f=faces[sid];s=b[sid];cells=fidelity_cells(fid,sid)
        row=[(14,sid),(40,f"{f['size_mm'][0]} x {f['size_mm'][1]}"),(58,f['status']),(136,s['source_status']),(214,s['spec_hash'][:10]),(236,s['pdf_sha256'][:10])]+list(zip([258,292,312,340,364,380,398],cells))
        for x,t in row:words(c,x,y,t,6.5)
        y-=7.5
    y-=3
    if fid is not None:
        t=fid['thresholds'];summary=[f"Bars (never moved): {t['wording'].replace(chr(8804),'<=')}",f"Measured faces passed: {fid['measured_faces_passed']}; family all categories passed: {fid['family_all_categories_passed']}; review_state {fid['review_state']}. {fid['reading']}"]
        for seam in fid['seams']:
            scalars=[f"{k}={v:.2f}" if isinstance(v,float) else f"{k}={v}" for k,v in seam.items() if isinstance(v,(bool,int,float,str)) and k not in ('seam',)]
            summary.append(f"seam {seam['seam']}: "+', '.join(scalars))
        for line in summary:
            for t in wrap(line,185):words(c,14,y,t,6.5);y-=4.6
            y-=1
    else:words(c,14,y,'fidelity: pending - fidelity-summary.json was absent when this sheet was built; rebuild with day6_presentation.build() once it exists.',7);y-=6
    y=superseded_block(c,d,y-2)
    y-=4;words(c,14,y,'Deviation list - the solved geometry wins; each difference from the picture is recorded per face (concept-D1-measurement.json faces[].deviations)',8);y-=7
    for sid in SURFACES:
        for dev in faces[sid]['deviations']:
            for i,t in enumerate(wrap(dev,170)):
                prefix=sid+' - '
                if i:prefix='    '
                words(c,14,y,prefix+t,7);y-=5
        y-=1.5
    y-=3
    for t in [m['shared_device_colours'],m['uncertainty_note'],'Required header copy (live, per-glyph): SUN / REPAIR / SERUM / Arabic line / Revive + Smooth. Picture count 8; geometry count 12.']:words(c,14,y,t,7);y-=5
    bar(c,14,16);c.showPage()


def page_surface(c,d,sid,size,y_top,enlarge):
    s=next(x for x in d['bindings']['surfaces'] if x['surface_id']==sid);f=next(x for x in d['measurement']['faces'] if x['surface_id']==sid);w,h=size;index=PAGE_INDEX[sid]
    heading(c,f"{sid} at 1:1 - {w} x {h} mm - surfaces revision {d['revision']}",'print at 100%, disable Fit; live type, parametric field, vector device; designer review',*A3)
    x=20;y=y_top-h;c.setStrokeColorRGB(.15,.2,.22);c.setLineWidth(.3);c.rect(x*mm,y*mm,w*mm,h*mm,fill=0,stroke=1)
    placements=[(index,[x,y,w,h])];note_y=y-8
    if enlarge is not None:
        ex,ey,ew,eh=20,y-16-h*enlarge,w*enlarge,h*enlarge;c.rect(ex*mm,ey*mm,ew*mm,eh*mm,fill=0,stroke=1);words(c,ex,ey-5,f'{enlarge}x enlargement for reading - NOT 1:1',7);placements.append((index,[ex,ey,ew,eh]));note_y=ey-12
    fidelity=fidelity_cells(d['fidelity'],sid)
    lines(c,20,note_y,[f"status: {f['status']}; source_status: {s['source_status']}",f"spec hash {s['spec_hash'][:16]}; pdf sha {s['pdf_sha256'][:16]}; texture at 300 PPI in the render",'fidelity: placement '+fidelity[0]+'; ink '+fidelity[1]+'; field '+fidelity[2]+'; gesture '+fidelity[3]+'; grammar '+fidelity[4]+'; continuity '+fidelity[5]+'; measured fidelity '+fidelity[6],'; '.join(f['deviations'])[:190]],7,5.2)
    bar(c,20,note_y-30);c.showPage();return placements


def overlay(out,placements,surfaces):
    """Place the actual vector artwork pages at their exact rects (fitz, top-left origin)."""
    with fitz.open(out) as doc:
        for sid,pages in placements.items():
            with fitz.open(surfaces/sid/'artwork.pdf') as art:
                for index,(x,y,w,h) in pages:doc[index].show_pdf_page(fitz.Rect(x*MM,(A3[1]-y-h)*MM,(x+w)*MM,(A3[1]-y)*MM),art,0)
        tmp=out.with_suffix('.tmp.pdf');doc.save(tmp)
    tmp.replace(out)


def render_review(d):
    out=d['render']/'render-review.pdf';c=Canvas(str(out),pagesize=(A4[0]*mm,A4[1]*mm));det=d['determinism']
    for view in d['cfg']['views']:
        heading(c,'Twelve-bottle stand / D1 Amber Current / '+view,f"Blender 4.5.12 LTS - deterministic material approximation; surfaces revision {d['revision']}, bottle r3; designer review")
        image_on(c,d['render']/'published'/f'{view}.png',15,28,180,240.03)
        words(c,14,23,f"Scene bar represents 50 mm; scaled perspective, image is not life-size. Two runs identical: {det['raw_hashes']['verified-run-1'][view]['pixels_sha256'][:16]}",7)
        bar(c,14,13);words(c,80,13,'Print calibration only: 100%, disable Fit.',7);c.showPage()
    c.save();render_pdf(out);return out


def build(surfaces_revision):
    """The current surfaces revision writes presentation.pdf; any other revision writes presentation-r<N>.pdf."""
    setup();d=inputs(surfaces_revision);stem='presentation' if surfaces_revision==CURRENT else f'presentation-r{surfaces_revision}';out=ROOT/(stem+'.pdf');c=Canvas(str(out),pagesize=(A3[0]*mm,A3[1]*mm))
    geometry=page_one(c,d);page_two(c,d);placements={'header.front':page_surface(c,d,'header.front',(180,100),250,None),'riser.1.front':page_surface(c,d,'riser.1.front',(180,6),250,2)}
    c.save();overlay(out,placements,d['surfaces']);render_pdf(out,160);fidelity=fidelity_path(surfaces_revision)
    # Only the current revision rewrites its render-review; a retained revision's render folder stays untouched.
    review=render_review(d) if surfaces_revision==CURRENT else d['render']/'render-review.pdf'
    manifest={'schema':'day6_presentation/1','surfaces_revision':surfaces_revision,'current_surfaces_revision':CURRENT,'page_scale':SCALE,'pages':['one scale: D1 picture | deterministic front render | bottle r3','per-surface table, fidelity categories and deviation list','header.front 1:1 with 50 mm bar','riser.1.front 1:1 with 50 mm bar and 2x reading enlargement'],'geometry':geometry,
      'fidelity_summary':{'path':str(fidelity),'present':d['fidelity'] is not None,'sha256':fa.sha(fidelity) if fidelity.exists() else None,'schema_recognised':fidelity_row(d['fidelity'],'header.front') is not None},'checks_present':d['checks'] is not None,
      'superseded_attempt':None if d['superseded'] is None else {'surfaces_revision':1,'fidelity_present':d['superseded']['fidelity'] is not None},
      'inputs':{'d1_picture_sha256':fa.sha(D1),'bottle_projected_master_sha256':fa.sha(BOTTLE),'assembly_sha256':fa.sha(d6.profile(surfaces_revision)['assembly']),'determinism_sha256':fa.sha(d['render']/'determinism.json'),'measurement_sha256':fa.sha(d6.MEASUREMENT),'bindings_sha256':fa.sha(d['surfaces']/'surface-bindings.json')},
      'outputs':{'presentation_pdf':str(out),'presentation_pdf_sha256':fa.sha(out),'render_review_pdf':str(review),'render_review_pdf_sha256':fa.sha(review)}}
    (ROOT/(stem+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n');return manifest

if __name__=='__main__':
    import sys
    print(json.dumps(build(int(sys.argv[1])),indent=2))
