"""Pinned scene contract and local Blender launcher. No AI geometry."""
from pathlib import Path
import json,hashlib,subprocess,copy,math
import fitz
from PIL import Image
from . import fidelity_assets as fa,fidelity_master as fm,day5_master as dm
BLENDER=Path('/Users/symow/Applications/Blender-4.5.12-LTS.app/Contents/MacOS/Blender')
SCRIPT=Path(__file__).parent/'blender_scripts/day5_display.py'

def validate_count(roots,positions):
    expected={x['id']:x['xyz'] for x in positions}
    if len(roots)!=12 or len({r['id'] for r in roots})!=12:raise ValueError('Exactly12 unique visible bottle roots required.')
    for r in roots:
        if len(r.get('xyz',[]))!=3 or not all(math.isfinite(float(v)) for v in r['xyz']):raise ValueError('Bottle transform needs three finite coordinates.')
        # Blender stores transforms as float32;0.0001mm bounds representation error.
        if r['id'] not in expected or r.get('hidden') or any(abs(a-b)>1e-4 for a,b in zip(r['xyz'],expected[r['id']])):raise ValueError('Bottle scene differs from assembly positions.')
    return True

def validate_visible_bodies(roots,positions):
    validate_count(roots,positions)
    for root in roots:
        children={c['component']:c for c in root.get('children',[])}
        for name in ['glass-fill','collar','cap','body.front']:
            item=children.get(name)
            if not item or item.get('hidden') or item.get('vertices',0)<=0 or item.get('faces',0)<=0:
                raise ValueError('Every counted bottle needs its visible nonempty body,collar,cap and artwork meshes.')
    return True

def source_preflight(cfg):
    if fm.digest(cfg['bottle_spec'])!=cfg['bottle_spec_hash']:raise ValueError('Bottle specification pin changed.')
    paths=[(cfg['bottle_texture'],cfg['bottle_texture_sha256'])]+[(s['texture'],s['texture_sha256']) for s in cfg['surfaces']]
    for path,expected in paths:
        if fa.sha(Path(path))!=expected:raise ValueError('A texture changed before Blender opened it.')
    return True

def prepare(destination):
    p=Path(destination);p.mkdir(exist_ok=False,parents=True);textures=p/'textures';textures.mkdir()
    assembly_path=fa.ROOT/'docs/audit/day-4/stand-family/assembly-spec.json';assembly=json.loads(assembly_path.read_text())
    spec=json.loads((dm.ROOT/'master/design-spec.json').read_text());dm.validate_spec(spec)
    source=fa.ROOT/'docs/audit/day-4/stand-family/surfaces';bindings=json.loads((source/'surface-bindings.json').read_text());surfaces=[]
    for s in bindings['surfaces']:
        pdf=source/(s['surface_id']+'.pdf');png=textures/(s['surface_id']+'.png')
        with fitz.open(pdf) as doc:doc[0].get_pixmap(dpi=300,alpha=False).save(png)
        surfaces.append(dict(s,texture=str(png),texture_sha256=fa.sha(png),pdf_sha256=fa.sha(pdf)))
    cfg={'schema':'day5_scene/1','assembly':assembly,'assembly_sha256':fa.sha(assembly_path),'assembly_proposed_envelope_mm':[180,150,322],'bottle_spec':spec,'bottle_spec_hash':fm.digest(spec),'bottle_texture':str(dm.ROOT/'master/artwork-linear-proof-texture.png'),'bottle_texture_sha256':fa.sha(dm.ROOT/'master/artwork-linear-proof-texture.png'),'surfaces':surfaces,'stand_artwork_revision':2,'bottle_revision':3,'label':'deterministic material approximation','construction_status':'provisional, not fabrication approval','shoulder_uv':'nominal angular mapping across0.549818mm shoulder overlap; unverified conformity','resolution':[2126,2835],'ppi':300,'placement_mm':[180.0013,240.03],'samples':16,'seed':0,'views':['front','median','three-quarter','plan-front'],'output':str(p/'run-1'),'blender_version':'4.5.12 LTS','script_sha256':fa.sha(SCRIPT)}
    (p/'scene-config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n');return cfg

def render(config,run='run-1',*,views=None,diagnostic=False):
    config=Path(config);cfg=json.loads(config.read_text());cfg['output']=str(config.parent/run)
    cfg['script_sha256']=fa.sha(SCRIPT)
    source_preflight(cfg)
    if views is not None:cfg['views']=views
    cfg['diagnostic']=diagnostic;folder=Path(cfg['output']);folder.mkdir(exist_ok=False)
    call=folder/'input.json';call.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
    with (folder/'blender.log').open('w') as log:
        result=subprocess.run([str(BLENDER),'-b','--factory-startup','-noaudio','-t','6','-P',str(SCRIPT),'--',str(call)],stdout=log,stderr=subprocess.STDOUT)
    if result.returncode or not (folder/'scene-manifest.json').exists():raise RuntimeError(f'Blender failed; inspect{folder}/blender.log')
    manifest=json.loads((folder/'scene-manifest.json').read_text());validate_count(manifest['bottle_roots'],cfg['assembly']['positions'])
    hashes={}
    for view in cfg['views']:
        image=folder/(view+'.png');im=Image.open(image).convert('RGB');hashes[view]={'file_sha256':fa.sha(image),'pixels_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'size':list(im.size)}
    (folder/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n');return hashes

def publish(config):
    from PIL import ImageDraw,ImageFont
    cfg=json.loads(Path(config).read_text());root=Path(config).parent;results={};font=ImageFont.truetype(str(fm.FONTS['symbol']),26)
    for run in ['verified-run-1','verified-run-2']:
        folder=root/run;pub=folder/'normalized';pub.mkdir(exist_ok=True);rows={}
        for view in cfg['views']:
            source=Image.open(folder/(view+'.png')).convert('RGB');im=Image.frombytes('RGB',source.size,source.tobytes());d=ImageDraw.Draw(im)
            d.text((35,12),'DETERMINISTIC MATERIAL APPROXIMATION / '+view.upper(),font=font,fill=(24,28,31))
            d.text((35,im.height-42),'Scene bar represents50mm; scaled perspective, image is not life-size',font=font,fill=(24,28,31))
            path=pub/(view+'.png');im.save(path,dpi=(300,300),compress_level=9)
            rows[view]={'file_sha256':fa.sha(path),'pixels_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'dpi':Image.open(path).info['dpi']}
        results[run]=rows
    matches={v:results['verified-run-1'][v]==results['verified-run-2'][v] for v in cfg['views']}
    if not all(matches.values()):raise ValueError('Normalized two-run images differ.')
    published=root/'published';published.mkdir(exist_ok=True)
    import shutil
    for view in cfg['views']:shutil.copyfile(root/'verified-run-1/normalized'/f'{view}.png',published/f'{view}.png')
    current=json.loads((dm.ROOT/'master/design-spec.json').read_text());old=cfg['bottle_spec']
    # Only the2Dpresentation shell changed; actual flat art/profile are identical.
    if current['graph']!=old['graph'] or current['elevation_proposal']!=old['elevation_proposal'] or fa.sha(Path(cfg['bottle_texture']))!=cfg['bottle_texture_sha256']:raise ValueError('Repinning would change rendered geometry/artwork; rerender required.')
    report={'blender_version':cfg['blender_version'],'decoded_pixels_identical':True,'normalized_files_identical':matches,'runs':results,'raw_hashes':{run:json.loads((root/run/'hashes.json').read_text()) for run in results},'initial_product_spec_hash':cfg['bottle_spec_hash'],'current_product_spec_hash':fm.digest(current),'repin_basis':'Only2Dpresentation-shell policy changed; flat graph,profile and texture bytes identical. Render pixels remain authoritative for the same artwork.','stand_artwork_revision':2,'bottle_revision':3,'ppi':300,'metadata_reason':'RawPNG contains date,file path and render timing; normalized files strip volatile metadata and add captions.'}
    (root/'determinism.json').write_text(json.dumps(report,indent=2)+'\n');return report

def inspect_saved_scene(config):
    cfg=json.loads(Path(config).read_text());root=Path(config).parent;script=SCRIPT.parent/'day5_inspect.py';output=root/'actual-scene-census.json'
    log=root/'scene-inspection.log'
    with log.open('w') as f:
        r=subprocess.run([str(BLENDER),'-b',str(root/'verified-run-1/display.blend'),'-P',str(script),'--',str(output)],stdout=f,stderr=subprocess.STDOUT)
    if r.returncode or not output.exists():raise RuntimeError('Savedscene inspection failed.')
    result=json.loads(output.read_text());validate_visible_bodies(result['bottle_roots'],cfg['assembly']['positions']);result['passed']=True;result['coordinate_tolerance_mm']=.0001;result['scene_sha256']=fa.sha(root/'verified-run-1/display.blend');output.write_text(json.dumps(result,indent=2)+'\n');return result
