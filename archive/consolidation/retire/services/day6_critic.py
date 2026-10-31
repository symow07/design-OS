"""Day 6 critic calls: ten dimensions per surface on the composed stand, and the bottle per F4.

The critic observes; code decides (concept_quality.evaluate, thresholds unchanged).
Every call reserves inside the owner's Day 6 allowance (10 USD, critic calls only)
before payment, inside the Shanghai-day and rescue caps of spend_reservation.
"""
from pathlib import Path
import base64, hashlib, json
from django.conf import settings
from .spend_reservation import paid_operation
from .concept_quality import DIMENSIONS, evaluate

BUDGET_PREFIX = 'day6/'
BUDGET_CAP = 10
REQUIRED_HEADER_COPY = ['BBROSE', 'SUN REPAIR', 'SERUM', 'Arabic line', 'Revive + Smooth']
DIMENSION_SCHEMA = {'type': 'object', 'properties': {'score': {'type': 'number', 'minimum': 1, 'maximum': 10},
                    **{k: {'type': 'string'} for k in ['observation', 'location', 'repair']}},
                    'required': ['score', 'observation', 'location', 'repair']}


MAX_EDGE_PX = 1568          # the provider resamples longer edges to this; sending more only risks the 10 MB request bound
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def critic_image_bytes(path):
    """PNG bytes the critic actually sees: the file as is when it fits, else resampled to the provider's edge bound."""
    import io
    from PIL import Image
    raw = Path(path).read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        longest = max(im.size)
        if len(raw) <= MAX_IMAGE_BYTES and longest <= MAX_EDGE_PX:
            return raw, {'resampled': False, 'size_px': list(im.size)}
        scale = MAX_EDGE_PX / longest
        resized = im.convert('RGB').resize((max(1, round(im.size[0] * scale)), max(1, round(im.size[1] * scale))), Image.Resampling.LANCZOS)
        out = io.BytesIO(); resized.save(out, format='PNG', optimize=True)
    data = out.getvalue()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Critic image still exceeds the provider bound after resampling: %d bytes' % len(data))
    return data, {'resampled': True, 'size_px': list(resized.size), 'source_size_px': list(im.size), 'method': 'LANCZOS to %d px longest edge' % MAX_EDGE_PX}


def _image(path):
    data, _ = critic_image_bytes(path)
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(data).decode()}}


def _sent(path):
    data, note = critic_image_bytes(path)
    return dict(note, source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), sent_sha256=hashlib.sha256(data).hexdigest(), sent_bytes=len(data))


def _unwrap(value):
    return value['value'] if isinstance(value, dict) and set(value) == {'value'} else value


def _schema(facts):
    return {'type': 'object', 'properties': {
        'dimensions': {'type': 'object', 'properties': {k: DIMENSION_SCHEMA for k in DIMENSIONS}, 'required': list(DIMENSIONS)},
        'hard_failures': {'type': 'array', 'items': {'type': 'string'}}, 'observations': {'type': 'string'},
        'golden_facts': {'type': 'object', 'properties': facts, 'required': list(facts)}},
        'required': ['dimensions', 'hard_failures', 'observations', 'golden_facts']}


def _call(content, destination, *, operation, facts, rules, extra):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Critic observations are immutable per attempt.')
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=120)
    response = paid_operation(client.messages.create, provider='anthropic', operation=operation,
                              reservation_prefix=BUDGET_PREFIX, reservation_cap=BUDGET_CAP, model=settings.CLAUDE_MODEL_FAST,
                              max_tokens=3000, messages=[{'role': 'user', 'content': content}],
                              tools=[{'name': 'record_review', 'description': 'Record independent image observations and literal counts.',
                                      'input_schema': _schema(facts)}], tool_choice={'type': 'tool', 'name': 'record_review'})
    raw = '\n'.join(b.text for b in response.content if getattr(b, 'type', '') == 'text')
    structured = next((b.input for b in response.content if getattr(b, 'type', '') == 'tool_use' and getattr(b, 'name', '') == 'record_review'), None)
    payload = structured if isinstance(structured, dict) else {}
    observed = payload['golden_facts'] if isinstance(payload.get('golden_facts'), dict) else {}
    observed = {k: _unwrap(v) for k, v in observed.items()}
    payload['golden_facts'] = observed
    hard = payload['hard_failures'] if isinstance(payload.get('hard_failures'), list) else None
    if hard is not None:
        payload['hard_failures'] = [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in hard]
        for good, reason in rules(observed):
            if not good:
                payload['hard_failures'].append(reason)
    record = dict(extra, payload=payload, verdict=evaluate(payload), raw_response=raw,
                  reservation_id=getattr(response, '_rescue_reservation_id', None),
                  response_artifact=getattr(response, '_rescue_response_artifact', None),
                  usage=response.model_dump(mode='json').get('usage'), model=settings.CLAUDE_MODEL_FAST,
                  golden_checks_are_visual='Image counts/copy need human confirmation; exact mm geometry remains deterministic scene authority.',
                  weights_changed=False)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


def critique_surface(render_png, artwork_png, destination, *, surface_id, size_mm, view, source_status):
    """Ten dimensions for one surface, judged on the composed deterministic stand render."""
    prompt = ('Judge the attached deterministic render of the twelve-bottle countertop display with the D1 "Amber Current" '
              'artwork mapped onto its real surfaces (first image, view: %s). Focus on surface %s (%s x %s mm; the second image '
              'is that surface\'s flat print artwork). The render is a deterministic material approximation, not a photograph: '
              'judge the designed hierarchy, legibility, quiet space, material depth and ownable coherent character of this '
              'surface within the composed stand, not render realism. Return JSON only through record_review with dimensions, '
              'hard_failures, observations, golden_facts. For each dimension: score 1..10, observation, location, repair '
              '(nonempty if score<8). Dimensions: %s. Required facts: exactly 12 bottles in 3 stepped rows of 4 (count row by row; '
              'the geometry is deterministic, so a different count means the render or the view failed, say so); header copy '
              'BBROSE, SUN REPAIR, SERUM, the Arabic line and Revive + Smooth present (header surfaces only; for other surfaces '
              'report what you see); countertop display, not booth or floor. surface_visible: whether surface %s is actually '
              'visible in this view. artwork_matches_flat: whether the artwork you see on that surface corresponds to the flat '
              'artwork image. Do not claim millimetre verification from an image. Do not reward the brief; inspect pixels. '
              'Measured-vs-composed status of this surface in the record: %s. No automatic pass field.'
              % (view, surface_id, size_mm[0], size_mm[1], ', '.join(DIMENSIONS), surface_id, source_status))
    facts = {'visible_bottle_count': {'type': 'integer'}, 'row_counts': {'type': 'array', 'items': {'type': 'integer'}, 'minItems': 3, 'maxItems': 3},
             **{k: {'type': 'boolean'} for k in ['countertop', 'required_header_copy_present', 'surface_visible', 'artwork_matches_flat']}}
    def rules(o):
        return [(o.get('visible_bottle_count') == 12, 'Visible bottle count must be 12'), (o.get('row_counts') == [4, 4, 4], 'Three rows of four required'),
                (o.get('countertop') is True, 'Countertop target unresolved or changed'), (o.get('surface_visible') is True, 'Surface not visible in the judged view'),
                (o.get('artwork_matches_flat') is True, 'Mapped artwork does not correspond to the flat artwork')]
    extra = {'kind': 'surface', 'surface_id': surface_id, 'view': view, 'size_mm': list(size_mm), 'source_status': source_status,
             'render_sha256': hashlib.sha256(Path(render_png).read_bytes()).hexdigest(), 'artwork_sha256': hashlib.sha256(Path(artwork_png).read_bytes()).hexdigest(),
             'images_sent': {'render': _sent(render_png), 'artwork': _sent(artwork_png)}}
    return _call([_image(render_png), _image(artwork_png), {'type': 'text', 'text': prompt}], destination,
                 operation=BUDGET_PREFIX + 'critic/stand/' + surface_id, facts=facts, rules=rules, extra=extra)


def critique_bottle(projected_png, grey_png, destination, *, revision, deviation):
    """F4: illustration and fidelity judged on the projected bottle beside concept 147; grey flat supplementary."""
    prompt = ('Two images. First: the accepted concept 147 (left) beside the revision %s projected bottle (right) at one scale. '
              'Second, supplementary diagnostic only: the revision %s flat artwork on neutral grey. Judge the PROJECTED bottle '
              'beside the concept. The swoosh is now a vector brand device (cream fill with a deep-amber shadow band); its '
              'named deviation from the concept is "%s". Score pattern_support as the illustration dimension: how faithfully '
              'and how well the vector device carries the concept\'s gesture, weight, placement and colour on the amber ground. '
              'Score the other dimensions on the projected bottle. Return JSON only through record_review with dimensions, '
              'hard_failures, observations, golden_facts. For each dimension: score 1..10, observation, location, repair '
              '(nonempty if score<8). Dimensions: %s. Required facts: product_identity_matches (clear glass serum bottle, '
              'chrome spray cap, amber liquid, same proportions as the concept); required_copy_present (BBROSE, SUN REPAIR, '
              'SERUM, Arabic line, Revive + Smooth); swoosh_present; swoosh_position_matches_concept. Do not claim millimetre '
              'verification from an image. Inspect pixels, not the brief. No automatic pass field.'
              % (revision, revision, deviation, ', '.join(DIMENSIONS)))
    facts = {k: {'type': 'boolean'} for k in ['product_identity_matches', 'required_copy_present', 'swoosh_present', 'swoosh_position_matches_concept']}
    def rules(o):
        return [(o.get('product_identity_matches') is True, 'Product identity unresolved or changed'), (o.get('required_copy_present') is True, 'Required copy unresolved or missing'),
                (o.get('swoosh_present') is True, 'Swoosh device absent'), (o.get('swoosh_position_matches_concept') is True, 'Swoosh position differs from concept')]
    extra = {'kind': 'bottle', 'revision': revision, 'judged_on': 'projected bottle beside concept 147; grey flat supplementary (F4)',
             'projected_sha256': hashlib.sha256(Path(projected_png).read_bytes()).hexdigest(), 'grey_sha256': hashlib.sha256(Path(grey_png).read_bytes()).hexdigest(),
             'images_sent': {'projected': _sent(projected_png), 'grey': _sent(grey_png)},
             'illustration_dimension': 'pattern_support', 'stop_rule': 'owner §5: illustration < 7 on the projected bottle stops swoosh work for the rescue'}
    return _call([_image(projected_png), _image(grey_png), {'type': 'text', 'text': prompt}], destination,
                 operation=BUDGET_PREFIX + 'critic/bottle/revision-%s' % revision, facts=facts, rules=rules, extra=extra)
