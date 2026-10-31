"""Repackage existing measured Day4 artifacts; no generation or database mutation. Run with Django settings configured."""
from pathlib import Path
import json,shutil,zipfile
import numpy as np,cv2
from PIL import Image
from apps.pipeline.services import fidelity_master as fm
from apps.pipeline.services.identity_assembly import legacy_negative
import django
django.setup()
R=fm.fa.ROOT/'docs/audit/day-4';p=R/'master'
shutil.copyfile(fm.fa.CONCEPT,p/'concept-reference.png')
e=fm.PRESET;flat=np.asarray(Image.open(e/'swoosh-flat.png'));source=np.asarray(Image.open(e/'swoosh-source-matte.png'));material=np.asarray(Image.open(e/'material-field.png').convert('RGB'));support=np.asarray(Image.open(e/'swoosh-reference-support.png'))
ex=json.loads((e/'extraction.json').read_text());ex['source_resolution_roundtrip_ssim']=fm.fa.ssim(fm.fa.composite(material,source),fm.fa.composite(material,fm.fa.project(flat)),cv2.dilate(support,np.ones((7,7),np.uint8)));ex['projection_renderer']='premultiplied alpha, 2x supersample, area reduction';(e/'extraction.json').write_text(json.dumps(ex,indent=2)+'\n')
critic={'source_sha256':fm.fa.sha(p/'projected-master.png'),'flat_sha256':fm.fa.sha(p/'artwork.png'),'reviewer':'independent read-only visual_audit agent','scores':dict(zip(['composition','placement','scale','typography','colour','illustration','material_appearance','logo_identity','copy_completeness','overall_fidelity'],[9,9,8,8,8,6,9,10,10,8])),'mean':8.5,'critical_min':6,'passed':False,'review_state':'designer_review','observation':'Amber/brown ground fragments at upper swoosh tip, inner bend, lower outer curve are concealed by matching amber projection. Supporting faces approximate source. Material score judges reference-derived composite only.','repairs_used':2,'repair_limit':2}
(p/'critic.json').write_text(json.dumps(critic,indent=2)+'\n')
metrics=json.loads((p/'fidelity-check.json').read_text());native=json.loads((p/'artwork-native-validation.json').read_text())
preflight={'schema':'fidelity_preflight/1.0','status':'designer_review','creative_accepted':False,'production_ready':False,'revision':2,'parent_hash':fm.PARENT,'spec_hash':fm.digest(json.loads((p/'design-spec.json').read_text())),'measured_fidelity_passed':metrics['measured_fidelity_passed'],'critic_passed':False,'native_transport_passed':native['passed'],'all_front_copy_live':metrics['live_copy_logical_actualtext'],'raster_alpha_embedded':metrics['rgba_soft_mask_embedded'],'effective_ppi':ex['effective_output_ppi'],'interpolated':True,'upscale_roundtrip_ssim':ex['source_resolution_roundtrip_ssim'],'spend_usd':0,'physical_deviations':[],'blockers':['ARABIC_SCALE_4_PERCENT_EXCEEDS_3','SWOOSH_MATTE_GROUND_REMNANTS','HEIGHT_DATUM_UNRESOLVED','SUPPLIER_PRINTABLE_AREA_AND_SHOULDER_CONFORMITY_UNKNOWN','DECORATION_METHOD_UNSELECTED','WHITE_OPACITY_AND_FINE_LINE_PROOF_PENDING','OUTPUT_ICC_AND_SEPARATIONS_UNCONFIRMED'],'native_limitations':['Each glyph is live and grouped by logical copy; per-line reflow differs from a single untransformed text frame.','Native transport fidelity does not accept the design.','Repeated full Illustrator regeneration currently errors MRAP at first text size setter; the retained native file was corrected for the complete vector logo and reopened/verified.'],'original_font':'Unknown; closest licensed class chosen from the concept.'}
(p/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
(R/'sightline-negative-control.json').write_text(json.dumps(legacy_negative(),indent=2)+'\n')
(R/'spend.json').write_text(json.dumps({'day':4,'today_usd':0,'build_total_usd':0,'paid_upscale_calls':0,'local_resampling':True,'limit_day_usd':25,'limit_total_usd':250,'statement':'$0, no paid upscale needed; local interpolation checked, no new detail claimed.'},indent=2)+'\n')
# The native comparison PDF is derived from the current AI PDF-compatible bytes.
import fitz
with fitz.open(p/'artwork-native.ai') as doc:doc.save(p/'artwork-native-check.pdf')
# Everything needed to review/rebuild stays with the editable files; no secrets or DB.
with zipfile.ZipFile(R/'day4-review-package.zip','w',zipfile.ZIP_DEFLATED) as z:
 for folder in ('master','measurement-assets','stand-family','stand-144','stand-146','stand-family-stagger'):
  for f in sorted((R/folder).rglob('*')):
   if f.is_file() and f.suffix not in ('.jsx',):z.write(f,f.relative_to(R))
 for name in ('concept-147-measurement.json','fidelity-instrument.json','sightline-negative-control.json','spend.json'):z.write(R/name,name)
files={f.relative_to(R).as_posix():fm.fa.sha(f) for folder in ('master','measurement-assets','stand-family','stand-144','stand-146','stand-family-stagger') for f in sorted((R/folder).rglob('*')) if f.is_file()}
files['day4-review-package.zip']=fm.fa.sha(R/'day4-review-package.zip')
record={'schema':'day4_publication/1.0','product_spec_hash':preflight['spec_hash'],'assembly_spec_hash':fm.digest(json.loads((R/'stand-family/assembly-spec.json').read_text())),'review_state':'designer_review','production_ready':False,'files':files}
(R/'publication.json').write_text(json.dumps(record,indent=2)+'\n')
print('package',len(files),'files; native',native['passed'],'creative',False,'local roundtrip',ex['source_resolution_roundtrip_ssim'])
