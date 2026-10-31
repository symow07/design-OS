"""The master's paid context, archived with the Round 1B/1C master pages (the owner's goal of 2026-10-29). Copied
whole from bbrose_design_os/apps/pipeline/services/round_calls.py at a634230 (where paid calls part 2, 7be1f95, had
put it); kept as text, not imported by anything."""

# --- the master's paid context: panel edits, its disjoint $15 scope (from round_master_calls, 2026-10-28) -------------
# Day-two paid boundary: explicit panel edits, durable replies, disjoint $15 scope.

class MasterContext(RoundContext):
    def __init__(self, build, job=None, *, text_client=None, image_client=None):
        super().__init__(build.round, job, text_client=text_client, image_client=image_client)
        self.build = build
        self.round = copy(build.round)
        self.round.budget_usd = build.budget_usd
        self.root = flow.round_root(build.round) / 'master'
        self.brief = build.inputs['brief']
        self.prefix = f'master/{build.round.slug}/'
        self.image_attempt_cap = 96  # bounded panels (32), detail + cleaning + one repair; dollars remain the cap

    def masked_edit(self, operation, prompt, folder, *, target, mask, size="1536x1024"):
        from . import round_calls as image_guard
        destination = self._destination(Path(folder) / 'image-call.json')
        target, mask = Path(target).resolve(), Path(mask).resolve()
        inputs, mask_input = [self._input(target)], self._input(mask)
        if settings.IMAGE_MODEL != IMAGE_MODEL or image_guard.competitor_in(prompt):
            raise ValueError('The master requires gpt-image-2 and a permitted preservation prompt.')
        if size not in ('1536x1024', '1024x1536'):
            raise ValueError('A panel edit requires a supported full-resolution canvas.')
        dimensions = [int(value) for value in size.split('x')]
        if inputs[0]['px'] != dimensions or mask_input['px'] != dimensions:
            raise ValueError('Panel edit must use its recorded full-resolution canvas and mask.')
        with Image.open(mask) as image:
            if image.mode != 'RGBA' or image.getchannel('A').getextrema() != (0, 255):
                raise ValueError('A panel edit needs both editable and protected pixels.')
        identity = {'model': IMAGE_MODEL, 'quality': 'high', 'size': size,
                    'prompt': prompt, 'inputs': inputs, 'mask': mask_input, 'protocol': 'master-panel-edit/1'}
        op = 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai', operation=op, estimate=1.0)
        if cached is not None:
            if sha(destination.parent / 'raw.png') != cached['output_sha256']:
                raise ValueError('Saved master edit changed; no repurchase.')
            return cached
        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
        else:
            if request['started_attempts']:
                raise ValueError('Prior master edit outcome is unknown; reservation held.')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            flow.write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Master fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                with target.open('rb') as source, mask.open('rb') as mask_file:
                    response = self.image_client.images.edit(model=IMAGE_MODEL, quality='high', size=size,
                        prompt=prompt, n=1, image=[source], mask=mask_file)
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                flow.write_json(destination.with_suffix('.error.json'),
                    {'error_type': type(exc).__name__, 'http_status': status, 'reservation_id': request['reservation_id']})
                flow.commit_artifacts(self.round, 'master edit failure retained')
                raise
            raw = spend._plain(response)
            flow.write_json(raw_path, raw)
            flow.commit_artifacts(self.round, 'master raw edit retained')
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)
        def reject_image(exc):
            self._finish(destination, request, dict(identity, status='validation_failed',
                usage=raw.get('usage'), validation_error=str(exc)), operation=op, image=True)
            raise ValueError('Invalid master image reply retained: ' + str(exc)) from exc

        image_url = None
        try:
            data = raw['data']
            if not isinstance(data,list) or len(data) != 1 or not isinstance(data[0],dict):
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
            from .round_calls import download_image_bytes
            # A local download failure retains the settled response for recovery;
            # it is not a malformed provider reply or permission to repurchase.
            image_bytes = download_image_bytes(image_url)
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                if list(image.size) != dimensions:
                    raise ValueError('Edited image has incorrect dimensions')
        except (TypeError, ValueError, UnidentifiedImageError, OSError) as exc:
            reject_image(exc)
        (destination.parent / 'raw.png').write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete',
            output_sha256=sha(destination.parent / 'raw.png'), usage=raw.get('usage')), operation=op, image=True)


def master_scoped_spend(build):
    prefix = f'master/{build.round.slug}/'
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls WHERE substr(operation,1,?)=?', (len(prefix), prefix))]
    return {'actual_usd': sum(row['accounted'] for row in rows if row['state'] == 'usage_recorded') / 1e6,
            'held_usd': sum(row['accounted'] for row in rows if row['state'] in ('reserved', 'billing_unresolved')) / 1e6,
            'accounted_usd': sum(row['accounted'] for row in rows) / 1e6,
            'calls': len(rows), 'budget_usd': float(build.budget_usd)}
