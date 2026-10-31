"""Day 6 deterministic scene: the Day 6 assembly, the seven D1 surfaces of a named
surfaces revision and the revision-3 bottle through the pinned Day 5 Blender launcher
and frozen script. Pins are recorded as used; nothing is re-pinned afterwards.
Surfaces revision 1 (render/) is the retained attempt; revision 2 (render-r2/) carries
the corrected device pose. No AI geometry."""
from pathlib import Path
import datetime,hashlib,json,re,shutil,time
import fitz
from PIL import Image,ImageDraw,ImageFont
from . import fidelity_assets as fa,fidelity_master as fm,day5_master as dm,day5_scene as ds

ROOT=fa.ROOT/'docs/audit/day-6/stand'
RENDER=ROOT/'render'
ASSEMBLY=ROOT/'assembly-spec.json'
BINDINGS=ROOT/'surfaces/surface-bindings.json'
MEASUREMENT=fa.ROOT/'docs/audit/day-6/concept-D1-measurement.json'
SCRIPT=ds.SCRIPT
VIEWS=['front','median','three-quarter','plan-front']
RUNS=['verified-run-1','verified-run-2']
THREADS=6
PIN_KEYS=('assembly_sha256','bottle_spec_hash','bottle_texture_sha256','script_sha256','samples','seed','resolution')
CURRENT_SURFACES_REVISION=2
PROFILES={1:{'assembly':ASSEMBLY,'surfaces':ROOT/'surfaces','render':RENDER,'stand_artwork_revision':3,'assembly_revision':3},
          2:{'assembly':ROOT/'assembly-spec-r2.json','surfaces':ROOT/'surfaces-r2','render':ROOT/'render-r2','stand_artwork_revision':4,'assembly_revision':4}}
REVISION_NOTE='stand_artwork_revision counts stand artwork generations: Day 4 surfaces = 2; Day 6 surfaces revision 1 = 3 (render/); Day 6 surfaces revision 2 = 4 (render-r2/).'


def profile(surfaces_revision):
    if surfaces_revision not in PROFILES:raise ValueError('Unknown surfaces revision.')
    return PROFILES[surfaces_revision]


def prepare(destination,surfaces_revision):
    """Scene config from the Day 6 assembly pinned to this surfaces revision and its seven artwork PDFs at 300 PPI."""
    pr=profile(surfaces_revision);p=Path(destination);p.mkdir(exist_ok=False,parents=True);textures=p/'textures';textures.mkdir()
    assembly=json.loads(pr['assembly'].read_text());bindings_path=pr['surfaces']/'surface-bindings.json';bindings=json.loads(bindings_path.read_text())
    if assembly['revision']!=pr['assembly_revision'] or assembly['product_revision']!=3 or assembly['case_id']!='family':raise ValueError('The Day 6 family assembly of this surfaces revision is required.')
    spec=json.loads((dm.ROOT/'master/design-spec.json').read_text());dm.validate_spec(spec)
    if fm.digest(spec)!=assembly['product_spec_hash']:raise ValueError('Assembly product pin differs from the revision-3 bottle spec.')
    if fa.sha(bindings_path)!=assembly['artwork_binding']['bindings_sha256']:raise ValueError('surface-bindings.json differs from the one the assembly pinned.')
    # The revision-1 bindings predate the 'revision' field; every later bindings file carries it.
    bound_revision=1
    if 'revision' in bindings:bound_revision=bindings['revision']
    if bound_revision!=surfaces_revision:raise ValueError('The bindings file is not this surfaces revision.')
    measurement=json.loads(MEASUREMENT.read_text());surfaces=[]
    for s in bindings['surfaces']:
        folder=pr['surfaces']/s['surface_id'];pdf=folder/'artwork.pdf';png=textures/(s['surface_id']+'.png')
        if fa.sha(pdf)!=s['pdf_sha256']:raise ValueError(s['surface_id']+': artwork.pdf differs from surface-bindings.json.')
        with fitz.open(pdf) as doc:
            page=doc[0];size=[page.rect.width/72*25.4,page.rect.height/72*25.4]
            if len(doc)!=1 or any(abs(a-b)>.01 for a,b in zip(size,s['size_mm'])):raise ValueError(s['surface_id']+': PDF page size differs from the bound surface size.')
            page.get_pixmap(dpi=300,alpha=False).save(png)
        header=s['surface_id']=='header.front'
        surfaces.append({'surface_id':s['surface_id'],'size_mm':s['size_mm'],'spec_hash':s['spec_hash'],'source_status':s['source_status'],'review_state':bindings['review_state'],'pdf':str(pdf),'pdf_sha256':fa.sha(pdf),
          'texture':str(png),'texture_sha256':fa.sha(png),'texture_px':list(Image.open(png).size),'texture_ppi':300,'required_copy':list(measurement['required_header_copy']) if header else [],'languages':['EN','AR'] if header else []})
    bottle_texture=dm.ROOT/'master/artwork-linear-proof-texture.png'
    cfg={'schema':'day6_scene/1','assembly':assembly,'assembly_sha256':fa.sha(pr['assembly']),'assembly_revision':assembly['revision'],'assembly_proposed_envelope_mm':assembly['realised_envelope_mm'],'bottle_spec':spec,'bottle_spec_hash':fm.digest(spec),
      'bottle_texture':str(bottle_texture),'bottle_texture_sha256':fa.sha(bottle_texture),'surfaces':surfaces,'surfaces_revision':surfaces_revision,'surfaces_root':str(pr['surfaces']),'bindings_sha256':fa.sha(bindings_path),
      'stand_artwork_revision':pr['stand_artwork_revision'],'stand_artwork_revision_note':REVISION_NOTE,'stand_artwork_source':f'Day 6 D1 Amber Current surfaces revision {surfaces_revision}, {pr["surfaces"].relative_to(fa.ROOT)} (D-D6-1, D-D6-2)',
      'bottle_revision':3,'measurement_sha256':fa.sha(MEASUREMENT),'label':'deterministic material approximation','construction_status':'provisional, not fabrication approval',
      'shoulder_uv':'nominal angular mapping across0.549818mm shoulder overlap; unverified conformity','resolution':[2126,2835],'ppi':300,'placement_mm':[180.0013,240.03],'samples':32,'seed':0,'views':list(VIEWS),
      'output':str(p/RUNS[0]),'blender':str(ds.BLENDER),'blender_version':'4.5.12 LTS','threads':THREADS,'script':str(SCRIPT),'script_sha256':fa.sha(SCRIPT)}
    (p/'scene-config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n');return cfg


def view_times(log):
    """Per-view render seconds from Blender's own 'Saved ... Time: mm:ss.ss' lines."""
    times={}
    for path,minutes,seconds in re.findall(r"Saved: '([^']+)'\s*\nTime: (\d+):(\d+\.\d+)",log):times[Path(path).stem]=round(int(minutes)*60+float(seconds),2)
    return times


def render(config,run,*,views=None,diagnostic=False):
    """Pinned Day 5 launcher (Blender -t 6, frozen script); wall-clock recorded beside the hashes."""
    started=datetime.datetime.now(datetime.timezone.utc);t=time.time()
    hashes=ds.render(config,run=run,views=views,diagnostic=diagnostic);wall=time.time()-t
    folder=Path(config).parent/run;times=view_times((folder/'blender.log').read_text())
    timing={'run':run,'threads':THREADS,'wall_clock_s':round(wall,1),'started_utc':started.isoformat(timespec='seconds'),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),'blender_view_seconds':times,'diagnostic':diagnostic}
    (folder/'timing.json').write_text(json.dumps(timing,indent=2)+'\n');return hashes


def publish(config):
    """Normalised captioned 300-PPI PNGs for both runs; decoded pixels must agree; run-1 is published."""
    cfg=json.loads(Path(config).read_text());root=Path(config).parent;font=ImageFont.truetype(str(fm.FONTS['symbol']),26);results={}
    for run in RUNS:
        folder=root/run;pub=folder/'normalized';pub.mkdir(exist_ok=False);rows={}
        for view in cfg['views']:
            source=Image.open(folder/(view+'.png')).convert('RGB');im=Image.frombytes('RGB',source.size,source.tobytes());d=ImageDraw.Draw(im)
            d.text((35,12),f"DETERMINISTIC MATERIAL APPROXIMATION / {view.upper()} / D1 AMBER CURRENT SURFACES R{cfg['surfaces_revision']} (STAND ARTWORK R{cfg['stand_artwork_revision']}) / BOTTLE R3",font=font,fill=(24,28,31))
            d.text((35,im.height-42),'Scene bar represents 50 mm; scaled perspective, image is not life-size. Designer review; construction provisional.',font=font,fill=(24,28,31))
            path=pub/(view+'.png');im.save(path,dpi=(300,300),compress_level=9)
            rows[view]={'file_sha256':fa.sha(path),'pixels_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'dpi':list(Image.open(path).info['dpi'])}
        results[run]=rows
    raw={run:json.loads((root/run/'hashes.json').read_text()) for run in RUNS};inputs={run:json.loads((root/run/'input.json').read_text()) for run in RUNS}
    manifests={run:json.loads((root/run/'scene-manifest.json').read_text()) for run in RUNS}
    decoded={v:raw[RUNS[0]][v]['pixels_sha256']==raw[RUNS[1]][v]['pixels_sha256'] for v in cfg['views']}
    normalized={v:results[RUNS[0]][v]==results[RUNS[1]][v] for v in cfg['views']}
    pins_identical=all(inputs[RUNS[0]][k]==inputs[RUNS[1]][k] for k in PIN_KEYS) and all(inputs[RUNS[0]][k]==cfg[k] for k in PIN_KEYS if k!='script_sha256')
    if not pins_identical:raise ValueError('The two runs were not rendered with the same pins.')
    if not all(decoded.values()):raise ValueError('Decoded pixels differ between the two runs: '+', '.join(v for v,ok in decoded.items() if not ok))
    if not all(normalized.values()):raise ValueError('Normalized two-run images differ.')
    published=root/'published';published.mkdir(exist_ok=False)
    for view in cfg['views']:shutil.copyfile(root/RUNS[0]/'normalized'/f'{view}.png',published/f'{view}.png')
    report={'schema':'day6_determinism/1','blender_version':manifests[RUNS[0]]['blender_version'],'blender_versions_identical':manifests[RUNS[0]]['blender_version']==manifests[RUNS[1]]['blender_version'],'decoded_pixels_identical':all(decoded.values()),
      'decoded_pixels_identical_by_view':decoded,'normalized_files_identical':normalized,'scene_manifests_identical':manifests[RUNS[0]]==manifests[RUNS[1]],'runs':results,'raw_hashes':raw,
      'pins':{'policy':'Recorded as used by both runs; nothing was re-pinned afterwards. A changed bottle, surface, assembly or script needs a new two-run render.','assembly_sha256':inputs[RUNS[0]]['assembly_sha256'],'assembly_revision':cfg['assembly_revision'],
        'product_spec_hash':inputs[RUNS[0]]['bottle_spec_hash'],'bottle_texture_sha256':inputs[RUNS[0]]['bottle_texture_sha256'],'script_sha256':inputs[RUNS[0]]['script_sha256'],'script':cfg['script'],'surfaces_revision':cfg['surfaces_revision'],'bindings_sha256':cfg['bindings_sha256'],
        'surfaces':[{k:s[k] for k in ('surface_id','spec_hash','pdf_sha256','texture_sha256','source_status')} for s in inputs[RUNS[0]]['surfaces']],'samples':cfg['samples'],'seed':cfg['seed'],'resolution':cfg['resolution'],'threads':THREADS},
      'stand_artwork_revision':cfg['stand_artwork_revision'],'stand_artwork_revision_note':REVISION_NOTE,'surfaces_revision':cfg['surfaces_revision'],'bottle_revision':3,'ppi':300,'timing':{run:json.loads((root/run/'timing.json').read_text()) for run in RUNS},
      'metadata_reason':'Raw PNG contains date, file path and render timing; normalized files strip volatile metadata and add captions.','label':cfg['label'],'construction_status':cfg['construction_status']}
    (root/'determinism.json').write_text(json.dumps(report,indent=2)+'\n');return report


def inspect_saved_scene(config):
    """Reopen verified-run-1/display.blend with the Day 5 inspector and count twelve visible bottles."""
    return ds.inspect_saved_scene(config)


if __name__=='__main__':
    import sys
    revision=int(sys.argv[2]);pr=profile(revision);cfg=pr['render']/'scene-config.json'
    if sys.argv[1]=='prepare':prepare(pr['render'],revision);print(json.dumps({'config':str(cfg),'script_sha256':fa.sha(SCRIPT)},indent=2))
    elif sys.argv[1]=='render':
        for run in sys.argv[3:]:print(run,json.dumps(render(cfg,run),indent=2),json.dumps(json.loads((pr['render']/run/'timing.json').read_text()),indent=2),flush=True)
    elif sys.argv[1]=='publish':print(json.dumps({k:v for k,v in publish(cfg).items() if k in ('decoded_pixels_identical','decoded_pixels_identical_by_view','normalized_files_identical','scene_manifests_identical')},indent=2))
    elif sys.argv[1]=='inspect':print(json.dumps({k:v for k,v in inspect_saved_scene(cfg).items() if k!='bottle_roots'},indent=2))
