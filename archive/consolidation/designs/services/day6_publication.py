"""Day 6 publication: the D1-mapped stand, listed as it is on disk (present with its hash, or pending by name).

Re-runnable: ``build()`` reads every artifact the other Day 6 builders produce, records a sha256 for each one that
exists, names each one that does not yet exist as pending, and writes ``publication.json`` plus the review package.
Nothing is fabricated: an absent file never gets a hash, a binding whose hash disagrees with its file stops the build.
The day's surfaces are revision 2 (``stand/surfaces-r2``); revision 1 (``stand/surfaces``) is retained as history.
"""
from pathlib import Path
import json,mimetypes,zipfile
from . import day5_master as dm,fidelity_master as fm,fidelity_assets as fa

AUDIT=fa.ROOT/'docs/audit'
SCHEMA='day6_publication/1'
VIEWS=('front','median','three-quarter','plan-front')
SURFACES='stand/surfaces-r2';RENDER='stand/render-r2';TEXT='stand/text-audit-r2/TRACED_TEXT.json'
#: role, path relative to docs/audit/day-6 (``..`` reaches the immutable earlier days), plain words, page section
FIXED=[
 ('owner-pick','../day-5/concepts/D1/attempt-2/image.png','The owner’s pick: D1 Amber Current, attempt 2 (direction accepted, not a file)','presentation'),
 ('presentation','stand/presentation.pdf','Presentation sheet: D1 picture, deterministic render and bottle at one scale, per-surface tables, deviation list','presentation'),
 ('measurement','concept-D1-measurement.json','D1 measurement record','presentation'),
 ('measurement-addendum','concept-D1-measurement-addendum.json','D1 measurement addendum (header width profile)','presentation'),
 ('surface-bindings',SURFACES+'/surface-bindings.json','Surface bindings, revision 2: each surface to its artwork and record','surfaces'),
 ('field-fit',SURFACES+'/field-fit.json','Fitted field gradient','surfaces'),
 ('device-pose',SURFACES+'/device-pose.json','Device pose across the faces','surfaces'),
 ('fidelity-summary',SURFACES+'/fidelity-summary.json','Per-surface fidelity instrument summary','surfaces'),
 ('negative-control',SURFACES+'/negative-control-day4.json','Negative control: the Day 4 flat surfaces against D1','surfaces'),
 ('text-audit',TEXT,'Live-text audit of the stand package','surfaces'),
 ('assembly','stand/assembly-spec-r2.json','Assembly revision pinned to the bottle revision','render'),
 ('sightlines','stand/sightlines.json','Sightline check, re-run on the mapped stand','render'),
 ('render-review',RENDER+'/render-review.pdf','Four render views with print calibration','render'),
 ('render-determinism',RENDER+'/determinism.json','Two-run render hashes','render'),
 ('render-checks',RENDER+'/checks/checks.json','Render delta checks','render'),
 ('cut-layout','cut-layout/cut-layout.pdf','Cut layout at 1:1 with cut, crease, glue, artwork and dimension layers','cut'),
 ('cut-layout-artwork','cut-layout/cut-layout-with-artwork.pdf','Flat layout with the mapped artwork in place','cut'),
 ('bom','cut-layout/bom.json','Bill of materials','cut'),
 ('bom-csv','cut-layout/bom.csv','Bill of materials, spreadsheet','cut'),
 ('parts','cut-layout/parts.json','Parts list','cut'),
 ('native-compare','cut-layout/native-compare.json','Illustrator open-and-compare result','cut'),
 ('device','device/device.json','Vector brand device record: trace, colours, contour check, named deviation','device'),
 ('device-svg','device/device.svg','Vector brand device','device'),
 ('device-source-cream','../day-5/master/assets/swoosh-cream.png','Original matte, cream plane (the trace source)','device'),
 ('device-source-shadow','../day-5/master/assets/swoosh-shadow.png','Original matte, shadow plane (the trace source)','device'),
 ('revision-4-sheet','bottle/revision-4/comparison-at-100-percent.pdf','Bottle revision 4 sheet: vector device, real size, named deviation','bottle'),
 ('revision-4-page-1','bottle/revision-4/comparison-at-100-percent-page-1.png','Bottle revision 4 sheet, page 1','bottle'),
 ('revision-4-spec','bottle/revision-4/design-spec.json','Bottle revision 4 design record','bottle'),
 ('revision-4-fidelity','bottle/revision-4/fidelity-check.json','Bottle revision 4 fidelity check','bottle'),
 ('revision-4-text','bottle/revision-4/traced-text.json','Bottle revision 4 live-text audit','bottle'),
 ('revision-4-critic','bottle/revision-4/critic.json','Bottle revision 4 critic review','bottle'),
 ('library-inventory','library/inventory-summary.json','Library inventory totals','library'),
 ('library-migration','library/migration-proof.json','Migration proof','library'),
 ('library-reconciliation','library/post-migration-reconciliation.json','Post-migration reconciliation','library'),
 ('library-tree','library/tree.md','Tree note, shown for objection','library'),
 ('calibration','critic-calibration.json','Critic calibration point: the owner’s order beside the critic’s','history'),
 ('spend','spend.json','Spend record','history'),
]
FIXED[12:12]=[('render-'+v,RENDER+'/published/'+v+'.png','Render view: '+v.replace('-',' '),'render') for v in VIEWS]
SURFACE_FILES=[('pdf','artwork.pdf','Artwork PDF'),('png','artwork.png','Artwork picture'),('svg','artwork.svg','Artwork SVG'),
 ('spec','design-spec.json','Surface record'),('fidelity','fidelity-check.json','Fidelity check'),('native','artwork-native.ai','Native Illustrator file'),
 ('native-validation','artwork-native-validation.json','Native Illustrator validation'),('text','TRACED_TEXT.json','Live-text audit')]
#: revision 1, retained: listed only where its files exist, never awaited
REVISION_1=[('revision-1-bindings','stand/surfaces/surface-bindings.json','Revision 1 surface bindings'),
 ('revision-1-assembly','stand/assembly-spec.json','Revision 1 assembly record'),
 ('revision-1-render-review','stand/render/render-review.pdf','Revision 1 render views'),
 ('revision-1-determinism','stand/render/determinism.json','Revision 1 two-run render hashes')]
REVISION_1+=[('revision-1-render-'+v,'stand/render/published/'+v+'.png','Revision 1 render view: '+v.replace('-',' ')) for v in VIEWS]
MIME={'.md':'text/markdown','.ai':'application/postscript','.csv':'text/csv'}

def root(audit=AUDIT):return Path(audit)/'day-6'

def mime(path):
    return MIME.get(Path(path).suffix) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'

def load(path):
    return json.loads(Path(path).read_text()) if Path(path).is_file() else None

def surface_role(surface_id,kind,prefix='surface'):return prefix+'-'+surface_id.replace('.','-')+'-'+kind

def catalogue(audit=AUDIT):
    """Every artifact the page may show: (role, path relative to day-6, words, section), present or not."""
    base=root(audit);rows=list(FIXED)
    pages=sorted(base.glob('stand/presentation-page-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[1]))
    rows[2:2]=[('presentation-page-%d'%i,'stand/presentation-page-%d.png'%i,'Presentation sheet, page %d'%i,'presentation')
               for i in (range(1,len(pages)+1) if pages else (1,))]
    bindings=load(base/SURFACES/'surface-bindings.json')
    for s in (bindings or {}).get('surfaces',[]):
        for kind,name,words in SURFACE_FILES:
            rows.append((surface_role(s['surface_id'],kind),'%s/%s/%s'%(SURFACES,s['surface_id'],name),s['surface_id']+' · '+words,'surfaces'))
    rows+=[(role,rel,words,'history') for role,rel,words in REVISION_1 if (base/rel).is_file()]
    for critic in sorted(base.glob('stand/surfaces/*/critic.json')):
        rows.append((surface_role(critic.parent.name,'critic','revision-1'),str(critic.relative_to(base)),'Revision 1 critic review: '+critic.parent.name,'history'))
    return rows

def status(path,keys=('passed','measured_fidelity_passed')):
    """What a check record says, in one word: pending (no file), passed, failed, or present (no verdict field)."""
    data=load(path)
    if data is None:return 'pending'
    if isinstance(data,dict):
        for key in keys:
            if isinstance(data.get(key),bool):return 'passed' if data[key] else 'failed'
    return 'present'

def fidelity_row(summary,surface_id):
    rows=(summary or {}).get('rows') if isinstance(summary,dict) else None
    row=next((r for r in rows or [] if isinstance(r,dict) and r.get('surface_id')==surface_id),None)
    if row is None:return 'pending' if summary is None else 'present'
    word=lambda v:str(v).lower() if isinstance(v,str) else v
    return {'measured':row.get('measured'),'passed':row.get('measured_fidelity_passed'),'all_categories_passed':row.get('all_categories_passed'),
      'placement':word(row.get('placement')),'placement_worst_offset_mm':row.get('placement_worst_offset_mm'),'placement_worst_size_percent':row.get('placement_worst_size_percent'),
      'ink_colour':word(row.get('ink_colour')),'ink_delta_e_max':row.get('ink_delta_e_max'),'field':word(row.get('field')),'field_delta_e_max':row.get('field_delta_e_max'),
      'field_failing':row.get('field_failing'),'field_total':row.get('field_total'),'gesture':word(row.get('gesture')),'gesture_max_mm':row.get('gesture_max_mm'),
      'grammar':word(row.get('grammar')),'continuity':word(row.get('continuity'))}

def surfaces(audit=AUDIT):
    base=root(audit);bindings=load(base/SURFACES/'surface-bindings.json')
    if bindings is None:return []
    summary=load(base/SURFACES/'fidelity-summary.json');out=[]
    for s in bindings['surfaces']:
        folder=base/SURFACES/s['surface_id'];spec=load(folder/'design-spec.json')
        if not (folder/'artwork.pdf').is_file() or fa.sha(folder/'artwork.pdf')!=s['pdf_sha256']:raise ValueError('Surface binding disagrees with its artwork: '+s['surface_id'])
        if spec is None or fm.digest(spec)!=s['spec_hash']:raise ValueError('Surface binding disagrees with its record: '+s['surface_id'])
        lines=[{'text':l['logical_text'],'measured_bbox_mm':l.get('measured_bbox_mm'),'measured_baseline_mm':l.get('measured_baseline_y_mm'),
                'realized_baseline_mm':l.get('realized_baseline_y_mm'),'type_deviation':l.get('type_deviation')} for l in spec['graph'].get('lines',[])]
        out.append({'surface_id':s['surface_id'],'size_mm':s['size_mm'],'source_status':s['source_status'],'spec_hash':s['spec_hash'],
          'pdf_sha256':s['pdf_sha256'],'revision':spec.get('revision'),'deviations':spec.get('deviations',[]),'lines':lines,'fidelity':fidelity_row(summary,s['surface_id']),
          'native':status(folder/'artwork-native-validation.json'),'traced_text':status(folder/'TRACED_TEXT.json'),
          'roles':{kind:surface_role(s['surface_id'],kind) for kind,name,_ in SURFACE_FILES if (folder/name).is_file()}})
    return out

def library_totals(audit=AUDIT):
    base=root(audit)/'library';inv=load(base/'inventory-summary.json');proof=load(base/'migration-proof.json');rec=load(base/'post-migration-reconciliation.json')
    totals={'inventory':None,'migration':None,'reconciliation':None}
    if inv:totals['inventory']={'files':inv['file_count'],'bytes':inv['source_bytes'],'by_kind':inv['by_kind'],'duplicate_groups':inv['duplicate_groups'],
      'extra_duplicate_copies':inv['extra_duplicate_copies'],'owner_estimate':inv['expected_owner_count'],'materials_modified_by_census':inv['materials_modified']}
    if proof:totals['migration']={'state':proof['state'],'rollback_triggered':proof['rollback_triggered'],'moved':proof['moved'],
      'expected_count':proof['after']['expected_count'],'actual_count':proof['after']['actual_count'],'path_set_matches':proof['after']['path_set_matches'],
      'sha_multiset_matches':proof['after']['sha_multiset_matches'],'every_manifest_row_exact':proof['after']['every_manifest_row_exact'],
      'file_metadata_preserved':proof['file_metadata_preserved'],'directory_spelling':proof['directory_spelling']}
    if rec:totals['reconciliation']={'files_on_disk':rec['files_on_disk_excluding_tree_and_migration'],'manifest_rows':rec['manifest_rows'],
      'counts_match':rec['counts_match'],'per_folder_match':rec['per_folder_match'],'by_folder':rec['files_by_top_folder_on_disk'],
      'legacy_folders_still_holding_files':rec['legacy_top_folders_still_holding_files']}
    return totals

def history(audit=AUDIT,downloads=None):
    """Revision 1 of the surfaces, retained and superseded — described by revision 2's own record, never as the pick."""
    base=root(audit);r1=base/'stand/surfaces/surface-bindings.json';r2=load(base/SURFACES/'surface-bindings.json')
    if not r1.is_file():return {'revision_1':None}
    parent=(r2 or {}).get('parent_bindings_sha256')
    if parent and fa.sha(r1)!=parent:raise ValueError('Revision 2 names a parent that is not the retained revision 1.')
    summary=load(base/SURFACES/'fidelity-summary.json');header=fidelity_row(summary,'header.front')
    words='revision 1, superseded'
    if r2 and r2.get('correction'):words+=': '+r2['correction']
    if isinstance(header,dict) and isinstance(header.get('gesture_max_mm'),(int,float)):words+=' Revision 2 header gesture within %.2f mm.'%header['gesture_max_mm']
    roles=sorted(role for role in (downloads or {}) if role.startswith('revision-1-'))
    return {'revision_1':{'bindings_sha256':fa.sha(r1),'is_parent_of_revision_2':bool(parent),'words':words,'roles':roles}}

def collect(audit=AUDIT):
    """The record without writing anything: present artifacts with hashes, pending ones by expected file."""
    base=root(audit);spec=load(Path(audit)/'day-5/master/design-spec.json');dm.validate_spec(spec);pin=fm.digest(spec)
    downloads={};pending=[]
    for role,rel,words,section in catalogue(audit):
        path=base/rel
        if path.is_file():downloads[role]={'path':rel,'sha256':fa.sha(path),'mime':mime(path),'words':words,'section':section}
        else:pending.append({'role':role,'expected':rel,'words':words,'section':section})
    if 'owner-pick' not in downloads:raise ValueError('The owner’s pick is missing.')
    measurement=load(base/'concept-D1-measurement.json')
    if measurement and measurement['source_sha256']!=downloads['owner-pick']['sha256']:raise ValueError('The measurement was taken from another picture.')
    device=load(base/'device/device.json')
    if device:
        for role in device['roles']:
            source=downloads.get('device-source-'+role['role'].lower())
            if source is None or source['sha256']!=role['source_sha256']:raise ValueError('The device names a trace source that is not the retained matte.')
    for rel,words in [('stand/assembly-spec-r2.json','Day 6 assembly revision %s, pinned to bottle revision 3'),('stand/assembly-spec.json','Day 6 assembly revision %s (first attempt), pinned to bottle revision 3')]:
        assembly=base/rel
        if assembly.is_file():
            model=load(assembly)
            if model['product_spec_hash']!=pin:raise ValueError('The Day 6 assembly is not pinned to bottle revision 3.')
            assembly_source,assembly_words=rel,words%model['revision'];break
    else:
        assembly=Path(audit)/'day-4/stand-family/assembly-spec.json';assembly_source,assembly_words='../day-4/stand-family/assembly-spec.json','Day 4 assembly; the Day 6 revision is pending'
    r4=load(base/'bottle/revision-4/design-spec.json');sheet=downloads.get('revision-4-sheet');revision4=None
    if r4 or sheet:
        revision4={'spec_hash':fm.digest(r4) if r4 else None,'parent_hash':r4['parent_hash'] if r4 else None,'parent_is_revision_3':bool(r4) and r4['parent_hash']==pin,
          'review_state':(r4 or {}).get('review_state','designer_review'),'pinned':False,'sheet_sha256':sheet['sha256'] if sheet else None,
          'fidelity':status(base/'bottle/revision-4/fidelity-check.json',('measured_fidelity_passed',)),'traced_text':status(base/'bottle/revision-4/TRACED_TEXT.json' if (base/'bottle/revision-4/TRACED_TEXT.json').is_file() else base/'bottle/revision-4/traced-text.json'),
          'critic':'present' if 'revision-4-critic' in downloads else 'pending'}
    calibration=load(base/'critic-calibration.json');point=next((p for p in (calibration or {}).get('points',[]) if p.get('type')=='direction_ranking'),None)
    owner_pick={'id':'D1','name':'Amber Current','attempt':'attempt-2','image':downloads['owner-pick']['path'],'image_sha256':downloads['owner-pick']['sha256'],
      'decision':'D-D6-1: the direction is accepted, not any file; D-D6-2: the eight-bottle picture supplies artwork only',
      'owner_order':point['owner'] if point else None,'critic_order':point['critic'] if point else None,'critic_scores':point['critic_scores'] if point else None}
    return {'schema':SCHEMA,'owner_pick':owner_pick,'product_spec_hash':pin,'product_revision':3,'bottle_revision_4':revision4,
      'assembly_sha256':fa.sha(assembly),'assembly_source':assembly_source,'assembly_words':assembly_words,'surfaces':surfaces(audit),
      'surfaces_revision':2,'review_state':'designer_review','production_ready':False,'downloads':downloads,'pending':pending,
      'history':history(audit,downloads),'library_totals':library_totals(audit)}

def members(record,audit=AUDIT):
    """Files of the review package: every present artifact, each bound surface folder, the revision 4 folder."""
    base=root(audit);out={base/item['path'] for item in record['downloads'].values()}
    # Symlinks (the tessdata links of the text audits) are not package members: they point outside docs/audit.
    for s in record['surfaces']:out|={p for p in (base/SURFACES/s['surface_id']).rglob('*') if p.is_file() and not p.is_symlink()}
    out|={p for p in (base/'bottle/revision-4').rglob('*') if p.is_file() and not p.is_symlink()}
    return sorted(q for q in out if not q.is_symlink())

def build(audit=AUDIT):
    base=root(audit);record=collect(audit);package=base/'day6-review-package.zip';arcs=[];top=Path(audit).resolve()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for path in members(record,audit):
            arc=str(path.relative_to(top));arcs.append(arc)
            info=zipfile.ZipInfo(arc,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,path.read_bytes())            # fixed dates: the same files give the same package bytes
    record['package_members']=arcs
    record['downloads']['package']={'path':package.name,'sha256':fa.sha(package),'mime':'application/zip','words':'Review package of every present artifact','section':'presentation'}
    (base/'publication.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record
