"""An explicit owner extension, pinned to a rejected review; never automatic."""
import shutil

from . import round_flow as flow
from .round_calls import sha


def policy():
    from .round_files_job import read
    return read(flow.REPO / 'docs/rounds/files-build-policy.json')


def authority(build):
    document = policy()
    if 'repair_extensions' not in document or build.round.slug not in document['repair_extensions']:
        return None
    value = document['repair_extensions'][build.round.slug]
    if (value['schema'] != 'owner_files_extension/1' or value['source_revision'] != 1 or
            value['result_revision'] != 2 or value['maximum_eye_looks'] != 3 or
            value['maximum_repairs'] != 2 or value['budget_usd'] != 10 or
            type(value['source_retry_attempt']) is not int or value['source_retry_attempt'] < 0 or
            float(build.budget_usd) != 10 or value['picture_sha256'] != build.inputs['picture_sha256'] or
            not isinstance(value['owner_instruction'], str) or not value['owner_instruction'].strip() or
            len(value['source_eye_sha256']) != 64):
        raise ValueError('The owner extension must bind this picture, one additional repair/review and the existing allowance.')
    return value


def extension_available(build):
    from .round_files_job import read
    prior = build.steps['eye']['result']
    if not prior or prior['revision'] != 1 or len(prior['looks']) != 2 or prior['verdict'] != 'needs_attention':
        return False
    try:
        approved = authority(build)
    except (ValueError, KeyError, TypeError):
        # Invalid configuration grants nothing; page rendering remains usable.
        # The queued execution path validates authority strictly again.
        return False
    if approved is None:
        return False
    path = flow.round_root(build.round) / 'files/review/eye-2.json'
    return (path.is_file() and sha(path) == approved['source_eye_sha256'] and
            read(path)['status'] == 'complete' and read(path)['payload'] == prior['looks'][1])


def require_authority(ctx):
    from .round_files_job import read
    approved = authority(ctx.build)
    path = ctx.root / 'review/eye-2.json'
    if (approved is None or not path.is_file() or sha(path) != approved['source_eye_sha256'] or
            read(path)['status'] != 'complete' or read(path)['payload']['verdict'] != 'needs_attention'):
        raise ValueError('A further designer look needs an explicit owner extension bound to the rejected second review.')
    if (ctx.build.steps['eye']['attempts'] <= approved['source_retry_attempt'] or
            read(ctx.root/'review/eye-2.request.json')['app_attempt'] != approved['source_retry_attempt']):
        raise ValueError('The additional pass needs a new owner Retry after the rejected second review.')
    return approved


def should_run(ctx):
    claim = ctx.root / 'review/extension-2.json'
    return claim.exists() or extension_available(ctx.build)


def prepare(ctx):
    from .round_files_job import read, verify_pins, _relative, object_specs, fit_repair_type, build_outputs
    from .round_files_repair_art import refine_inspection_v2, prepare_repaired_art_v2
    from .round_files_stand import build_stand
    approved = require_authority(ctx)
    claim_path = ctx.root / 'review/extension-2.json'
    if not claim_path.exists():
        prior = ctx.build.steps['eye']['result']
        if (ctx.build.steps['eye']['attempts'] < 1 or not extension_available(ctx.build) or
                read(ctx.root/'review/verdict.json') != prior or
                (ctx.root/'review/eye-3.request.json').exists()):
            raise ValueError('The additional pass needs an owner Retry and the complete saved second verdict.')
        # Validate earlier baselines before retaining them. A new census must
        # never silently authorize an altered or deleted historical artifact.
        verify_pins(ctx, ctx.build.steps['files']['result']['pins'])
        verify_pins(ctx, prior['outputs']['pins'])
        previous_repair = read(ctx.root/'review/repair.json')
        if 'input_pins' in previous_repair:
            verify_pins(ctx, previous_repair['input_pins'])
        reviewed_images = {_relative(ctx, row['path']): row['sha256']
                           for row in read(ctx.root/'review/eye-2.json')['images']}
        verify_pins(ctx, reviewed_images)
        saved = ctx.root/'review/verdict-before-extension-2.json'
        original = ctx.root/'review/verdict.json'
        if saved.exists():
            if saved.read_bytes() != original.read_bytes():
                raise ValueError('The retained second verdict changed.')
        else:
            shutil.copyfile(original, saved)
        retained = [ctx.root/name for name in ('inputs.json', 'source.png', 'inspection.json', 'art.json', 'stand.json',
                    'review/repair.json', 'review/verdict-before-extension-2.json')]
        if (ctx.root/'review/verdict-before-repair.json').exists():
            retained.append(ctx.root/'review/verdict-before-repair.json')
        retained.extend(path for directory in ('art', 'stand', 'repairs/mechanical', 'revisions/0', 'revisions/1',
                                               'review/views/0', 'review/views/1')
                        for path in (ctx.root/directory).rglob('*') if path.is_file())
        retained.extend(path for number in (1, 2) for path in (ctx.root/'review').glob(f'eye-{number}.*json'))
        claim = {'authority': approved, 'owner_retry_attempt': ctx.build.steps['eye']['attempts'],
                 'source_revision': 1, 'result_revision': 2, 'previous_looks': prior['looks'],
                 'additional_provider_cost_usd': 0,
                 'input_pins': {_relative(ctx, path): sha(path) for path in retained}}
        claim['input_pins'].update(ctx.build.steps['files']['result']['pins'])
        claim['input_pins'].update(prior['outputs']['pins'])
        claim['input_pins'].update(reviewed_images)
        flow.write_json(claim_path, claim)
    claim = read(claim_path)
    if claim['authority'] != approved:
        raise ValueError('The owner extension changed after this pass started.')
    verify_pins(ctx, claim['input_pins'])
    folder = ctx.root/'repairs/owner-extension-2'
    manifest = folder/'bundle.json'
    if manifest.exists():
        bundle = read(manifest)
        if bundle['claim_sha256'] != sha(claim_path):
            raise ValueError('The additional repair claim changed.')
        verify_pins(ctx, bundle['pins'])
        for key, name in (('inspection', 'inspection'), ('measurements', 'measurements'), ('art', 'art'), ('geometry', 'stand'),
                          ('assembly_material', 'assembly-material')):
            if bundle[key] != read(folder/(name+'.json')):
                raise ValueError('The additional repair descriptor changed: '+name)
    else:
        refined = refine_inspection_v2(ctx.root/'source.png', read(ctx.root/'inspection.json'), ctx.brief,
                                      original_sha256=ctx.build.inputs['picture_sha256'])
        inspection = refined['inspection']
        art = prepare_repaired_art_v2(ctx.root/'source.png', inspection, ctx.brief, folder/'art',
                                     expected_sha256=ctx.build.inputs['picture_sha256'])
        geometry = build_stand(ctx.brief, inspection, folder/'stand', include_enclosure=True)
        assembly = inspection['drawing_material']['physical_source']['enclosure']
        flow.write_json(folder/'assembly-material.json', assembly)
        for name, value in (('inspection', inspection), ('measurements', refined['record']), ('art', art), ('stand', geometry)):
            flow.write_json(folder/(name+'.json'), value)
        bundle = {'claim_sha256': sha(claim_path), 'inspection': inspection, 'art': art, 'geometry': geometry,
                  'measurements': refined['record'], 'geometry_path': _relative(ctx, folder/'stand/stand-geometry.json'),
                  'assembly_material': assembly, 'assembly_material_path': _relative(ctx, folder/'assembly-material.json'),
                  'pins': {_relative(ctx, path): sha(path) for path in folder.rglob('*') if path.is_file()}}
        flow.write_json(manifest, bundle)
    specs = [fit_repair_type(spec, bundle['geometry']) for spec in object_specs(ctx, bundle=bundle)]
    return build_outputs(ctx, specs, 2, bundle=bundle), claim


def review(ctx):
    from .round_files_job import eye_view, validate_eye, preview
    outputs, claim = prepare(ctx)
    bundle = outputs['repair_bundle']
    import json
    prompt = (
        'You are the designer’s eye. This is look THREE and the final look. The owner explicitly permitted '
        'one additional $0 repair and review after the second rejection; no fourth look or further repair is allowed. '
        'Does this built bottle and loaded stand read as the unchanged picked picture? Judge the actual images, '
        'not the existence of records or passing numeric checks. Return needs_attention for unresolved visual defects. '
        'Allowed differences remain approved vector logo, live GRANTED type with house Arabic shaping, source-position '
        'foil tracing, provisional physical dimensions, engine die and square header with source-edge pixel extension, '
        'the stand built for the brief’s rows × columns, and invented lettering replaced by live brand and Arabic COPY '
        'along its path. '
        'Physical source material crops belong only to the engine drawing, never to the ink files. Unknown rear liquid '
        'stays unknown. This is a true front elevation: sidewall perspective widths are not invented. '
        'Return JSON only: {"verdict":"pass" or "needs_attention","findings":["observed finding"],"repair":null}. '
        '\nPREVIOUS FINDINGS: '+json.dumps(claim['previous_looks'][1]['findings'], ensure_ascii=False)+
        '\nSOURCE MEASUREMENTS: '+json.dumps(bundle['measurements'], ensure_ascii=False)+
        '\nSTAND REPORTS: '+json.dumps({key: bundle['geometry'][key] for key in ('fold_check', 'sightlines')})+
        '\nASSEMBLY MATERIAL: '+json.dumps(bundle['assembly_material'], ensure_ascii=False)+
        '\nDRAWING: '+json.dumps(outputs['drawing_record'], ensure_ascii=False)+
        '\nLIVE TYPE: '+json.dumps({item['id']: item['type'] for item in outputs['objects']}, ensure_ascii=False))
    images = [('Picked picture, unchanged', ctx.root/'source.png'),
              ('Engine front elevation after authorized repair', eye_view(ctx, ctx.root/outputs['drawing'], 2))]
    images.extend((item['id']+' flat print', eye_view(ctx, item['png'], 2)) for item in outputs['objects'])
    call = ctx.text_call('eye/3', prompt, ctx.root/'review/eye-3.json', images=images, max_tokens=16384, ceiling=2.0)
    verdict = validate_eye(call['payload'])
    if verdict.get('repair') is not None:
        raise ValueError('The owner extension permits no fourth look or further repair.')
    result = dict(verdict, looks=claim['previous_looks']+[verdict], revision=2, outputs=outputs,
                  preview=preview(ctx, outputs, verdict))
    flow.write_json(ctx.root/'review/verdict.json', result)
    return result
