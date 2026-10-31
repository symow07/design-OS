"""Day 6 assembly revision 3: the Day 4 family geometry (rise 54) pinned to the
revision-3 bottle and the seven D1-mapped surfaces, with the D-D4-1 sightlines
re-run and compared number-for-number against Day 4. No geometry is adjusted."""
from pathlib import Path
import copy,json,time
from apps.pipeline.services import fidelity_assets as fa,fidelity_master as fm,identity_assembly as ia
from apps.ire.identity_sightlines import evaluate

ROOT=fa.ROOT/'docs/audit/day-6/stand'
DAY4_ASSEMBLY=fa.ROOT/'docs/audit/day-4/stand-family/assembly-spec.json'
BOTTLE_SPEC=fa.ROOT/'docs/audit/day-5/master/design-spec.json'
BINDINGS=ROOT/'surfaces/surface-bindings.json'
MEASUREMENT=fa.ROOT/'docs/audit/day-6/concept-D1-measurement.json'
RISE=54
POINTS=[('pass_point',(550,500)),('median',(650,650)),('secondary',(350,500)),('far_advisory',(550,800))]
GEOMETRY_KEYS=('envelope','square','product_width','product_height','profile','identity','decoration','hole','thickness','header_height','rise','seats','tread','pitch','positions','stagger','required_height')
SURFACE_IDS=['header.front','riser.3.front','riser.2.front','lip.front','riser.1.front','side.left','side.right']


def geometry_digest(model):
    return fm.digest({k:model[k] for k in GEOMETRY_KEYS})


def revision3():
    """Revision 3 of the family model. Base: identity_assembly.model_at('family',54)."""
    for name,point in POINTS:
        if tuple(ia.INSTRUMENT[name])!=point:raise ValueError('Sightline points must be the D-D4-1 instrument points.')
    base=ia.model_at('family',RISE);parent=json.loads(DAY4_ASSEMBLY.read_text());bottle=json.loads(BOTTLE_SPEC.read_text());bindings=json.loads(BINDINGS.read_text())
    if parent['revision']!=2 or parent['case_id']!='family' or parent['rise']!=RISE:raise ValueError('Parent must be the Day 4 family revision 2 at rise 54.')
    if bottle['revision']!=3 or bottle['review_state']!='designer_review':raise ValueError('Bottle pin must be revision 3 in designer review.')
    if bindings['review_state']!='designer_review' or [s['surface_id'] for s in bindings['surfaces']]!=SURFACE_IDS:raise ValueError('Seven Day 6 surfaces in designer review are required.')
    for s in bindings['surfaces']:
        pdf=ROOT/'surfaces'/s['surface_id']/'artwork.pdf';spec=json.loads((ROOT/'surfaces'/s['surface_id']/'design-spec.json').read_text())
        if fa.sha(pdf)!=s['pdf_sha256'] or fm.digest(spec)!=s['spec_hash']:raise ValueError(s['surface_id']+': surface package differs from surface-bindings.json.')
    identity_differs=bottle['identity_zones']!=parent['identity'];decoration_differs=bottle['decoration_region_mm']!=parent['decoration'];profile_differs=bottle['elevation_proposal']['profile']!=parent['profile']
    model=dict(base,revision=3,parent_hash=fm.digest(parent),parent_file_sha256=fa.sha(DAY4_ASSEMBLY),product_spec_hash=fm.digest(bottle),product_revision=3,product_review_state=bottle['review_state'],
      identity=copy.deepcopy(bottle['identity_zones']),decoration=copy.deepcopy(bottle['decoration_region_mm']),profile=copy.deepcopy(bottle['elevation_proposal']['profile']))
    model.update(realised_envelope_mm=[model['envelope'][0],model['envelope'][1],model['required_height']],height_mm=model['required_height'],requested_height_mm=base['envelope'][2],
      requested_height_shortfall_mm=max(0,model['required_height']-base['envelope'][2]),about_height_passed=model['required_height']<=model['about_height_range_mm'][1],
      identity_source={'used':'revision 3 bottle spec identity_zones (docs/audit/day-5/master/design-spec.json)','differs_from_revision_2':identity_differs,'decoration_differs_from_revision_2':decoration_differs,'profile_differs_from_revision_2':profile_differs,
        'why':'The pinned product is revision 3, so its zones are the authority; they are byte-identical to revision 2 (same concept-147 measurement, parent chain 95abc4d3), so the sightline inputs are unchanged.' if not (identity_differs or decoration_differs or profile_differs) else 'The pinned product is revision 3; its zones differ from revision 2 and the sightlines below are evaluated on them.'},
      identity_authority='Measured concept147 fidelity revision 3 identity (logo, SUN, REPAIR, SERUM); same measurement as revision 2',
      artwork_binding={'schema':bindings['schema'],'review_state':bindings['review_state'],'bindings_sha256':fa.sha(BINDINGS),'measurement_sha256':fa.sha(MEASUREMENT),'source':'D1 Amber Current attempt 2, artwork only (D-D6-1, D-D6-2)',
        'surfaces':[{k:s[k] for k in ('surface_id','size_mm','spec_hash','pdf_sha256','source_status')} for s in bindings['surfaces']]},
      artwork_state='Day 6 D1-mapped surfaces, designer_review; direction accepted (D-D6-1), no file accepted',
      geometry_note="D1's header is a plain rectangle: the Day 4 revision-2 geometry (rise 54, seats 6/60/114, header 100, height 322) is unchanged; no geometry was adjusted for any check.",
      status='geometry_pinned_provisional',status_note="Rise 54 / height 322 is the Day 4 certified minimum under D-D4-1; exactly 300 stays 22 mm short (Day 4 status 'refused' for 300). Artwork and bottle remain designer review.")
    return model


def compare_with_day4(parent,results):
    """Number-for-number comparison with the Day 4 revision-2 sightlines."""
    report={};identical=True
    for name,_ in POINTS:
        old=parent['sightlines'][name];new=results[name];differences=[]
        if old['passed']!=new['passed']:differences.append(f"passed {old['passed']} -> {new['passed']}")
        for a,b in zip(old['rows'],new['rows']):
            for key in ('identity_passed','decoration_fraction_lower','decoration_fraction_upper'):
                if a[key]!=b[key]:differences.append(f"row {a['row']} {key} {a[key]} -> {b[key]}")
        for a,b in zip(old['bottles'],new['bottles']):
            if a['identity_passed']!=b['identity_passed']:differences.append(f"{a['bottle']} identity_passed {a['identity_passed']} -> {b['identity_passed']}")
            if a['decoration']['lower']!=b['decoration']['lower'] or a['decoration']['upper']!=b['decoration']['upper']:differences.append(f"{a['bottle']} decoration bounds differ")
        report[name]={'eye_above_base_mm':new['eye_above_base_mm'],'front_distance_mm':new['front_distance_mm'],'passed_day4':old['passed'],'passed_day6':new['passed'],'identical':not differences,'differences':differences,
          'rows_day6':[{k:r[k] for k in ('row','identity_passed','decoration_fraction_lower','decoration_fraction_upper')} for r in new['rows']]}
        identical=identical and not differences
    return {'all_identical':identical,'points':report}


def build(destination=ROOT):
    """Write assembly-spec.json and sightlines.json. Existing files are never overwritten."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);spec_path=destination/'assembly-spec.json';sight_path=destination/'sightlines.json'
    for p in (spec_path,sight_path):
        if p.exists():raise FileExistsError(f'{p} exists; Day 6 records are immutable once written.')
    model=revision3();parent=json.loads(DAY4_ASSEMBLY.read_text());plan=ia.plan_checks(model)
    if not plan['passed']:raise ValueError('Plan checks failed; sightlines are not evaluated on an invalid plan.')
    started=time.time();results={};seconds={}
    for name,(eye_z,distance) in POINTS:
        t=time.time();results[name]=evaluate(model,eye_z,distance);seconds[name]=round(time.time()-t,3)
    comparison=compare_with_day4(parent,results)
    sightlines={'schema':'day6_sightlines/1','instrument':copy.deepcopy(ia.INSTRUMENT),'assembly_revision':3,'geometry_digest':geometry_digest(model),'rise_mm':model['rise'],'seats_mm':model['seats'],'header_mm':model['header_height'],'height_mm':model['height_mm'],
      'plan_checks':plan,'points':{name:{'eye_above_base_mm':eye_z,'front_distance_mm':distance,'result':results[name]} for name,(eye_z,distance) in POINTS},
      'day4_comparison':dict(comparison,parent_file_sha256=fa.sha(DAY4_ASSEMBLY),parent_hash=fm.digest(parent)),'certification':{'pass_point':results['pass_point']['passed'],'median':results['median']['passed'],'secondary_reported':results['secondary']['passed'],'far_advisory_reported':results['far_advisory']['passed'],
      'law':ia.INSTRUMENT['pass_law'],'note':'The secondary and far-advisory cases are reported, not certified; no whole-band or lateral claim is made (Day 4 measured correction).'},
      'geometry_note':model['geometry_note'],'evaluation_seconds':dict(seconds,total=round(time.time()-started,3))}
    sight_path.write_text(json.dumps(sightlines,ensure_ascii=False,indent=2)+'\n')
    model.update(plan_checks=plan,sightlines={name:{'eye_above_base_mm':r['eye_above_base_mm'],'front_distance_mm':r['front_distance_mm'],'passed':r['passed'],'rows':r['rows']} for name,r in results.items()},
      sightlines_file='sightlines.json',sightlines_sha256=fa.sha(sight_path),sightlines_identical_to_day4=comparison['all_identical'],minimum_height_mm=model['required_height'] if results['pass_point']['passed'] else None)
    spec_path.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
    return {'assembly_spec':str(spec_path),'assembly_sha256':fa.sha(spec_path),'sightlines':str(sight_path),'comparison':comparison,'seconds':seconds}

ASSEMBLY_R1=ROOT/'assembly-spec.json'
BINDINGS_R2=ROOT/'surfaces-r2/surface-bindings.json'


def revision4():
    """Revision 4: revision 3's geometry and product pin unchanged; the artwork binding moves to
    surfaces revision 2 (device pose corrected onto the measured centreline). Revision 3 and
    surfaces revision 1 stay on disk as the retained attempt."""
    parent=json.loads(ASSEMBLY_R1.read_text());bindings=json.loads(BINDINGS_R2.read_text())
    if parent['revision']!=3 or parent['product_revision']!=3:raise ValueError('Revision 4 descends from the Day 6 revision-3 assembly.')
    if bindings['revision']!=2 or bindings['review_state']!='designer_review' or [s['surface_id'] for s in bindings['surfaces']]!=SURFACE_IDS:raise ValueError('Seven surfaces-r2 bindings (revision 2, designer review) are required.')
    if bindings['parent_bindings_sha256']!=parent['artwork_binding']['bindings_sha256']:raise ValueError('surfaces-r2 bindings do not descend from the revision-3 binding.')
    for s in bindings['surfaces']:
        folder=ROOT/'surfaces-r2'/s['surface_id'];spec=json.loads((folder/'design-spec.json').read_text())
        if fa.sha(folder/'artwork.pdf')!=s['pdf_sha256'] or fm.digest(spec)!=s['spec_hash'] or spec['revision']!=2:raise ValueError(s['surface_id']+': surfaces-r2 package differs from its bindings.')
    model=copy.deepcopy(parent)
    model.update(revision=4,parent_hash=fm.digest(parent),parent_file_sha256=fa.sha(ASSEMBLY_R1),supersedes='assembly-spec.json (revision 3; surfaces revision 1, retained attempt)',
      artwork_binding={'schema':bindings['schema'],'revision':bindings['revision'],'review_state':bindings['review_state'],'bindings_sha256':fa.sha(BINDINGS_R2),'parent_bindings_sha256':bindings['parent_bindings_sha256'],'correction':bindings['correction'],
        'surfaces_root':'docs/audit/day-6/stand/surfaces-r2','measurement_sha256':fa.sha(MEASUREMENT),'source':parent['artwork_binding']['source'],'surfaces':[{k:s[k] for k in ('surface_id','size_mm','spec_hash','pdf_sha256','source_status')} for s in bindings['surfaces']]},
      artwork_state='Day 6 D1-mapped surfaces revision 2 (corrected device pose), designer_review; revision 1 retained as the superseded attempt',
      sightlines_note='Geometry byte-identical to revision 3 (same geometry_digest); the revision-3 sightlines.json applies and is re-verified at build.')
    if geometry_digest(model)!=geometry_digest(parent):raise ValueError('Revision 4 must not change geometry.')
    return model


def build_r2(destination=ROOT):
    """Write assembly-spec-r2.json (revision 4). The revision-3 record and sightlines.json are never rewritten."""
    destination=Path(destination);path=destination/'assembly-spec-r2.json'
    if path.exists():raise FileExistsError(f'{path} exists; Day 6 records are immutable once written.')
    model=revision4();record=json.loads((destination/'sightlines.json').read_text())
    if record['geometry_digest']!=geometry_digest(model):raise ValueError('sightlines.json was evaluated on different geometry.')
    plan=ia.plan_checks(model)
    if not plan['passed']:raise ValueError('Plan checks failed.')
    reverified={name:evaluate(model,eye_z,distance)['passed'] for name,(eye_z,distance) in POINTS}
    if any(reverified[name]!=record['points'][name]['result']['passed'] for name,_ in POINTS):raise ValueError('Re-verified sightlines differ from sightlines.json.')
    model.update(plan_checks=plan,sightlines_reverified=reverified,sightlines_sha256=fa.sha(destination/'sightlines.json'))
    path.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
    return {'assembly_spec':str(path),'assembly_sha256':fa.sha(path),'revision':4,'parent_hash':model['parent_hash'],'sightlines_reverified':reverified}


if __name__=='__main__':
    import sys
    print(json.dumps(build_r2() if sys.argv[1:]==['r2'] else build(),indent=2))
