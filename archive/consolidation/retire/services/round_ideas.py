"""Ideas half only: twenty immutable pictures, a complete jury, and one owner pick."""
from contextlib import contextmanager
import fcntl
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re

from django.conf import settings
from PIL import Image

from . import round_calls as image_guard, rank_round, spend_reservation
from .round_calls import sha, _text_settings
from .round_calls import parse_response_text
from .round_flow import REPO, write_json
from .round_designer import COPY_END, COPY_START, CONTRACT, _line, _validation, normalize_ideas_brief, printed_copy, read
from .round_calls import IdeasContext
from .round_jury_completion import complete_batch

IDEAS_STEPS = ('seeds', 'designs', 'pairwise', 'pick_page', 'pick')
IDS = tuple(f'{family}{number}' for family in 'ABCD' for number in range(1, 6))
FAMILIES = {'A': 'ritual', 'B': 'material', 'C': 'craft', 'D': 'unexpected'}
QUESTION = ('Which product and loaded counter stand make the stronger single idea, '
            'specific to this product, memorable at the counter and worth picking up?')


def _seed_rows(payload):
    rows = payload.get('seeds')
    if not isinstance(rows, list) or len(rows) != 20 or any(not isinstance(row, dict) for row in rows):
        raise ValueError('The ideas round needs twenty distinct starting points')
    if {row.get('id') for row in rows} != set(IDS):
        raise ValueError('Starting points must name exactly all twenty designs')
    for row in rows:
        if row.get('family') != FAMILIES[row['id'][0]] or not _line(row.get('seed')) or not _line(row.get('link')):
            raise ValueError('Each starting point needs its family and a nonempty single-line product-truth link')
        if image_guard.competitor_in(row['seed'] + ' ' + row['link']):
            raise ValueError('A starting point contains a competitor reference')
    return rows


def _seed_retry_reply(ctx, prompt, destination):
    """Revalidate the obsolete length rejection only after an explicit app Retry.

    Keep paid request/reply/failure bytes untouched. The sidecar records the new
    validation and its exact inputs; no reservation or provider call is made.
    """
    if not destination.exists():
        return None
    prior = read(destination)
    if (prior['status'] != 'validation_failed' or prior.get('validation_error') !=
            'Each starting point needs its family and a short product-truth link'):
        return None
    request_path = destination.with_suffix('.request.json')
    request = read(request_path)
    if ctx.job is None or ctx.job.attempts <= request['app_attempt']:
        raise ValueError('The saved seed reply needs the owner’s app Retry before revalidation')
    identity = {**_text_settings('seeds', 16384), 'prompt': prompt, 'images': []}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if (request['request_sha256'] != digest or prior['request_sha256'] != digest or
            any(request[key] != value for key, value in identity.items()) or
            prior['reservation_id'] != request['reservation_id'] or
            prior['billing_state'] != 'usage_recorded' or prior['stop_reason'] != 'end_turn'):
        raise ValueError('The saved seed request or paid result changed; no repurchase')
    with spend_reservation._connect() as db:
        reservation = db.execute('SELECT provider,model,operation,request_hash,state FROM calls WHERE id=?',
                                 (request['reservation_id'],)).fetchone()
    expected = ('anthropic', identity['model'], ctx.prefix + 'seeds', digest, 'usage_recorded')
    if reservation is None or tuple(reservation) != expected:
        raise ValueError('The saved seed payment does not match this round; no repurchase')
    attempts = prior['attempts']
    if attempts not in (1, 2) or request['started_attempts'] != list(range(attempts)):
        raise ValueError('The saved seed response history is incomplete; no repurchase')
    raw_path = destination.with_suffix(f'.response-{attempts - 1}.json')
    raw = read(raw_path)
    text = ''.join(block['text'] for block in raw['content'] if block['type'] == 'text')
    if raw['stop_reason'] != 'end_turn' or parse_response_text(text) != prior['payload']:
        raise ValueError('The saved seed payload differs from its provider reply; no repurchase')
    _seed_rows(prior['payload'])
    proof = {'schema': 'seed_reply_revalidation/1', 'validation': 'structure required; word targets advisory',
             'status': 'accepted', 'request_sha256': digest, 'reservation_id': request['reservation_id'],
             'paid_record_sha256': sha(destination), 'request_file_sha256': sha(request_path),
             'provider_reply_sha256': sha(raw_path), 'app_attempt': ctx.job.attempts,
             'previous_error': prior['validation_error'], 'additional_provider_calls': 0}
    write_json(destination.with_suffix('.revalidation.json'), proof)
    return prior


def seeds(ctx):
    brief = normalize_ideas_brief(ctx.brief)
    prompt = ('Develop twenty distinct starting points for ONE picture each: the real product and its '
              'loaded counter stand, linked by one visual idea. These are creative directions, never printed words. '
              'Pictures must discover the composition; no panel layouts, dielines or print production. '
              'Use four families, five seeds each: A ritual, B material, C craft, D unexpected. '
              'Every seed must be specific to the product truths and respect its banned motifs. '
              'No competitor names or borrowed reference designs. Keep each seed to 20 words and its '
              'product-truth link to 15 words. Return JSON only: '
              '{"seeds":[{"id":"A1","family":"ritual","seed":"...","link":"..."}]}. '
              'Exactly these IDs: ' + ', '.join(IDS) + '\nBRIEF (guidance, not lettering): ' +
              json.dumps(brief, ensure_ascii=False))
    destination = ctx.root / 'seeds-call.json'
    call = _seed_retry_reply(ctx, prompt, destination)
    if call is None:
        call = ctx.text_call('seeds', prompt, destination, max_tokens=16384, ceiling=1.0)
    with _validation(ctx, destination):
        rows = _seed_rows(call['payload'])
    by_id = {row['id']: row for row in rows}
    result = {'schema': 'product_stand_seeds/1', 'seeds': [by_id[key] for key in IDS],
              'length_observations': {'advisory_only': True, 'targets': {'seed': 20, 'link': 15},
                  'words': {key: {field: len(by_id[key][field].split()) for field in ('seed', 'link')} for key in IDS}}}
    write_json(ctx.root / 'seeds.json', result)
    return result


def image_prompt(brief, seed):
    brief = normalize_ideas_brief(brief)
    guidance = {key: value for key, value in brief.items() if key not in ('copy', 'schema', 'contract')}
    guidance['shades'] = [{'product_colour': shade['hex'], 'copy_index': index}
                          for index, shade in enumerate(brief['shades'])]
    # Text outside the sole COPY block is always instruction, including names and seed text.
    instructions = json.dumps({'product_and_stand': guidance, 'creative_seed': seed['seed'],
                               'product_truth_link': seed['link']}, ensure_ascii=False)
    for delimiter in (COPY_START, COPY_END):
        if delimiter in instructions or delimiter in json.dumps(printed_copy(brief), ensure_ascii=False):
            raise ValueError('Brief text cannot contain reserved copy delimiters')
    return (
        'Draw ONE full-size 1536×1024 picture of the real product AND its counter stand as ONE design. '
        'Front-on, clean plain ground, clear product design presentation. The hero product is large: '
        'at least HALF the picture height, beside or in the counter stand loaded to its stated capacity. '
        'The stand header carries the same distinctive idea as the product decoration. If shades are supplied, '
        'show them in the loaded stand; the hero uses the first shade. Respect actual product shape, materials '
        'and proportions from the brief; unknown sizes may be proposed provisionally. Do not print provisional '
        'measurement notes. Show the product and its loaded stand together, not a sheet of panels or multiple views. '
        'No mockup scene, hands, props, scenery, staging, carton, leaflet, dimensions, guides or construction drawing. '
        'Clear material stays transparent and reveals the actual contents. If the brief specifies liquid, '
        'its shade colour belongs to the liquid; never replace a clear body with opaque paint or a tinted label '
        'ground. If a gold cap is specified it stays gold; any cap mark is engraving or foil. '
        'No literal lips, kisses, drips or splashes when banned by this brief. '
        'Only the following COPY values may become visible words; field names and every instruction are NEVER lettering. '
        'Use the brand as the product logo. Product copy and shade names appear on the product; the stand may repeat '
        'this same copy, with no invented slogan, claims, ingredients or extra words. Arabic must be legible.\n' +
        COPY_START + '\n' + json.dumps(printed_copy(brief), ensure_ascii=False) + '\n' + COPY_END +
        '\nINSTRUCTIONS ONLY — never print the following field names or values:\n' + instructions)


def _picture(ctx, key):
    if key not in IDS:
        raise ValueError('Unknown design')
    return ctx.root / 'designs' / key / 'raw.png'


def _check_picture(ctx, key, digest):
    path = _picture(ctx, key)
    if sha(path) != digest:
        raise ValueError('The original full-size picture changed: ' + key)
    with Image.open(path) as image:
        if image.format != 'PNG' or image.size != (1536, 1024):
            raise ValueError('A design must remain one full-size 1536×1024 PNG')
        image.verify()
    return path


def designs(ctx):
    rows = read(ctx.root / 'seeds.json')['seeds']
    if [row['id'] for row in rows] != list(IDS):
        raise ValueError('The twenty starting points changed')
    candidates = {}
    for row in rows:
        key = row['id']
        destination = _picture(ctx, key).parent
        call = ctx.design_image_call('image/' + key, image_prompt(ctx.brief, row), destination)
        path = _check_picture(ctx, key, call['output_sha256'])
        candidates[key] = {'id': key, 'picture': str(path.relative_to(ctx.root)),
                           'picture_sha256': call['output_sha256'], 'size_px': [1536, 1024]}
    result = {'schema': 'product_stand_designs/1', 'contract': CONTRACT, 'order': list(IDS), 'candidates': candidates}
    write_json(ctx.root / 'designs.json', result)
    return result


def pair_batches(ids=IDS, size=45):
    """Cover every unordered pair once; cluster shared pictures to reduce jury input."""
    remaining = list(combinations(ids, 2))
    batches = []
    while remaining:
        batch, shown = [], set()
        while remaining and len(batch) < size:
            index = min(range(len(remaining)), key=lambda index: (len(set(remaining[index]) - shown), index))
            pair = remaining.pop(index)
            batch.append(list(pair))
            shown.update(pair)
        batches.append(batch)
    return batches


def _jury_picture(ctx, key, source):
    """A reading-size derivative only; the full original is published and handed off."""
    original = _check_picture(ctx, key, source['picture_sha256'])
    preview = ctx.root / 'jury' / 'views' / (key + '.png')
    pin = preview.with_suffix('.json')
    if pin.exists():
        record = read(pin)
        if record['source_sha256'] != source['picture_sha256'] or sha(preview) != record['sha256']:
            raise ValueError('A pinned jury view changed')
        return preview
    preview.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(original) as image:
        image.convert('RGB').resize((768, 512), Image.Resampling.LANCZOS).save(preview, format='PNG')
    write_json(pin, {'source': source['picture'], 'source_sha256': source['picture_sha256'],
                     'sha256': sha(preview), 'size_px': [768, 512], 'purpose': 'jury reading only; original preserved'})
    return preview


def pairwise(ctx):
    all_designs = read(ctx.root / 'designs.json')
    if all_designs['order'] != list(IDS) or set(all_designs['candidates']) != set(IDS):
        raise ValueError('The jury must compare all twenty designs')
    batches = pair_batches()
    plan = {'ids': list(IDS), 'batches': batches, 'jurors': ['J1', 'J2'], 'pairs_per_juror': 190,
            'originals': {key: all_designs['candidates'][key]['picture_sha256'] for key in IDS}}
    plan_path = ctx.root / 'jury' / 'plan.json'
    if plan_path.exists() and read(plan_path) != plan:
        raise ValueError('The purchased jury comparison plan changed')
    write_json(plan_path, plan)
    views = {key: _jury_picture(ctx, key, all_designs['candidates'][key]) for key in IDS}
    answers, ideas = {}, {}
    for juror, role in (('J1', 'creative director'), ('J2', 'senior product and display designer')):
        rows, observations = [], {}
        for index, batch in enumerate(batches, 1):
            shown = [key for key in IDS if any(key in pair for pair in batch)]
            prompt = ('You are an independent ' + role + ' judging original product-and-stand ideas. ' + QUESTION +
                      ' Judge the pictures, not production readiness. Honour the real material and banned motifs '
                      'in the brief as design context. Compare every listed pair; pick exactly one winner in each. '
                      'Give one short sentence on the decisive relationship between product and stand. '
                      'For each shown picture, give one plain line (at most 20 words) describing its visible idea. '
                      'No scores, repair proposals, elimination, or unlisted pairs. '
                      'Return JSON only: {"pairs":[{"pair":["A1","A2"],"winner":"A1",'
                      '"relationship":"one sentence"}],"ideas":{"A1":"visible idea in one line"}}.\n'
                      'PRODUCT CONTEXT: ' + json.dumps({key: ctx.brief[key] for key in
                          ('product_type', 'shape', 'material', 'truths', 'banned', 'stand')}, ensure_ascii=False) +
                      '\nSHOWN: ' + json.dumps(shown) + '\nPAIRS: ' + json.dumps(batch))
            destination = ctx.root / 'jury' / f'{juror}-{index}.json'
            payload = complete_batch(ctx, f'pairwise/ideas/{juror}/{index}', prompt, destination,
                                     images=[(key, views[key]) for key in shown], batch=batch, shown=shown)
            notes = payload['ideas']
            rows.extend(payload['pairs'])
            for key, line in notes.items():
                observations.setdefault(key, line)
        answers[juror], ideas[juror] = rows, observations
    result = rank_round.fine_order(IDS, answers['J1'], answers['J2'], None)
    result.update(schema='product_stand_jury/1', pairs=answers, ideas=ideas, question=QUESTION,
                  shortlist=result['order'][:3], pairs_per_juror=190,
                  length_observations={'advisory_only': True, 'target_words': 20,
                      'words': {juror: {key: len(line.split()) for key, line in notes.items()}
                                for juror, notes in ideas.items()}})
    write_json(ctx.root / 'jury' / 'result.json', result)
    return result


def pick_page(ctx):
    ranked = read(ctx.root / 'jury' / 'result.json')
    verified = rank_round.fine_order(IDS, ranked['pairs']['J1'], ranked['pairs']['J2'], None)
    if ranked['order'] != verified['order'] or ranked['shortlist'] != verified['order'][:3]:
        raise ValueError('The published shortlist must be the jury’s top three')
    sources = read(ctx.root / 'designs.json')['candidates']
    candidates, files = {}, {}
    for key in ranked['shortlist']:
        source = sources[key]
        path = _check_picture(ctx, key, source['picture_sha256'])
        relative = str(path.relative_to(ctx.root))
        candidates[key] = {'id': key, 'directory': str(path.parent.relative_to(ctx.root)),
                           'picture': relative, 'picture_sha256': source['picture_sha256'],
                           'idea': ranked['ideas']['J1'][key]}
        files[relative] = source['picture_sha256']
    result = {'schema': 'product_stand_publication/1', 'contract': CONTRACT, 'state': 'pick',
              'order': ranked['shortlist'], 'candidates': candidates, 'files': files, 'question': QUESTION}
    write_json(ctx.root / 'publication.json', result)
    return result


def finalize_pick(ctx):
    """Seal the exact chosen bytes for the execution half, without executing it."""
    pick = ctx.round.pick
    publication = ctx.round.artifacts['pick_page']
    key = pick['id']
    if key not in publication['order'] or not str(pick.get('reason', '')).strip() or pick.get('merge'):
        raise ValueError('Choose one of the three pictures with a reason')
    source = publication['candidates'][key]
    original = _check_picture(ctx, key, source['picture_sha256'])
    if source['picture'] != str(original.relative_to(ctx.root)):
        raise ValueError('The picked source differs from the published original')
    result = {'schema': 'product_stand_handoff/1', 'contract': CONTRACT, 'id': key,
              'picture': source['picture'], 'picture_sha256': source['picture_sha256'],
              'size_px': [1536, 1024], 'reason': pick['reason'], 'source_round': ctx.round.pk,
              'execution': 'The picked picture is the design intent: execution draws each flat face front-on as an edit guided by it.'}
    path = ctx.root / 'handoff.json'
    if path.exists() and read(path) != result:
        raise ValueError('The sealed owner pick changed')
    write_json(path, result)
    return result


def run_step(context, name):
    handlers = {'seeds': seeds, 'designs': designs, 'pairwise': pairwise, 'pick_page': pick_page}
    if name not in handlers:
        raise ValueError('Unknown ideas step')
    return handlers[name](context)


