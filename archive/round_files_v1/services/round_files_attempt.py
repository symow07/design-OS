"""Owner-pinned second execution attempt; every paid action awaits app Retry."""
from copy import copy, deepcopy
import json
from pathlib import Path
import shutil
import traceback

from . import round_flow as flow
from .round_calls import RoundContext, sha
from .round_files_job import read, verify_pins, _relative, digest


def policy():
    return read(flow.REPO/'docs/rounds/files-build-policy.json')


def authority(build):
    value = policy().get('execution_attempts', {}).get(build.round.slug)
    if value is None:
        return None
    if (value['schema'] != 'owner_files_attempt/1' or value['attempt'] != 2 or
            value['maximum_eye_looks'] != 2 or value['maximum_repairs'] != 1 or
            value['maximum_image_calls'] != 2 or value['budget_usd'] != 4 or
            value['picture_sha256'] != build.inputs['picture_sha256'] or
            value['first_revision'] != value['source_revision']+1 or
            any(type(value[key]) is not int or value[key] < 0 for key in
                ('source_revision', 'source_retry_attempt', 'source_look_count', 'first_revision')) or
            value['source_look_count'] < 1 or len(value['source_eye_sha256']) != 64 or
            not value['owner_instruction'].strip()):
        raise ValueError('Attempt authority must pin the picked picture, $4, two edits, two looks and one repair.')
    return value


def folder(build):
    return flow.round_root(build.round)/'files/attempts/2'


def available(build):
    """Read-only UI permission; a new attempt never starts by rendering a page."""
    try:
        approved = authority(build)
        if approved is None:
            return False
        prior = build.steps['eye']['result']
        if prior.get('attempt') == 2:
            return False
        path = flow.round_root(build.round)/'files/review'/f"eye-{approved['source_look_count']}.json"
        return (prior['verdict'] == 'needs_attention' and prior['revision'] == approved['source_revision'] and
                len(prior['looks']) == approved['source_look_count'] and path.is_file() and
                sha(path) == approved['source_eye_sha256'] and read(path)['status'] == 'complete' and
                read(path)['payload'] == prior['looks'][-1])
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def active(build):
    return (folder(build)/'claim.json').is_file()


def claim(ctx):
    approved = authority(ctx.build)
    if approved is None or ctx.build.steps['eye']['attempts'] <= approved['source_retry_attempt']:
        raise ValueError('The second execution attempt requires the owner’s new app Retry.')
    path = folder(ctx.build)/'claim.json'
    source_eye = ctx.root/'review'/f"eye-{approved['source_look_count']}.json"
    if sha(source_eye) != approved['source_eye_sha256'] or read(source_eye)['status'] != 'complete':
        raise ValueError('The rejected review bound to the owner instruction changed.')
    if not path.exists():
        prior = ctx.build.steps['eye']['result']
        if not available(ctx.build) or read(ctx.root/'review/verdict.json') != prior:
            raise ValueError('The second attempt must begin from the complete retained rejected verdict.')
        verify_pins(ctx, prior['outputs']['pins'])
        verify_pins(ctx, ctx.build.steps['files']['result']['pins'])
        path.parent.mkdir(parents=True, exist_ok=True)
        for name in ('review/verdict.json', 'README.md'):
            source = ctx.root/name
            if source.exists():
                destination = path.parent/('previous-'+source.name)
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    raise ValueError('A retained pre-attempt record changed.')
                shutil.copyfile(source, destination)
        retained = [ctx.root/name for name in ('inputs.json','source.png','inspection.json','art.json','stand.json')]
        retained.extend(p for p in path.parent.glob('previous-*') if p.is_file())
        retained.extend(p for directory in ('art','stand','repairs','revisions') for p in (ctx.root/directory).rglob('*') if p.is_file())
        retained.extend(p for p in (ctx.root/'review').rglob('*') if p.is_file() and p.name != 'verdict.json')
        flow.write_json(path, {'authority': approved, 'owner_retry_attempt': ctx.build.steps['eye']['attempts'],
            'previous_looks': prior['looks'], 'input_pins': {_relative(ctx,p):sha(p) for p in retained}})
    result = read(path)
    if result['authority'] != approved:
        raise ValueError('Attempt authority changed after the attempt started.')
    verify_pins(ctx, result['input_pins'])
    return result


class AttemptContext(RoundContext):
    def __init__(self, build, job=None, *, text_client=None, image_client=None, native=True):
        super().__init__(build.round, job, text_client=text_client, image_client=image_client)
        self.build, self.native = build, native
        self.root = flow.round_root(build.round)/'files'
        from .round_files_flow import files_brief
        self.brief = files_brief(build)
        self.round = copy(build.round)
        self.authorization = claim(self)['authority']
        self.round.budget_usd = self.authorization['budget_usd']
        self.prefix = f'files-attempt-2/{build.round.slug}/'
        self.image_attempt_cap = self.authorization['maximum_image_calls']
        if not native:
            import sys
            if 'pytest' not in sys.modules:
                raise ValueError('Only fixtures may omit native Illustrator readback.')

    def image_call(self, operation, prompt, destination, *, target, mask, size):
        from .round_files_detail import CANVASES, PROMPT
        from .round_master_calls import MasterContext
        panel = operation.removeprefix('detail/')
        if operation != 'detail/'+panel or panel not in CANVASES or prompt != PROMPT:
            raise ValueError('Only the two authorized own-crop preservation edits may be purchased.')
        expected = folder(self.build)/'details'/panel
        if (Path(destination).resolve() != (expected/'call').resolve() or
                Path(target).resolve() != (expected/'input.png').resolve() or
                Path(mask).resolve() != (expected/'mask.png').resolve() or
                size != 'x'.join(map(str, CANVASES[panel]))):
            raise ValueError('The detail edit must use its prepared own-crop canvas and mask.')
        prepared = read(expected/'prepared.json')
        inspection = checked_inspection(self)
        identity = prepared['identity']
        if (identity['source_sha256'] != self.build.inputs['picture_sha256'] or identity['panel'] != panel or
                identity['crop_px'] != inspection['panels'][panel]['crop_px']):
            raise ValueError('The paid detail canvas must bind the unchanged picked picture and measured crop.')
        for name in ('input.png', 'mask.png'):
            if sha(expected/name) != prepared['pins'][name]:
                raise ValueError('A prepared detail input changed before payment.')
        return MasterContext.masked_edit(self, operation, prompt, destination, target=target, mask=mask, size=size)

    def text_call(self, operation, prompt, destination, **kwargs):
        if operation not in ('eye/1', 'eye/2'):
            raise ValueError('Only two designer looks belong to this attempt.')
        expected = folder(self.build)/'review'/('eye-'+operation[-1]+'.json')
        if Path(destination).resolve() != expected.resolve():
            raise ValueError('An attempt review must use its own durable record.')
        if expected.exists() and read(expected)['status'] != 'complete':
            raise ValueError('An incomplete review already used its automatic truncation retry; no repurchase.')
        return super().text_call(operation, prompt, destination, **kwargs)


def scoped_spend(build):
    from . import spend_reservation as spend
    prefix = f'files-attempt-2/{build.round.slug}/'
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls WHERE substr(operation,1,?)=?',(len(prefix),prefix))]
    return {'actual_usd':sum(row['accounted'] for row in rows if row['state']=='usage_recorded')/1e6,
        'held_usd':sum(row['accounted'] for row in rows if row['state'] in ('reserved','billing_unresolved'))/1e6,
        'accounted_usd':sum(row['accounted'] for row in rows)/1e6, 'calls':len(rows),
        'budget_usd':4., 'attempt':2}


def checked_inspection(ctx):
    base = folder(ctx.build)
    retained = claim(ctx)
    previous = read(base/'previous-verdict.json')['outputs'].get('repair_bundle')
    inspection = deepcopy(previous['inspection'] if previous else read(ctx.root/'inspection.json'))
    inspection['drawing_material'] = {'status':'engine','wall_mm':1.,'base_mm':2.,
        'scope':'Provisional physical acrylic and gold for the engine drawing only; no source cap pixels or print ink.'}
    path = base/'inspection.json'
    if path.exists() and read(path) != inspection:
        raise ValueError('The retained attempt inspection changed from its pinned prior inspection.')
    if not path.exists():
        flow.write_json(path,inspection)
    measurements = {'source':'Prior pinned inspection','inspection_sha256':sha(path),'cap_pixels_excluded':True}
    measured = base/'measurements.json'
    if measured.exists() and read(measured) != measurements:
        raise ValueError('The attempt inspection measurements changed before detail replay.')
    if not measured.exists():
        flow.write_json(measured,measurements)
    return inspection


def _pictured_art(ctx, inspection, details, geometry, width_rule, prepare_art):
    """Retain failed fits; a newer owner Retry gets its own unpaid art directory."""
    from . import round_files_attempt_art, round_files_line_fit, round_files_art, round_files_refinement_v2
    base = Path(ctx.root)/'attempts/2'
    owner_retry = ctx.build.steps['eye']['attempts']
    if type(owner_retry) is not int or owner_retry < width_rule['owner_retry_attempt']:
        raise ValueError('A pictured fit must retain its owner Retry identity.')
    out = base/f'art-pictured-widths-retry-{owner_retry}'
    record_path = out/'run.json'
    retained_pins = {}
    previous = [base/'art-pictured-widths', *sorted(base.glob('art-pictured-widths-retry-*'))]
    for prior in previous:
        if prior == out or not prior.exists():
            continue
        if (prior/'run.json').exists():
            old = read(prior/'run.json')
            if old['owner_retry_attempt'] >= owner_retry:
                raise ValueError('A pictured fit cannot replay an earlier owner Retry.')
            verify_pins(ctx, old['retained_pins'])
            verify_pins(ctx, old['artifact_pins'])
        retained_pins.update({_relative(ctx,p):sha(p) for p in prior.rglob('*') if p.is_file()})
    identity = {'schema':'pictured_fit_run/1', 'owner_retry_attempt':owner_retry,
        'source_sha256':sha(ctx.root/'source.png'), 'claim_sha256':sha(base/'claim.json'),
        'width_rule_sha256':sha(base/'width-rule.json'),
        'brief_sha256':digest(ctx.brief),
        'inspection_sha256':digest(inspection), 'details_sha256':digest(details),
        'geometry_sha256':digest(geometry), 'retained_pins':retained_pins,
        'implementation_sha256':{Path(path).name:sha(Path(path)) for path in
            (__file__, round_files_attempt_art.__file__, round_files_line_fit.__file__,
             round_files_art.__file__, round_files_refinement_v2.__file__)}}
    if record_path.exists():
        saved = read(record_path)
        if any(saved.get(key) != value for key,value in identity.items()):
            raise ValueError('The pictured fit inputs or code changed; a new owner Retry is required.')
        verify_pins(ctx, saved['artifact_pins'])
        if saved['status'] == 'complete':
            if digest(saved['art']) != saved['art_sha256']:
                raise ValueError('The completed pictured-fit descriptor changed.')
            return saved['art']
        if saved['status'] != 'running':
            raise ValueError('This pictured fit failed; its records stay unchanged until a new owner Retry.')
    else:
        if out.exists():
            raise ValueError('An unrecorded pictured-fit directory cannot be overwritten.')
        flow.write_json(record_path, dict(identity, status='running', artifact_pins={}))

    def pins():
        return {_relative(ctx,p):sha(p) for p in out.rglob('*') if p.is_file() and p != record_path}

    try:
        art = prepare_art(ctx.root/'source.png', inspection, ctx.brief, out,
            details=details, geometry=geometry, expected_sha256=ctx.build.inputs['picture_sha256'],
            width_mode='pictured')
        verify_pins(ctx, retained_pins)
    except Exception as exc:
        diagnostic = getattr(exc, 'diagnostic', None)
        try:
            diagnostic = json.loads(json.dumps(diagnostic, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError):
            diagnostic = {'schema':'invalid_exception_diagnostic/1',
                          'reason':'The exception diagnostic was not JSON-safe; original error and traceback are retained.'}
        frames = [{'file':frame.f_code.co_filename, 'function':frame.f_code.co_name, 'line':line}
                  for frame,line in traceback.walk_tb(exc.__traceback__)]
        flow.write_json(record_path, dict(identity, status='failed', artifact_pins=pins(),
            error_type=type(exc).__name__, error=str(exc), diagnostic=diagnostic,
            traceback_frames=frames))
        raise
    flow.write_json(record_path, dict(identity, status='complete', artifact_pins=pins(),
        art=art, art_sha256=digest(art)))
    return art


def prepare(ctx):
    from .round_files_job import object_specs, fit_repair_type, build_outputs
    from .round_files_detail import run_details
    from .round_files_attempt_art import prepare_attempt_art
    from .round_files_stand import build_stand
    from .round_files_width_authority import claim_width_rule
    base = folder(ctx.build)
    manifest = base/'bundle.json'
    retained = claim(ctx)
    width_rule = claim_width_rule(ctx)
    if manifest.exists():
        bundle = read(manifest)
        if bundle['claim_sha256'] != sha(base/'claim.json'):
            raise ValueError('The attempt claim changed before output replay.')
        if bundle.get('width_rule', {'mode': 'fixed'}) != width_rule:
            raise ValueError('The prepared files use a different foil-width authority.')
        verify_pins(ctx,bundle['pins'])
    else:
        inspection = checked_inspection(ctx)
        details = run_details(ctx, ctx.root/'source.png', {key:inspection['panels'][key]['crop_px']
            for key in ('body_front','stand_header')}, base/'details', expected_source_sha256=ctx.build.inputs['picture_sha256'])
        geometry = build_stand(ctx.brief, inspection, base/'stand', include_enclosure=True, rear_visibility=True)
        if width_rule['mode'] == 'pictured':
            art = _pictured_art(ctx, inspection, details, geometry, width_rule, prepare_attempt_art)
        else:
            art = prepare_attempt_art(ctx.root/'source.png', inspection, ctx.brief, base/'art-fit-2',
                details=details, geometry=geometry, expected_sha256=ctx.build.inputs['picture_sha256'], width_mode='fixed')
        flow.write_json(base/'art.json',art)
        flow.write_json(base/'stand.json',geometry)
        bundle = {'claim_sha256':sha(base/'claim.json'), 'width_rule':width_rule, 'inspection':inspection,'art':art,'geometry':geometry,
            'details':details, 'measurements':read(base/'measurements.json'),
            'geometry_path':_relative(ctx,base/'stand/stand-geometry.json'),
            'pins':{_relative(ctx,p):sha(p) for p in base.rglob('*') if p.is_file()}}
        flow.write_json(manifest,bundle)
    specs = [fit_repair_type(spec,bundle['geometry']) for spec in object_specs(ctx,bundle=bundle)]
    specs[2]['die_visible'] = True
    return build_outputs(ctx,specs,retained['authority']['first_revision'],bundle=bundle)


def review(ctx):
    from .round_files_job import eye_view, validate_eye, preview, build_outputs
    outputs = prepare(ctx)
    initial = outputs
    base = folder(ctx.build)
    verdicts = []
    pictured_widths = outputs['repair_bundle'].get('width_rule', {'mode':'fixed'})['mode'] == 'pictured'
    foil_rule = ('foil widths measured per segment from the original picture, with full source-pixel area coverage >=90%; '
                 if pictured_widths else 'body foil .3mm, stand scaled; ')
    for look in (1,2):
        prompt = ('You are the designer’s eye. This is owner-authorized execution attempt 2, look '+str(look)+' of at most two. '
            'Does the built bottle and loaded stand read as the unchanged picked picture? Judge the images, not numeric records. '
            'Allowed changes: measured preservation detail edit only when ΔE00 mean<=1.5 AND SSIM>=.97 else exact2x upscale; '
            'geometric gold-line fitting with >=90% source-line coverage and no unsupported strokes; '+foil_rule+
            'header gold raster removed only beneath fitted strokes, separate live-copy removal; square header with own edge extension; '
            'approved vector logo only, centered engraving on a physical gold cap; live GRANTED type with house Arabic shaping; '
            'provisional geometry, full square-hole engine die and raised rear platform exposing at least top25mm of rear bottles. '
            'Clear acrylic/liquid and gold cap are physical drawing materials, not ink. Hidden faces remain unprinted. '
            'Reject broken/beaded/unsupported foil, cap ghosts, raster lettering, lost header ground, missing die or failed sightlines. '
            'One provider-free adjustment of one live type run scale0.9–1.1 in its existing box is available after look1; '
            'if the required repair is different, list it clearly and leave repair null. No third look. '
            'Return JSON only: {"verdict":"pass" or "needs_attention","findings":["observed finding"],'
            '"repair":null or {"kind":"type_size","object_id":"bottle-front" or "stand","run_index":0,"scale":1.05}}. '
            'The second look must leave repair null.\nSTAND: '+json.dumps({key:outputs['repair_bundle']['geometry'][key]
                for key in ('count','fold_check','sightlines')})+'\nTYPE: '+json.dumps({item['id']:item['type'] for item in outputs['objects']},ensure_ascii=False))
        images = [('Picked picture unchanged',ctx.root/'source.png'),
            ('Built engine elevation',eye_view(ctx,ctx.root/outputs['drawing'],outputs['revision']))]
        images.extend((item['id']+' print',eye_view(ctx,item['png'],outputs['revision'])) for item in outputs['objects'])
        call = ctx.text_call('eye/'+str(look),prompt,base/'review'/f'eye-{look}.json',images=images,max_tokens=16384,ceiling=2.)
        verdict = validate_eye(call['payload']); verdicts.append(verdict)
        if look == 2 and verdict.get('repair') is not None:
            raise ValueError('The attempt permits no third look or second repair.')
        if verdict['verdict']=='pass' or verdict.get('repair') is None or look==2:
            break
        repair = verdict['repair']; specs = deepcopy(initial['specs'])
        target = next(row for row in specs if row['id']==repair['object_id'])
        if not 0 <= repair['run_index'] < len(target['type_runs']):
            raise ValueError('The requested live-copy repair does not exist.')
        row = target['type_runs'][repair['run_index']]
        row['size_pt'] = max(5.,row['size_pt']*repair['scale'])
        flow.write_json(base/'review/repair.json',{'repair':repair,'additional_provider_cost_usd':0,
            'source_revision':initial['revision'],'result_revision':initial['revision']+1})
        outputs = build_outputs(ctx,specs,initial['revision']+1,bundle=initial['repair_bundle'])
    result = dict(verdicts[-1],attempt=2,looks=verdicts,revision=outputs['revision'],outputs=outputs,
        preview=preview(ctx,outputs,verdicts[-1]),repairs_used=int(outputs['revision']!=initial['revision']))
    flow.write_json(ctx.root/'review/verdict.json',result)
    return result


def progress(build):
    base = folder(build)
    revision = read(base/'claim.json')['authority']['first_revision']
    rows = []

    def completed(relative):
        path = base/relative
        return path.is_file() and (not relative.startswith('review/eye-') or read(path).get('status') == 'complete')

    for label,relative in [('Bottle detail','details/body_front/detail.json'),
                           ('Header detail','details/stand_header/detail.json'),
                           ('Fitting the gold lines and building the stand','bundle.json'),
                           ('Making your files',f'../../revisions/{revision}/outputs.json'),
                           ('Designer’s first look','review/eye-1.json')]:
        rows.append({'label':label,'state':'Done' if completed(relative) else 'Waiting'})
    if (base/'review/repair.json').is_file():
        rows.append({'label':'Designer’s final look','state':'Done' if completed('review/eye-2.json') else 'Waiting'})
    rows.append({'label':'Preparing your download','state':'Done' if build.state == 'complete' else 'Waiting'})
    result = build.steps['eye']['result'] or {}
    if build.state == 'failed' and result.get('attempt') == 2 and result.get('verdict') == 'needs_attention':
        label = 'Designer’s final look' if len(result['looks']) == 2 else 'Designer’s first look'
        next(row for row in rows if row['label'] == label)['state'] = 'Needs attention'
        return rows
    if build.state in ('failed', 'running', 'queued'):
        pending = next((row for row in rows if row['state'] == 'Waiting'), None)
        if pending is not None:
            pending['state'] = 'Needs attention' if build.state == 'failed' else 'Working'
    return rows
