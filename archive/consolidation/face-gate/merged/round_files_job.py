"""Picked picture to print files. The picture is the design intent (owner, 2026-10-27): each flat face is drawn
front-on as one edit guided by the picture, its live type and the approved logo placed, and the owner accepts or redraws
it (owner, 2026-10-28; round_files_gate); the accepted faces are composed on the engine's die and written with the die
locked (round_files_faces, docs/rounds/reuse-plan.md). One spend cap per round; a call whose outcome is unknown is
checked once against the provider and closed, never a permanent stop."""
from copy import copy, deepcopy
import base64
import binascii
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, UnidentifiedImageError
from django.conf import settings

from . import round_files_faces as faces
from . import round_flow as flow
from . import spend_reservation as spend
from .round_calls import IMAGE_MODEL, STREAM_PARTIAL_IMAGES, RoundContext, sha, streamed_edit
from .round_files_flow import SCHEMA

#: every prefix the round's files have been paid under: the reading's and the drawings' (files/), and the retired face
#: path's attempts (files-faces/, files-faces-2/, ...). Their sum is held to the build's one cap.
FILES_PREFIXES = "operation LIKE 'files/%' OR operation LIKE 'files-faces%'"


class LostCall(ValueError):
    """A paid call whose outcome is unknown: checked once against the provider, then closed; never sent twice."""


def provider_check(provider, reservation_id):
    """The one check of a lost call against the provider. OpenAI reports image usage only to an organisation admin
    key (OPENAI_ADMIN_KEY); Anthropic offers no lookup of a request that returned nothing. Without a lookup, the check
    is recorded as unavailable and the hold stays counted."""
    key = getattr(settings, 'OPENAI_ADMIN_KEY', '') if provider == 'openai' else ''
    if not key:
        return {'checked': False, 'billed': None, 'why': (
            'OpenAI\'s usage records need an organisation admin key, which this app does not hold (the project key '
            'is refused: 403)' if provider == 'openai' else 'Anthropic offers no lookup of a request that returned '
            'nothing')}
    import httpx
    from datetime import datetime, timedelta
    with spend._connect() as db:
        started = datetime.fromisoformat(db.execute('SELECT started_at FROM calls WHERE id=?',
                                                    (reservation_id,)).fetchone()[0])
    try:
        reply = httpx.get('https://api.openai.com/v1/organization/usage/images', timeout=30,
                          headers={'Authorization': 'Bearer ' + key},
                          params={'start_time': int((started - timedelta(minutes=1)).timestamp()),
                                  'end_time': int((started + timedelta(minutes=15)).timestamp()),
                                  'bucket_width': '1m', 'models': IMAGE_MODEL})
        reply.raise_for_status()
        images = sum(row.get('images', 0) for bucket in reply.json().get('data', [])
                     for row in bucket.get('results', []))
    except Exception as exc:
        return {'checked': False, 'billed': None, 'why': 'the usage lookup failed: ' + type(exc).__name__}
    return {'checked': True, 'billed': images > 0, 'images_in_window': images,
            'why': 'OpenAI\'s image usage in the call\'s window (any image there keeps the hold counted)'}


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def execution_brief(brief):
    """Missing physical dimensions become explicit provisional estimates."""
    result = deepcopy(brief)
    values = result['dimensions_mm']
    estimates = {}
    for key, estimate in (('width', 15.), ('height', 100.)):
        if values.get(key) is None:
            values[key] = estimate
            estimates[key] = estimate
    for key, estimate in (('depth', values['width']), ('cap_height', values['height'] * .3)):
        if values.get(key) is None:
            values[key] = estimate
            estimates[key] = estimate
    if estimates:
        result['measurements_provisional'] = True
    result['execution_estimates_mm'] = estimates
    return result


def input_snapshot(record):
    from .round_files_export import LOGO, LOGO_SHA256, font_records
    from apps.dashboard.product_round_views import publication
    folder = flow.round_root(record)
    handoff = read(folder / 'handoff.json')
    published = publication(record)
    if (record.pick.get('merge') or handoff['id'] != record.pick['id'] or
            handoff['source_round'] != record.pk or handoff['reason'] != record.pick['reason']):
        raise ValueError('The recorded choice and frozen picture handoff must agree.')
    picture = (folder / handoff['picture']).resolve()
    if (not picture.is_relative_to(folder) or published['files'].get(handoff['picture']) != handoff['picture_sha256']
            or sha(picture) != handoff['picture_sha256']):
        raise ValueError('The chosen picture no longer matches its publication.')
    if sha(LOGO) != LOGO_SHA256:
        raise ValueError('The approved logo changed.')
    policy = read(flow.REPO / 'docs/rounds/files-build-policy.json')
    return {'schema': SCHEMA, 'contract': handoff['contract'], 'picture': handoff['picture'],
            'picture_sha256': handoff['picture_sha256'], 'handoff_sha256': sha(folder / 'handoff.json'),
            'pick': deepcopy(record.pick), 'brief': execution_brief(record.product_brief),
            'brief_sha256': digest(record.product_brief), 'logo_sha256': LOGO_SHA256,
            'fonts': font_records(), 'policy': deepcopy(policy['default']),
            'completion_tag': policy['completion_tags'].get(record.slug, ''), 'budget_usd': 10}



class FilesContext(RoundContext):
    def __init__(self, build, job=None, *, text_client=None, image_client=None, native=True):
        super().__init__(build.round, job, text_client=text_client, image_client=image_client)
        self.build = build
        self.round = copy(build.round)
        self.round.budget_usd = build.budget_usd
        self.root = flow.round_root(build.round) / 'files'
        self.prefix = f'files/{build.round.slug}/'
        # One spend cap per round (owner, 2026-10-28): new calls go under files/<slug>/, held to what the build's cap
        # leaves after the retired attempts' prefixes; no separate image-count cap.
        spent = scoped_spend(build)
        self.round.budget_usd = max(float(build.budget_usd) - (spent['accounted_usd'] - spent['this_prefix_usd']), 0.01)
        self.image_attempt_cap = 10_000
        from .round_files_flow import files_brief
        self.brief = files_brief(build)
        self.native = native
        if not native and 'pytest' not in sys.modules:
            raise ValueError('Only isolated fixtures may omit the Illustrator save/reopen.')

    def _unknown_outcome(self, destination, request, provider):
        self._close_lost(destination, request['reservation_id'], provider)

    def _close_lost(self, destination, reservation_id, provider, error=None):
        """A call whose outcome is unknown: checked once against the provider, closed, and reported; the face it
        belongs to is marked failed and only the owner's Redraw buys a new drawing."""
        check = provider_check(provider, reservation_id)
        spend.close_unknown(reservation_id, dict(check, error=error or 'started, nothing saved'))
        flow.write_json(Path(destination).with_suffix('.lost.json'), {
            'reservation_id': reservation_id, 'provider': provider, 'check': check, 'error': error,
            'rule': 'checked once against the provider, then closed; never sent twice (owner, 2026-10-28)'})
        flow.commit_artifacts(self.round, 'a lost call checked once and closed')
        raise LostCall('The call\'s outcome is unknown (nothing came back). It was checked once and closed: '
                       + check['why'] + '.')

    def image_call(self, *args, **kwargs):
        raise ValueError('The execution half draws only its flat faces, through face_edit.')

    def text_call(self, operation, prompt, destination, **kwargs):
        if not operation.startswith('eye/'):
            return super().text_call(operation, prompt, destination, **kwargs)
        _, key, n = (operation.split('/') + ['', ''])[:3]
        if key not in faces.FACES or not n.isdigit():
            raise ValueError('The eye looks only at a drawn face.')
        expected = (faces.drawing_folder(self.root, key, int(n)) / 'eye.json').resolve()
        if Path(destination).resolve() != expected:
            raise ValueError('The eye\'s notes on a drawing use its own durable record.')
        try:
            return super().text_call(operation, prompt, destination, **kwargs)
        except (LostCall, flow.YieldRound):
            raise
        except Exception as exc:
            request = expected.with_suffix('.request.json')
            errors = sorted(expected.parent.glob(expected.stem + '.error-*.json'))
            if (request.exists() and errors and read(errors[-1]).get('http_status') is None and
                    _ledger_state(read(request)['reservation_id']) == 'reserved'):
                self._close_lost(expected, read(request)['reservation_id'], 'anthropic', type(exc).__name__)
            raise

    def face_edit(self, operation, prompt, folder, *, template, references, size):
        """One gpt-image-2 high edit: image 1 its template (its own mask), then its references. ``face/<key>/<n>``: a
        product face guided by the picked picture's view of it (and, for a Redraw with the owner's note, the previous
        drawing), or a stand face repainted on the flat die; ``flat/stand/<n>``: the whole flat die painted, image 2
        the style reference. Saved replies are never bought twice; one new call per delivery."""
        return self._face_edit(operation, prompt, folder, template=template, references=references, size=size)

    def _face_edit(self, operation, prompt, folder, *, template, references, size):
        from . import image_guard
        kind, key, n = (operation.split('/') + ['', ''])[:3]
        if kind == 'flat' and key == 'stand' and n.isdigit():
            expected = (faces.flat_root(self.root) / 'paintings' / n / 'call').resolve()
            sheet = faces.flat_root(self.root).resolve() / 'template.png'
        elif kind == 'face' and key in faces.FACES and n.isdigit():
            expected = (faces.drawing_folder(self.root, key, int(n)) / 'call').resolve()
            sheet = expected.parent / 'template.png'
        else:
            raise ValueError('Only a face\'s own drawing or the flat die\'s painting may be drawn.')
        destination = self._destination(Path(folder) / 'image-call.json')
        if destination.parent != expected:
            raise ValueError('A face edit must use its own durable folder.')
        template = Path(template).resolve()
        paths = [template] + [Path(path).resolve() for path in references]
        if template != sheet or not 1 <= len(references) <= 2:
            raise ValueError('A face edit uses its own template and its reference.')
        if settings.IMAGE_MODEL != IMAGE_MODEL or image_guard.competitor_in(prompt):
            raise ValueError('The face edit requires gpt-image-2 and a permitted prompt.')
        if size not in ('1536x1024', '1024x1536'):
            raise ValueError('A face edit requires a supported full-resolution canvas.')
        inputs = [self._input(path) for path in paths]
        if inputs[0]['px'] != [int(value) for value in size.split('x')]:
            raise ValueError('A face template must be its full-resolution canvas.')
        with Image.open(template) as image:
            if image.mode != 'RGBA' or image.getchannel('A').getextrema() != (0, 255):
                raise ValueError('A face template needs both its transparent face and protected white.')
        identity = {'model': IMAGE_MODEL, 'quality': 'high', 'size': size, 'prompt': prompt, 'inputs': inputs,
                    'mask': inputs[0], 'protocol': 'picture-face-edit/1',
                    'stream': {'partial_images': STREAM_PARTIAL_IMAGES}}
        op = 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai', operation=op,
                                                      estimate=faces.EDIT_HOLD_USD)
        if cached is not None:
            if sha(destination.parent / 'raw.png') != cached['output_sha256']:
                raise ValueError('A saved face edit changed; no repurchase.')
            return cached
        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = read(raw_path)
        else:
            if request['started_attempts']:
                self._unknown_outcome(destination, request, 'openai')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            flow.write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Files fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                opened = [path.open('rb') for path in paths]
                mask = template.open('rb')
                try:
                    raw = streamed_edit(self.image_client, destination.with_suffix('.stream.json'), model=IMAGE_MODEL,
                                        quality='high', size=size, prompt=prompt, n=1, image=opened, mask=mask)
                finally:
                    for handle in opened + [mask]:
                        handle.close()
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                flow.write_json(destination.with_suffix('.error.json'), {'error_type': type(exc).__name__,
                                'http_status': status, 'reservation_id': request['reservation_id']})
                flow.commit_artifacts(self.round, f'{op}: provider failure retained')
                if status is None:
                    self._close_lost(destination, request['reservation_id'], 'openai', type(exc).__name__)
                raise
            flow.write_json(raw_path, raw)
            flow.commit_artifacts(self.round, f'{op}: raw face edit retained')
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)

        def reject_image(reason):
            self._finish(destination, request, dict(identity, status='validation_failed', usage=raw.get('usage'),
                         validation_error=str(reason)), operation=op, image=True)
            raise ValueError('Invalid face edit reply retained: ' + str(reason))

        image_url = None
        try:
            data = raw['data']
            if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError('One edited image is required')
            if data[0].get('b64_json'):
                image_bytes = base64.b64decode(data[0]['b64_json'], validate=True)
            elif data[0].get('url'):
                image_url = data[0]['url']
            else:
                raise ValueError('Edited image bytes missing')
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            reject_image(exc)
        if image_url is not None:
            from apps.pipeline.agents.image_producer import download_image_bytes
            image_bytes = download_image_bytes(image_url)
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                if list(image.size) != inputs[0]['px']:
                    raise ValueError('Edited image has incorrect dimensions')
        except (TypeError, ValueError, UnidentifiedImageError, OSError) as exc:
            reject_image(exc)
        (destination.parent / 'raw.png').write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete',
                            output_sha256=sha(destination.parent / 'raw.png'), usage=raw.get('usage')),
                            operation=op, image=True)


def _ledger_state(reservation_id):
    with spend._connect() as db:
        row = db.execute('SELECT state FROM calls WHERE id=?', (reservation_id,)).fetchone()
    return row['state'] if row else None


def scoped_spend(build):
    """The round's files spend against its one cap: every files prefix of the round (FILES_PREFIXES) — what was billed,
    what is held, what was lost with its outcome unknown — and, apart, the share under files/<slug>/."""
    slug = build.round.slug
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls WHERE (' + FILES_PREFIXES + ') AND operation LIKE ?',
                                                ('%/' + slug + '/%',))]
    rows = [row for row in rows if row['operation'].split('/', 2)[1] == slug]
    usd = lambda picked: sum(row['accounted'] for row in picked) / 1e6
    return {'actual_usd': usd(r for r in rows if r['state'] == 'usage_recorded'),
            'held_usd': usd(r for r in rows if r['state'] in ('reserved', 'billing_unresolved')),
            'unknown_usd': usd(r for r in rows if r['state'] == 'outcome_unknown'),
            'accounted_usd': usd(rows), 'calls': len(rows), 'budget_usd': float(build.budget_usd),
            'this_prefix_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/')),
            'flat_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/image/flat/')),
            'reading_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/reading'))}


def checked_inputs(ctx):
    from .round_files_export import LOGO, font_records
    inputs = ctx.build.inputs
    folder = flow.round_root(ctx.build.round)
    if (digest(ctx.build.round.product_brief) != inputs['brief_sha256'] or
            ctx.build.round.pick != inputs['pick'] or sha(folder / 'handoff.json') != inputs['handoff_sha256'] or
            sha(folder / inputs['picture']) != inputs['picture_sha256'] or
            sha(LOGO) != inputs['logo_sha256'] or font_records() != inputs['fonts']):
        raise ValueError('A frozen picture, brief, pick, logo or granted font changed.')
    return folder / inputs['picture']



def read_picture(ctx):
    from .round_files_faces import copy_fields, normalise_reading, validate_inspection
    source = checked_inputs(ctx)
    copied = ctx.root / 'source.png'
    if copied.exists() and sha(copied) != ctx.build.inputs['picture_sha256']:
        raise ValueError('The retained picked picture changed.')
    if not copied.exists():
        shutil.copyfile(source, copied)
    flow.write_json(ctx.root / 'inputs.json', ctx.build.inputs)
    with Image.open(copied) as image:
        size = list(image.size)
    prompt = (
        'Read this one picked picture for print-file extraction. Do NOT design, redraw, repaint or improve it. '
        'Locate the large standalone hero product body FRONT (excluding cap), cap FRONT, '
        'the stand header printed front and stand base strip printed front. Return absolute integer '
        'pixel coordinates in the original image coordinate system. Crop only each printed planar face, '
        'excluding surroundings, perspective side walls and physical thickness. '
        'For the stand header, crop the printed interior artwork, excluding any physical gold arched trim, '
        'metallic rim or surrounding frame. Its print_polygon_px must follow the visible printed-art boundary '
        'inside that trim. If this printed interior is arched, use its full rectangular bounding box and '
        'record the actual arched silhouette; do not include the physical trim in line-art regions. '
        'The squared header corners will be filled only by extending the printed artwork’s own nearest '
        'silhouette-edge pixels. Preserve its interior without stretching, repainting or copying the gold rim. '
        'Count the actual loaded products shown on the stand, including partially occluded back rows; '
        'never substitute the intake stand count. Ignore the standalone hero and loose wand. '
        'Record a box for every loaded bottle, including the visible portion of a partly occluded bottle. '
        'Rows are zero-based from front to back and columns are zero-based from left to right; '
        'count must equal rows times columns. Each bottle must include shade_field naming the supplied '
        'shade_N COPY field that matches its observed shade, or null when unresolved. Never cycle or guess '
        'shades to fill the grid. Identify the hero bottle shade only through its actual shade_N text entry; '
        'if its shade name cannot be read, do not invent a shade text entry. '
        'Separate line art from letters/logo and physical metallic edges. Mark tight line-art regions; '
        'exclude physical cap reflections, acrylic edges, liquid and surrounding frame thickness. '
        'Give a tight box for EVERY visible word or logo, with enough room to cover antialiased lettering. '
        'Words are specified ONLY by the COPY field key below, never instructions or invented text. '
        'A printed word that means a COPY field takes that field even when the picture misspells it; '
        'the files set the field’s exact words. '
        'Use multiple entries for separate Latin and Arabic lines. Every BBROSE mark is kind logo. '
        'rotation is the turn of the lettering as seen: 0 upright, 90 reads bottom to top, '
        '180 upside down, 270 reads top to bottom. For a word set at another angle or along a curve, '
        'give its tight bounding box, the nearest of those turns, and "angle_deg" or "arc": true. '
        'Lettering the picture invented that matches no COPY field (pseudo-script, a decorative calligraphy band) '
        'is neither text nor line art: list it under that panel’s ornament_lettering as '
        '{"path_px":[[x,y],...] along the centre line of the lettering band, in the direction its letters advance '
        '(letter tops on the left-hand side of travel), "height_px": the band’s letter height, "color":"#RRGGBB"}. '
        'Never transcribe it; keep it out of lineart_boxes_px. '
        'colour_print_boxes_px identifies actual decorative colour ink on the body, never the liquid or clear acrylic. '
        'The cap substrate is metal: it is not colour ink. Record hidden/back/side faces as unprinted unless visible '
        'decoration proves otherwise. The one owner change is a square header top; do not invent new artwork. '
        'Return JSON only, following this valid example structure: '
        '{"image_size_px":[1536,1024],"stand":{"rows":2,"columns":3,"count":6,'
        '"bottles":[{"row":0,"column":0,"box_px":[650,500,700,800],"shade_field":"shade_0"},'
        '{"row":0,"column":1,"box_px":[800,500,850,800],"shade_field":"shade_1"},'
        '{"row":0,"column":2,"box_px":[950,500,1000,800],"shade_field":null},'
        '{"row":1,"column":0,"box_px":[675,450,725,750],"shade_field":"shade_0"},'
        '{"row":1,"column":1,"box_px":[825,450,875,750],"shade_field":"shade_1"},'
        '{"row":1,"column":2,"box_px":[975,450,1025,750],"shade_field":null}]},'
        '"panels":{"body_front":{"crop_px":[100,300,200,800],'
        '"print_polygon_px":[[100,300],[200,300],[200,800],[100,800]],'
        '"text":[{"field":"product_latin","box_px":[110,650,190,680],"color":"#D5AF59","rotation":0},'
        '{"field":"shade_0","box_px":[110,700,190,725],"color":"#D5AF59","rotation":0}],'
        '"marks":[],"lineart_boxes_px":[[110,350,190,620]],"colour_print_boxes_px":[]},'
        '"cap_front":{"crop_px":[100,100,200,300],'
        '"print_polygon_px":[[100,100],[200,100],[200,300],[100,300]],"text":[], '
        '"marks":[{"kind":"logo","box_px":[125,150,175,200],"color":"#D5AF59","rotation":0}],'
        '"lineart_boxes_px":[],"colour_print_boxes_px":[]},'
        '"stand_header":{"crop_px":[600,100,1200,400],'
        '"print_polygon_px":[[600,200],[750,125],[900,100],[1050,125],[1200,200],[1200,400],[600,400]],'
        '"text":[{"field":"product_latin","box_px":[700,300,1100,340],"color":"#D5AF59","rotation":0}],'
        '"marks":[],"lineart_boxes_px":[],"colour_print_boxes_px":[],'
        '"ornament_lettering":[{"path_px":[[620,190],[900,112],[1180,190]],"height_px":28,"color":"#D5AF59"}]},'
        '"stand_base":{"crop_px":[600,800,1200,900],'
        '"print_polygon_px":[[600,800],[1200,800],[1200,900],[600,900]],'
        '"text":[],"marks":[],"lineart_boxes_px":[],"colour_print_boxes_px":[],"ornament_lettering":[]}},'
        '"unprinted_faces":[{"face":"back","reason":"not shown"}],"notes":["observed facts only"]}. '
        'Only list observations you can locate in the picture. Every coordinate, count, field and arrangement '
        'in the example is illustrative: measure this picture and use only the available COPY fields below. '
        'Return all four panel objects with these fields; use empty arrays when no such element is observed '
        '(ornament_lettering may be omitted where there is none). '
        '\nIMAGE SIZE: ' + json.dumps(size) +
        '\nCOPY FIELDS: ' + json.dumps(copy_fields(ctx.brief), ensure_ascii=False) +
        '\nPRODUCT MATERIAL: ' + ctx.brief['material'])
    destination = ctx.root / 'reading-call.json'
    call = ctx.text_call('locate-picture', prompt, destination, images=[('Picked picture, unchanged', copied)],
                         max_tokens=16384, ceiling=2.0)
    try:
        inspection = validate_inspection(normalise_reading(call['payload'], size, ctx.brief), size, ctx.brief)
        stand = inspection['stand']
        if (any(not isinstance(stand[key], int) or isinstance(stand[key], bool) or stand[key] < 1
                for key in ('rows', 'columns', 'count')) or stand['rows'] * stand['columns'] != stand['count']
                or stand['count'] > 100):
            raise ValueError('The observed rows, columns and product count must agree.')
        if not isinstance(inspection.get('unprinted_faces'), list) or not isinstance(inspection.get('notes'), list):
            raise ValueError('The reading must list unprinted faces and observed findings.')
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        ctx.reject_result(destination, str(exc))
        raise
    flow.write_json(ctx.root / 'inspection.json', inspection)
    return inspection


def prepare_stand(ctx):
    from .round_files_gate import build_stand
    result = build_stand(ctx.brief, read(ctx.root / 'inspection.json'), ctx.root / 'stand')
    flow.write_json(ctx.root / 'stand.json', result)
    return result


def _relative(ctx, path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(ctx.root.resolve()):
        raise ValueError('A files artifact escaped its build folder.')
    return str(resolved.relative_to(ctx.root.resolve()))


def build_outputs(ctx, drawn, revision):
    """The faces composed and written: bottle front, cap and stand through the writer (native Illustrator save and
    reopen in the worker), each face rendered back from its file for the eye, and the built drawing."""
    from .round_files_export import export_object
    from .round_files_faces import shade_loading
    folder = ctx.root / 'revisions' / str(revision)
    manifest = folder / 'outputs.json'
    inspection, geometry = read(ctx.root / 'inspection.json'), read(ctx.root / 'stand.json')
    binding = {'faces': digest({key: row['face_sha256'] for key, row in drawn.items()}),
               'source': ctx.build.inputs['picture_sha256'], 'native': ctx.native, 'inspection': digest(inspection),
               'geometry': digest(geometry), 'contract': 'picture_design_intent/1'}
    if ctx.brief.get('copy_sources'):
        from .round_files_faces import copy_fields
        binding['copy'] = digest(copy_fields(ctx.brief))
    if manifest.exists():
        prior = read(manifest)
        if prior['binding'] != binding or any(sha(ctx.root / path) != value for path, value in prior['pins'].items()):
            raise ValueError('A retained files revision changed.')
        return prior
    folder.mkdir(parents=True, exist_ok=True)
    specs, placements = faces.specs(drawn, inspection, ctx.brief, geometry, folder)
    flow.write_json(folder / 'specs.json', specs)
    objects = [export_object(spec, folder, native=ctx.native) for spec in specs]
    views = faces.face_views(objects, placements, folder / 'views')
    loading = shade_loading(inspection, ctx.brief)
    drawing_record = faces.drawing(views, ctx.brief, geometry, loading, folder / 'drawing')
    pins = {_relative(ctx, path): sha(path) for path in folder.rglob('*') if path.is_file()}
    result = {'binding': binding, 'revision': revision, 'specs': specs, 'objects': objects,
              'placements': placements, 'views': {key: _relative(ctx, path) for key, path in views.items()},
              'drawing': _relative(ctx, drawing_record['file']), 'drawing_record': drawing_record, 'pins': pins}
    flow.write_json(manifest, result)
    return result


def tag_completed(build):
    import fcntl
    name = build.inputs['completion_tag']
    if not name or build.state != 'complete' or 'pytest' in sys.modules or not getattr(settings, 'ROUND_COMMIT_ARTIFACTS', True):
        return
    if name != 'round-gloss-files-a':
        raise ValueError('Unrecognized owner-requested closing tag.')
    with (flow.REPO/'.git/round-artifacts.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exists = subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/'+name], cwd=flow.REPO, capture_output=True)
        if exists.returncode == 0:
            relative = str((flow.round_root(build.round)/'files/publication.json').relative_to(flow.REPO))
            saved = subprocess.run(['git', 'show', name+':'+relative], cwd=flow.REPO, check=True, capture_output=True)
            if json.loads(saved.stdout) != build.publication:
                raise ValueError('The closing tag belongs to different files; it will not move.')
            return
        subprocess.run(['git', 'tag', '-a', name, '-m', 'Owner-picked picture built through the app; files and designer verdict retained'],
                       cwd=flow.REPO, check=True, capture_output=True)



def run_step(name, ctx):
    """The reading and the die; the faces and the files are the gate's (round_files_gate)."""
    checked_inputs(ctx)
    for step_name, path in (('read', 'inspection.json'), ('stand', 'stand.json')):
        saved = ctx.build.steps[step_name]
        if saved['state'] == 'complete' and read(ctx.root / path) != saved['result']:
            raise ValueError('A completed files step changed: ' + step_name)
    return {'read': read_picture, 'stand': prepare_stand}[name](ctx)
