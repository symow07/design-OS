"""Durable original-image calls for the ideas-only round pipeline."""
from __future__ import annotations

import base64
import binascii
from contextlib import ExitStack
from io import BytesIO
import json
import math
from pathlib import Path
import sys

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from . import spend_reservation as spend
from .round_calls import IMAGE_MODEL, STREAM_PARTIAL_IMAGES, RoundContext, sha, streamed_edit
from .round_flow import commit_artifacts, write_json


def design_image_estimate(prompt):
    """Reserve from the configured tariff; settlement uses provider usage.

    Historical high-quality 1536x1024 replies use 5,488 output tokens. Reserve
    8,192, plus a conservative byte-per-token prompt allowance and 1,024 input
    tokens of overhead, with another 25 percent margin. No reference images
    are sent by this endpoint. Missing tariffs fail before any provider call.
    """
    tariff = getattr(settings, 'OPENAI_IMAGE_PRICES', {}).get(IMAGE_MODEL, {})
    prices = [tariff.get(key) for key in ('text_input', 'image_output', 'image_input')]
    if any(isinstance(price, bool) or not isinstance(price, (int, float))
           or not math.isfinite(price) or price <= 0 for price in prices):
        raise ValueError('A current image tariff is required before reserving an ideas image.')
    text_price, output_price, _ = prices
    return math.ceil(1.25 * ((len(prompt.encode('utf-8')) + 1024) * text_price
                            + 8192 * output_price)) / 1_000_000


#: A gpt-image-2 input picture, reserved generously (the 1600 px library previews are resized by the provider).
REFERENCE_INPUT_TOKENS = 8192
MAX_REFERENCES = 3


def reference_image_estimate(prompt, count):
    """A board drawn from house-library pictures: the original reservation plus each input picture's tokens."""
    image_price = getattr(settings, 'OPENAI_IMAGE_PRICES', {}).get(IMAGE_MODEL, {}).get('image_input')
    if isinstance(image_price, bool) or not isinstance(image_price, (int, float)) or not math.isfinite(image_price) or image_price <= 0:
        raise ValueError('A current image-input tariff is required before reserving a board drawn from references.')
    return design_image_estimate(prompt) + math.ceil(1.25 * count * REFERENCE_INPUT_TOKENS * image_price) / 1_000_000


class IdeasContext(RoundContext):
    # Twenty accepted originals remain the stage target. Failed/rejected paid
    # attempts count too; the round's dollar cap remains the binding guard.
    image_attempt_cap = 40

    def _reference(self, item):
        """A house-library picture chosen at research time, sent only while its bytes match their record."""
        from . import image_guard
        path = Path(item['path']).resolve()
        if image_guard._under(path, image_guard.WEB_ROOTS) or not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('A library reference changed or is not a house-library picture; no image call made.')
        with Image.open(path) as image:
            size = list(image.size)
        return {'id': item['id'], 'role': 'mood board reference', 'library_sha256': item['library_sha256'],
                'path': str(path), 'sha256': item['sha256'], 'px': size, 'sent_unchanged': True}

    def design_image_call(self, operation, prompt, output, *, references=(), template=None, style=None):
        """Generate one original PNG, preserving raw replies across deliveries.

        ``output`` is a candidate directory inside this round. The provider
        bytes are saved unchanged as raw.png beside the durable call records.
        Only an explicit owner retry can replace a known invalid response;
        an unknown provider outcome always retains its reservation. A mood
        board may carry up to three house-library pictures as references,
        recorded by hash; without them the request identity is unchanged.
        ``template`` and ``style``: a design painted on the stand's flat die
        (owner, 2026-10-28) — one edit, image 1 the die's template and its
        mask, image 2 the picked board, at the template's own canvas.
        """
        from . import image_guard

        destination = self._destination(Path(output) / 'image-call.json')
        if settings.IMAGE_MODEL != IMAGE_MODEL or image_guard.competitor_in(prompt):
            raise ValueError('Round image model or prompt is outside the allowed boundary.')
        if len(references) > MAX_REFERENCES:
            raise ValueError('A board takes at most three library references.')
        args = {'model': IMAGE_MODEL, 'quality': 'high', 'size': '1536x1024',
                'prompt': prompt, 'n': 1, 'output_format': 'png'}
        identity = {'protocol': 'ideas-original-v1', 'endpoint': 'images.generate', **args}
        estimate = design_image_estimate(prompt)
        inputs = [self._reference(item) for item in references]
        flat = [self._input(template), self._input(style)] if template is not None else []
        if flat:
            if inputs or '%dx%d' % tuple(flat[0]['px']) not in ('1536x1024', '1024x1536'):
                raise ValueError('A flat design is the die\'s template and the picked board, on a full canvas.')
            args['size'] = '%dx%d' % tuple(flat[0]['px'])
            identity = {'protocol': 'designer-flat-die-v1', 'endpoint': 'images.edit', **args, 'inputs': flat,
                        'mask': flat[0], 'stream': {'partial_images': STREAM_PARTIAL_IMAGES}}
            estimate = reference_image_estimate(prompt, len(flat))
        elif inputs:
            identity = {'protocol': 'designer-board-references-v1', 'endpoint': 'images.edit', **args,
                        'references': inputs}
            estimate = reference_image_estimate(prompt, len(inputs))
        operation = operation if operation.startswith('image/') else 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai',
            operation=operation, estimate=estimate)
        raw_image = destination.parent / 'raw.png'
        if cached is not None:
            if not raw_image.exists() or sha(raw_image) != cached['output_sha256']:
                raise ValueError('Saved paid image changed; no repurchase.')
            return cached

        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
        else:
            if request['started_attempts']:
                raise ValueError('Prior image outcome is unknown; reservation held, no repeated payment.')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Round fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                if flat:
                    with ExitStack() as stack:
                        opened = [stack.enter_context(Path(item['path']).open('rb')) for item in flat]
                        mask = stack.enter_context(Path(flat[0]['path']).open('rb'))
                        response = streamed_edit(self.image_client, destination.with_suffix('.stream.json'),
                                                 image=opened, mask=mask, **args)
                elif inputs:
                    with ExitStack() as stack:
                        opened = [stack.enter_context(Path(item['path']).open('rb')) for item in inputs]
                        response = self.image_client.images.edit(image=opened, **args)
                else:
                    response = self.image_client.images.generate(**args)
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                write_json(destination.with_suffix('.error.json'), {
                    'error_type': type(exc).__name__, 'http_status': status,
                    'reservation_id': request['reservation_id']})
                commit_artifacts(self.round, f'{operation}: provider failure retained')
                raise
            raw = spend._plain(response)
            write_json(raw_path, raw)
            commit_artifacts(self.round, f'{operation}: raw image reply saved')

        # A malformed image is still a billed reply. Reconcile before decoding.
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)
        usage = raw.get('usage') if isinstance(raw, dict) else None

        def reject_image(reason):
            self._finish(destination, request, dict(identity, status='validation_failed',
                         usage=usage, validation_error=reason), operation=operation, image=True)
            raise ValueError(reason)

        data = raw.get('data') if isinstance(raw, dict) else None
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            reject_image('Exactly one paid image is required; reply retained.')
        item = data[0]
        if item.get('b64_json'):
            try:
                image_bytes = base64.b64decode(item['b64_json'], validate=True)
            except (binascii.Error, ValueError, TypeError):
                reject_image('Paid image bytes are not valid base64; reply retained.')
        elif item.get('url'):
            from apps.pipeline.agents.image_producer import download_image_bytes
            # Local download errors recover from the saved reply, never a new purchase.
            image_bytes = download_image_bytes(item['url'])
        else:
            reject_image('Paid image bytes missing; reply retained.')
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                dimensions, image_format = image.size, image.format
        except (UnidentifiedImageError, OSError, ValueError, TypeError):
            reject_image('Paid image bytes cannot be decoded; reply retained.')
        if image_format != 'PNG':
            reject_image('Provider image is not PNG; paid reply retained.')
        if list(dimensions) != (flat[0]['px'] if flat else [1536, 1024]):
            reject_image('Provider image has the wrong dimensions; paid reply retained.')
        # Keep byte identity: do not re-encode even a valid PNG. Local write errors
        # leave the saved provider reply recoverable without buying another image.
        raw_image.write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete',
            output_sha256=sha(raw_image), output_px=list(dimensions), usage=usage),
            operation=operation, image=True)
