"""The jury (Day 8 §3, D-D8-6): two independent jurors on one candidate, the stricter score standing.

J1 is the creative director of a global prestige beauty house; J2 the senior packaging designer and production lead.
Both see the same fixed anchors (two launched prestige lids = the bar; two concepts the client's leadership rejected =
a floor to clear), the candidate at full size and the candidate shrunk to the shelf view, the brief's facts and the
direction's spec. Each returns the ten raw scores of ``concept_quality`` with observation, location and repair, its
top issues and the stated answers. The computed rules run AFTER the raw scores are recorded: the stricter juror per
dimension, hard failures the union, the pairwise caps, the easy-to-make cap, the collection penalty; then
``concept_quality.evaluate`` decides. The verdict is computed, never model-owned.

The jury model is ``settings.JURY_MODEL`` (claude-opus-5-5 after the Day 8 pre-flight probe), falling back to
``settings.CLAUDE_MODEL_HEAVY`` only when the provider does not know the model; never ``CLAUDE_MODEL_FAST``.
The rubric and the anchor set are prompt-cached (``cache_control``): the system block and the last anchor block
carry the breakpoints, so every call after the first reads them.

Day 9 (D-D9-6, D-D9-7) adds, under rubric v2p only (v1 and v2 send exactly what Day 8 sent): the build's finish proof,
shown between the flat build and the flat build's shelf view in the same call, and J1's desirability answer for the
palette's audience (a "no" is a top issue, never a cap). For the Day 9 sketches and specs it adds the sketch ranking v2
(desirability and buildability per sketch) and the idea check v2 (the ceiling, her purchase, ownability), beside Day 8's
two, which are kept as they were.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import statistics
from pathlib import Path

from django.conf import settings

from apps.pipeline.services.concept_quality import CRITICAL, DIMENSIONS, evaluate, pending
from apps.pipeline.services.day6_critic import critic_image_bytes
from apps.pipeline.services.spend_reservation import paid_operation

SCHEMA = 'jury/1.0'
ANCHOR_EDGE_PX = 768
SHELF_WIDTH_PX = 330
MAX_OUTPUT_TOKENS = 4000           # the JSON is asked to stay under 1,200 tokens; the rest is headroom (a cut answer
                                   # stops at max_tokens and reads as pending, never as a verdict)
PASS_SCORE = 8

BANNED_MOTIFS = (
    'rose flowers, rose petals, rose gardens, garden scenes',
    'arches and glow frames (the "Arch & Bloom" family)',
    'lips and cherries',
    'botanical line-art wallpaper (leaves, vines or florals repeated across the face)',
    'the twelve-rosette, the engine-turned cartouche and the strapwork moiré exactly as the August artworks drew them',
)

SCALE = (
    '10 = a Pentawards-gold palette. 9 = a top prestige launch (the launched anchors). '
    '8 = credible beside them on a Sephora shelf with minor flaws — THE GATE. 7 = good masstige. '
    '6 = competent mass-market. 5 = template or AI-generic. 4 or below = amateur.'
)

DIMENSION_WORDS = {
    'colour_contrast': 'contrast and colour hierarchy — every line readable on its ground, one dominant, one secondary, one accent, never one hue family absorbing everything',
    'focal_hierarchy': 'focal point and the order brand → name → descriptor; what the eye lands on first, second, third',
    'negative_space': 'negative space — deliberate quiet zones, breathing room around the name and the mark',
    'pattern_support': 'pattern and artwork in a SUPPORTING role — crafted, never wallpaper, never clip-art, never a stock illustration as the hero',
    'typography': 'character, pairing and scale of the type, Latin and Arabic as equals; the Arabic set with the same care as the Latin',
    'shelf_impact': 'shelf impact at 2 m — what the shrunk lid still says',
    'premium_cues': 'material and finish cues — foil, deboss, spot varnish, restraint; finishes that a $1B house would specify',
    'distinctiveness': 'brand distinctiveness — an ownable device a shopper would recognise again; not a near-copy of any named brand',
    'trend_relevance': 'relevance to the best palettes on the market today, never to our earlier work',
    'beauty': 'the whole — would a $1B prestige house launch it',
}

RUBRIC_V1 = f"""WHAT YOU ARE LOOKING AT. Each candidate is the design of a cosmetics product's printed face or faces. Usually it is
FLAT PRINT ARTWORK shown front-on, with finishes as flat zones (flat gold = hot foil; a flat marked zone = deboss or spot
varnish); sometimes it is a concept picture or render of the product or its display. What the candidate is — the product,
its size and the kind of picture — is stated with each candidate: judge it as the design of THAT product. The anchors are
PHOTOGRAPHS of launched products. Judge the DESIGN, never the photography, the rendering, the lighting or the product's
three dimensions. The bar is a $1B prestige cosmetics house: modern, professional, minimal in type, layout and colour,
crafted in the artwork, restrained in the branding. A design that looks easy to make is rejected. One colour family
absorbing everything is rejected. Judge against the best palettes on the market today, never against the client's
earlier work.

THE SCALE. {SCALE}

THE TEN DIMENSIONS (score each 1–10 on that scale): {'; '.join(f'{k}: {v}' for k, v in DIMENSION_WORDS.items())}.

HARD FAILURES (list them in hard_failures; any one fails the candidate): a BANNED MOTIF as a main motif —
{'; '.join(BANNED_MOTIFS)} — "rose" may live only in colour, light, texture, geometry and type; a NEAR-COPY — a
shopper could mistake the lid for a named brand's product (name the brand).

EVERY ISSUE = observation + location + the repair a senior designer would make. Observation: what you see.
Location: where on the lid (e.g. "name, upper third", "lower-left quadrant"). Repair: the concrete change.
Be strict and specific; a generic compliment is worthless. Keep the JSON compact: under 1,200 tokens of output."""

RUBRIC_V2 = RUBRIC_V1 + """

READING THE BAR (v2, the calibration's one wording rewrite — no threshold moved). "One colour family absorbing
everything" means a printed design whose one hue swallows the ground, the artwork and the type with no contrasting
role; one metal or one lacquer set against glass, a deep ink or the product's own colours is a material choice, not
that failure. Arabic is judged where the candidate's facts name an Arabic market; a product its facts do not place
there is not marked down for lacking it. A launched product in a photograph is judged as manufactured: its materials
(metal, lacquer, glass, relief) are its artwork."""

#: Day 9 (D-D9-6): a build is judged beside its finish proof. v2p is v2's text plus exactly this sentence, appended under
#: READING THE BAR; v1 and v2 stay byte-identical (Day 8's records and their replay cite them)
FINISH_PROOF_SENTENCE = ('Candidates come as the flat print artwork and its finish proof, which renders the planned '
                         'finishes; judge the design as it will be manufactured, never the rendering.')
RUBRIC_V2P = RUBRIC_V2 + ' ' + FINISH_PROOF_SENTENCE

RUBRICS = {'v1': RUBRIC_V1, 'v2': RUBRIC_V2, 'v2p': RUBRIC_V2P}
#: the Day 9 build protocol runs under these rubrics only: the finish proof shown (D-D9-6) and J1's desirability asked
#: (D-D9-7). A proof goes with them and they go with a proof
DAY9_RUBRICS = ('v2p',)

#: the answer's shape and length — the owner's ≤ 1,200 output tokens a juror (Day 8 §3a); measured on the first call:
#: 1,917 tokens without word limits
ANSWER_WORDS = (
    'Answer with the JSON only, compact — the whole answer under 1,200 tokens: the ten dimensions, each with its score '
    'and an observation, a location and a repair of at most 12 words each; hard_failures; banned_motif_seen and '
    'near_copy_of (or ""); observations in at most 40 words; idea_read in one sentence of at most 25 words and whether it '
    'matches the direction\'s idea line; would_remove and ai_or_template_signs in at most 15 words each; reads_first, '
    'reads_second and reads_third from the shelf view in at most 6 words each; vs_launched_a, vs_launched_b, '
    'vs_rejected_a and vs_rejected_b (is the candidate clearly_better / similar / worse than that anchor as a design); '
    'your top five issues, each field at most 15 words; and your juror-specific answers.')

ROLE_J1 = ("You are J1: the creative director of a global prestige beauty house, judging a new eyeshadow-palette lid for "
           "launch. You care about the idea, beauty, distinctiveness, modernity and shelf impact, and whether the design "
           "language would carry a lipstick, a lip balm and a counter-display header without losing its idea.")
ROLE_J2 = ("You are J2: the senior packaging designer and production lead of that house. You care about typography "
           "(Latin and Arabic), hierarchy, space, colour discipline, finish logic and printability — foil, deboss and "
           "blind lines read as a press would print them; every text line's contrast on its ground; nothing that "
           "would fail on a real press or a real shelf.")

#: D-D9-7: the palette's audience, in the owner's words. It goes into J1's role in every Day 9 call (a build's verdict
#: under v2p, the sketch ranking v2, the idea check v2) and never into Day 8's (``ROLE_J1`` is kept as it was)
AUDIENCE = 'women 18–30, dreamy, magical, bold make-up lovers in Amman, Beirut, Damascus, Ramallah and Tunis'
ROLE_J1_D9 = ROLE_J1 + f' The palette is made for its audience, {AUDIENCE}: you also answer for her.'
#: J1's desirability answer (D-D9-7) as three flat fields: every nested object adds to the provider's compiled grammar
#: (Day 8: "the compiled grammar is too large"), so the answer brings no object of its own
DESIRABILITY_FIELDS = {'would_buy_partly_for_the_lid': {'type': 'boolean'}, 'would_photograph_it': {'type': 'boolean'},
                       'desirability_why': {'type': 'string'}}
#: the question and its word limit, set after ``ANSWER_WORDS`` for J1 alone (J2 is never asked it)
DESIRABILITY_WORDS = ('DESIRABILITY (J1, D-D9-7). Answer for her, the audience named in your role: '
                      'would_buy_partly_for_the_lid — would she buy this palette partly for its lid; would_photograph_it — '
                      'would she photograph it; desirability_why — why, in at most 15 words.')
#: a "no" to either question is a top issue in ``combine`` (D-D9-7), never a cap: the answer's key, the issue's words and
#: the repair
DESIRABILITY_ISSUES = (
    ('would_buy_partly_for_the_lid', 'she would not buy it partly for the lid',
     'Give her a reason to buy the palette for its lid: an idea, a picture and a finish she wants at arm\'s length.'),
    ('would_photograph_it', 'she would not photograph it',
     'Give the lid a moment worth a photograph: a picture, an ornament or a finish that reads in a phone shot.'),
)

_ISSUE = {'type': 'object', 'additionalProperties': False,
          'properties': {'observation': {'type': 'string'}, 'location': {'type': 'string'}, 'repair': {'type': 'string'}},
          'required': ['observation', 'location', 'repair']}
#: one item schema for every dimension (an array with a name enum), so the provider's compiled grammar stays small — ten
#: distinct nested objects compiled too large (Day 8, measured: "The compiled grammar is too large"); normalised back
#: to ``{name: row}`` in code (``_normalise``), so every computed rule reads the same shape
_DIM_ITEM = {'type': 'object', 'additionalProperties': False,
             'properties': {'dimension': {'type': 'string', 'enum': list(DIMENSIONS)}, 'score': {'type': 'number'},
                            'observation': {'type': 'string'}, 'location': {'type': 'string'}, 'repair': {'type': 'string'}},
             'required': ['dimension', 'score', 'observation', 'location', 'repair']}
_PAIR = {'type': 'string', 'enum': ['clearly_better', 'similar', 'worse']}
PAIRWISE = ('launched_a', 'launched_b', 'rejected_a', 'rejected_b')


def verdict_schema(juror, *, desirability=False):
    """The juror's strict answer schema. ``desirability``: J1's D-D9-7 answer as three flat fields (the Day 9 protocol,
    rubric v2p); J2 is never asked it."""
    if desirability and juror != 'J1':
        raise ValueError('Only J1 answers for the audience (D-D9-7).')
    props = {
        'dimensions': {'type': 'array', 'items': _DIM_ITEM},
        'hard_failures': {'type': 'array', 'items': {'type': 'string'}},
        'banned_motif_seen': {'type': 'string'},
        'near_copy_of': {'type': 'string'},
        'observations': {'type': 'string'},
        'idea_read': {'type': 'string'},
        'idea_matches_direction': {'type': 'boolean'},
        'would_remove': {'type': 'string'},
        'ai_or_template_signs': {'type': 'string'},
        'reads_first': {'type': 'string'}, 'reads_second': {'type': 'string'}, 'reads_third': {'type': 'string'},
        **{'vs_' + k: _PAIR for k in PAIRWISE},
        'top_issues': {'type': 'array', 'items': _ISSUE},
    }
    if juror == 'J1':
        props['looks_easy_to_make'] = {'type': 'boolean'}
        props['carries_collection'] = {'type': 'boolean'}
        if desirability:
            props.update(DESIRABILITY_FIELDS)
    else:
        props['foil_and_blind_lines_legible'] = {'type': 'boolean'}
        props['printability_note'] = {'type': 'string'}
    return {'type': 'object', 'additionalProperties': False, 'properties': props, 'required': list(props)}


def _normalise(payload):
    """The provider's array-shaped answer as the dict shape every rule reads: ``dimensions`` keyed by name (each name
    once — a repeated or missing name leaves the answer incomplete, never guessed) and ``pairwise`` as one object."""
    if not isinstance(payload, dict):
        return payload
    rows = payload.get('dimensions')
    if isinstance(rows, list):
        named = {}
        for row in rows:
            if isinstance(row, dict) and row.get('dimension') in DIMENSIONS and row['dimension'] not in named:
                named[row['dimension']] = {k: v for k, v in row.items() if k != 'dimension'}
        payload['dimensions'] = named
    if 'pairwise' not in payload and any('vs_' + k in payload for k in PAIRWISE):
        payload['pairwise'] = {k: payload.pop('vs_' + k, None) for k in PAIRWISE}
    if isinstance(payload.get('top_issues'), list):
        payload['top_issues'] = payload['top_issues'][:5]          # the owner's five; the API takes no array-length limit
    return payload


# --- images ---------------------------------------------------------------------------------------------------------

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resized_png(path, *, long_edge=None, width=None):
    """PNG bytes of the image resized to a long edge or a width (LANCZOS); the file as is when it already fits."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert('RGB')
        w, h = im.size
        if width is not None:
            scale = width / w
        elif long_edge is not None:
            scale = long_edge / max(w, h)
        else:
            scale = 1.0
        if scale < 1.0:
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
        out = io.BytesIO(); im.save(out, format='PNG', optimize=True)
        return out.getvalue(), list(im.size)


def _block(data, *, cache=False):
    block = {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(data).decode()}}
    if cache:
        block['cache_control'] = {'type': 'ephemeral'}
    return block


def anchor_blocks(launched, rejected):
    """The fixed anchor set, in the order every call sends it; the last block carries the cache breakpoint."""
    if len(launched) != 2 or len(rejected) != 2:
        raise ValueError('The jury needs exactly two launched and two rejected anchors.')
    blocks = [{'type': 'text', 'text': 'ANCHORS — launched prestige palettes (photographs; these set the bar, a 9): A then B.'}]
    for path in launched:
        blocks.append(_block(resized_png(path, long_edge=ANCHOR_EDGE_PX)[0]))
    blocks.append({'type': 'text', 'text': 'ANCHORS — rejected by the client\'s leadership (a floor to clear, never the bar): A then B.'})
    for i, path in enumerate(rejected):
        blocks.append(_block(resized_png(path, long_edge=ANCHOR_EDGE_PX)[0], cache=(i == len(rejected) - 1)))
    record = {'launched': [{'path': str(p), 'sha256': _sha(p)} for p in launched],
              'rejected': [{'path': str(p), 'sha256': _sha(p)} for p in rejected], 'edge_px': ANCHOR_EDGE_PX}
    return blocks, record


# --- the call -------------------------------------------------------------------------------------------------------

def _client():
    import anthropic
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=300)


def jury_model():
    return getattr(settings, 'JURY_MODEL', '') or settings.CLAUDE_MODEL_HEAVY


def _system(rubric_version):
    """The rubric alone: identical for both jurors, for calibration and for the gate, so one cache entry serves all."""
    return [{'type': 'text', 'text': RUBRICS[rubric_version], 'cache_control': {'type': 'ephemeral'}}]


def _role(juror, *, audience=False):
    """The juror's role, set after the anchors. ``audience``: J1's Day 9 role, which names the palette's audience
    (D-D9-7); Day 8's roles are unchanged."""
    if audience and juror != 'J1':
        raise ValueError('Only J1 answers for the audience (D-D9-7).')
    if juror == 'J1':
        return {'type': 'text', 'text': 'YOUR ROLE. ' + (ROLE_J1_D9 if audience else ROLE_J1)}
    return {'type': 'text', 'text': 'YOUR ROLE. ' + ROLE_J2}


LID_WHAT = 'flat print artwork of the closed lid of an eyeshadow palette, 190 × 120 mm, front-on, edge to edge'


#: the finish proof's label (D-D9-6), set right before it: what it is, how it was made and how to read it
PROOF_LABEL = ('FINISH PROOF of the same lid: not the print artwork and not a mockup. Its planned finishes '
               'are rendered as materials from the finish plates (foil as polished metal with a fine foil grain under one '
               'fixed softbox, emboss and deboss as relief, metallic ink as a soft sheen, on the board\'s own texture), '
               'front-on, with no perspective. It shows how the finishes will read; judge the design, never the rendering:')
PROOF_SHELF_LABEL = 'The flat print artwork (not the finish proof) at 330 px wide (shelf view):'


def _pair_rubric_and_proof(rubric_version, proof):
    """A finish proof goes only with a Day 9 rubric and a Day 9 rubric only with a proof: v2p tells the jury that a proof
    comes with each candidate (D-D9-6). Refused before any payment."""
    if rubric_version in DAY9_RUBRICS and proof is None:
        raise ValueError(f'Rubric {rubric_version} tells the jury a finish proof comes with each candidate: give the '
                         'build\'s finish proof (D-D9-6), or ask under v2.')
    if proof is not None and rubric_version not in DAY9_RUBRICS:
        raise ValueError(f'A finish proof is judged only under a rubric that says how to read it '
                         f'({", ".join(DAY9_RUBRICS)}), not {rubric_version}.')


def _proof_sha256(proof, candidate):
    """The finish proof's sha256 after its checks: a PNG (its image block declares image/png, and a picture that fits is
    sent as it is) and never the flat build itself. Refused before any payment."""
    from PIL import Image
    with Image.open(proof) as im:
        kind = im.format
    if kind != 'PNG':
        raise ValueError(f'The finish proof must be a PNG (its image block declares image/png): {proof} is {kind}.')
    sha = _sha(proof)
    if sha == _sha(candidate):
        raise ValueError('The finish proof is the flat build itself: give the proof rendered from the finish plates (D-D9-6).')
    return sha


def _candidate_blocks(candidate, *, what, facts, spec, engine_issues, direction_idea, proof=None):
    """The candidate as the juror sees it, and what was sent. Without a proof: the flat build at full size, then shrunk
    to the shelf view (Day 8's blocks, unchanged). With a finish proof (Day 9, v2p): the flat build at full size, its
    finish proof at full size under its label, then the FLAT build's shelf view, in the same call."""
    full, full_size = critic_image_bytes(candidate)
    shelf, shelf_size = resized_png(candidate, width=SHELF_WIDTH_PX)
    text = [f'CANDIDATE — {what}. First at full size, then shrunk to 330 px wide (about one arc-minute a pixel at 2 m '
            'for a 190 mm face — the shelf view).',
            'THE PRODUCT (facts, not design):\n' + facts.strip()]
    if spec:
        text.append('THE DIRECTION\'S SPEC (the designer\'s own statement; compare your reading of the idea with its idea line):\n' + spec.strip())
    if direction_idea:
        text.append('THE DIRECTION\'S IDEA LINE: ' + direction_idea.strip())
    if engine_issues:
        text.append('MEASURED CHECKS THE ENGINE COULD NOT MEET (issues, in plain words; weigh them):\n' + '\n'.join('- ' + x for x in engine_issues))
    text.append(ANSWER_WORDS)
    sent = {'candidate_sha256': _sha(candidate), 'full_px': full_size, 'shelf_px': shelf_size}
    if proof is None:
        shown = [{'type': 'text', 'text': '\n\n'.join(text[:1])}, _block(full),
                 {'type': 'text', 'text': 'The same lid at 330 px wide (shelf view):'}, _block(shelf)]
    else:
        proof_data, proof_size = critic_image_bytes(proof)
        shown = [{'type': 'text', 'text': f'CANDIDATE — {what}. First the flat print artwork at full size, then its finish '
                                          'proof at full size, then the flat print artwork shrunk to 330 px wide (about one '
                                          'arc-minute a pixel at 2 m for a 190 mm face — the shelf view).'},
                 _block(full), {'type': 'text', 'text': PROOF_LABEL}, _block(proof_data),
                 {'type': 'text', 'text': PROOF_SHELF_LABEL}, _block(shelf)]
        sent.update(proof_sha256=_sha(proof), proof_px=proof_size)
    return shown + [{'type': 'text', 'text': '\n\n'.join(text[1:])}], sent


def ask(juror, candidate, *, anchors, facts, what=LID_WHAT, spec='', engine_issues=(), direction_idea='', operation, destination,
        rubric_version='v1', effort='high', reservation_prefix=None, reservation_cap=None, model=None, proof=None, client=None):
    """One juror, one call, one immutable record. Returns the record (its ``payload`` feeds ``combine``).

    Day 9, under rubric v2p only (v1 and v2 send exactly what Day 8 sent): ``proof`` is the build's finish proof
    (D-D9-6), shown at full size after the flat build and before the flat build's shelf view, in the same call; the
    record keeps its sha256 (``sent['proof_sha256']``) and its path (``proof``). J1 also answers for the palette's
    audience (D-D9-7): the audience in its role, ``would_buy_partly_for_the_lid``, ``would_photograph_it`` and
    ``desirability_why`` in its schema. A proof outside v2p, or v2p without one, is refused before any payment; so is a
    record already at ``destination`` that was not asked about this proof (never read back as its verdict).
    ``client``: the provider client whose ``messages.create`` makes the one paid call (a fake in tests); the Anthropic
    client when None."""
    destination = Path(destination)
    _pair_rubric_and_proof(rubric_version, proof)
    proof_sha256 = None if proof is None else _proof_sha256(proof, candidate)
    if destination.exists():                      # written once, never overwritten: asking again reads it back
        record = json.loads(destination.read_text())
        if proof_sha256 is not None and (record.get('sent') or {}).get('proof_sha256') != proof_sha256:
            raise ValueError(f'The record at {destination} was not asked about this finish proof: judge it in a new folder.')
        return record
    destination.parent.mkdir(parents=True, exist_ok=True)
    blocks, anchor_record = anchors
    content, sent = _candidate_blocks(candidate, what=what, facts=facts, spec=spec, engine_issues=list(engine_issues), direction_idea=direction_idea,
                                      proof=proof)
    desirability = juror == 'J1' and rubric_version in DAY9_RUBRICS
    if desirability:
        content = content + [{'type': 'text', 'text': DESIRABILITY_WORDS}]
    model = model or jury_model()
    kwargs = dict(model=model, max_tokens=MAX_OUTPUT_TOKENS, output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': verdict_schema(juror, desirability=desirability)}},
                  system=_system(rubric_version), messages=[{'role': 'user', 'content': blocks + [_role(juror, audience=desirability)] + content}])
    create = _client().messages.create if client is None else client.messages.create
    response = paid_operation(create, provider='anthropic', operation=operation,
                              reservation_prefix=reservation_prefix, reservation_cap=reservation_cap, **kwargs)
    text = ''.join(b.text for b in response.content if getattr(b, 'type', '') == 'text')
    payload, parse_error = None, ''
    if response.stop_reason == 'end_turn':
        try:
            payload = _normalise(json.loads(text))
        except ValueError as exc:
            parse_error = str(exc)[:200]
    usage = response.model_dump(mode='json').get('usage') or {}
    record = {'schema_version': SCHEMA, 'juror': juror, 'rubric_version': rubric_version, 'model': model, 'effort': effort,
              'candidate': str(candidate), 'what': what, 'sent': sent, 'anchors': anchor_record, 'operation': operation,
              'stop_reason': response.stop_reason, 'parse_error': parse_error, 'payload': payload,
              'usage': usage, 'cost_usd': cost_usd(model, usage),
              'reservation_id': getattr(response, '_rescue_reservation_id', None),
              'response_artifact': getattr(response, '_rescue_response_artifact', None), 'weights_changed': False}
    if proof is not None:                         # Day 9: the proof this juror saw (its sha256 is in ``sent``)
        record['proof'] = str(proof)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


def _number(value):
    """An int or a float, never a bool or None: a token count or a cost that can be summed."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cost_usd(model, usage):
    """USD at the ledger's tariff: cache writes at 1.25× input, cache reads at the published read price where known.
    None when the usage lacks either token count."""
    from apps.pipeline.services.cost_ledger import claude_cost_usd
    # The gate review of Day 8 (cost_usd|or_default): both token counts are required (the SDK types them int) and are
    # read directly, as the ledger's ``settle`` reads them; a usage without either is an unknown cost, None, never
    # priced as zero tokens (an understated cost). Only the two cache counters keep `or 0`: Optional in the SDK, null
    # there is a call with no cache read or write.
    if not usage or not all(_number(usage.get(k)) for k in ('input_tokens', 'output_tokens')):
        return None
    inputs = usage['input_tokens'] + 1.25 * (usage.get('cache_creation_input_tokens') or 0)
    reads = usage.get('cache_read_input_tokens') or 0
    base = float(claude_cost_usd(model, inputs, usage['output_tokens']))
    in_price = settings.CLAUDE_PRICES.get(model, settings.CLAUDE_PRICE_DEFAULT)[0]
    read_price = in_price * cache_read_multiplier(model)
    return round(base + reads / 1000.0 * read_price, 6)


def cache_read_multiplier(model):
    from apps.pipeline.services.spend_reservation import cache_read_multiplier as ledger_multiplier
    return ledger_multiplier(model)


def _total_cost(costs):
    """The calls' costs summed, or None when any one is unknown: an unknown cost is never counted as $0 (the gate
    review of Day 8: ``judge`` and ``calibration_summary`` summed ``cost or 0``)."""
    costs = list(costs)
    return round(sum(costs), 6) if all(_number(c) for c in costs) else None


# --- computed rules -------------------------------------------------------------------------------------------------

def _clearly_beats_both_rejected(payload):
    pair = payload.get('pairwise') or {}
    return pair.get('rejected_a') == 'clearly_better' and pair.get('rejected_b') == 'clearly_better'


def _desirability_issues(payload):
    """J1's "no" to either desirability question (D-D9-7) as a top issue carrying J1's why; an answer that is not False
    (absent in every Day 8 record) adds none."""
    why = payload.get('desirability_why')
    because = f' — {why.strip()}' if isinstance(why, str) and why.strip() else ''
    return [{'observation': f'J1: {words}{because}', 'location': 'the whole lid', 'repair': repair}
            for key, words, repair in DESIRABILITY_ISSUES if payload.get(key) is False]


def combine(j1, j2):
    """The stricter score per dimension, hard failures the union, then the computed caps. Raw scores stay on the record."""
    p1, p2 = (j1 or {}).get('payload'), (j2 or {}).get('payload')
    if not isinstance(p1, dict) or not isinstance(p2, dict):
        return {'raw': {'J1': p1, 'J2': p2}, 'capped': None, 'caps_applied': [],
                'verdict': pending('A juror did not return a complete review — review pending.')}
    dims, raw = {}, {'J1': {}, 'J2': {}}
    for name in DIMENSIONS:
        rows = [(p1.get('dimensions') or {}).get(name), (p2.get('dimensions') or {}).get(name)]
        if any(not isinstance(r, dict) or not isinstance(r.get('score'), (int, float)) for r in rows):
            return {'raw': {'J1': p1, 'J2': p2}, 'capped': None, 'caps_applied': [],
                    'verdict': pending(f'The jury did not review {name} — review pending.')}
        raw['J1'][name], raw['J2'][name] = float(rows[0]['score']), float(rows[1]['score'])
        stricter = min(rows, key=lambda r: r['score'])
        dims[name] = dict(stricter)
    hard = list(dict.fromkeys([*(p1.get('hard_failures') or []), *(p2.get('hard_failures') or [])]))
    for p, who in ((p1, 'J1'), (p2, 'J2')):
        if (p.get('banned_motif_seen') or '').strip():
            hard.append(f'{who}: banned motif — {p["banned_motif_seen"].strip()}')
        if (p.get('near_copy_of') or '').strip():
            hard.append(f'{who}: near-copy of {p["near_copy_of"].strip()}')
    caps = []
    if not (_clearly_beats_both_rejected(p1) and _clearly_beats_both_rejected(p2)):
        caps.append('does not clearly beat both rejected anchors: beauty and distinctiveness capped at 6')
    if p1.get('looks_easy_to_make') is True:
        caps.append('J1 says it looks easy to make: beauty and distinctiveness capped at 6 (D-D8-3)')
    for name in ('beauty', 'distinctiveness'):
        if caps and dims[name]['score'] > 6:
            dims[name] = dict(dims[name], score=6.0, repair=(dims[name].get('repair') or '') or 'Raise the craft until it clearly beats the rejected anchors.')
    if p1.get('carries_collection') is False:
        caps.append('J1 says the language would not carry a lipstick, a lip balm and a display header: distinctiveness −1 (D-D8-13)')
        dims['distinctiveness'] = dict(dims['distinctiveness'], score=max(1.0, dims['distinctiveness']['score'] - 1),
                                       repair=(dims['distinctiveness'].get('repair') or '') or 'Make the device carry the collection.')
    for name in DIMENSIONS:
        if dims[name]['score'] < PASS_SCORE and not (dims[name].get('repair') or '').strip():
            dims[name]['repair'] = 'See the juror\'s top issues.'
    # D-D9-7: J1's "no" to either desirability question is a top issue, set first so the cut to ten never drops it, and
    # never a cap; a payload without the answers (every Day 8 record) adds none
    issues = _desirability_issues(p1) + [i for p in (p1, p2) for i in (p.get('top_issues') or []) if isinstance(i, dict)]
    for p, who in ((p1, 'J1'), (p2, 'J2')):
        if p.get('idea_matches_direction') is False:
            issues.append({'observation': f'{who} reads the idea as: {p.get("idea_read", "")}', 'location': 'the whole lid',
                           'repair': 'Make the lid say the direction\'s idea or change the idea line.'})
    payload = {'dimensions': dims, 'hard_failures': hard, 'observations': ' / '.join(x for x in (p1.get('observations'), p2.get('observations')) if x)}
    capped = {k: v['score'] for k, v in dims.items()}
    verdict = evaluate(payload)
    verdict['issues'] = verdict['issues'] + [f"{i['observation']} ({i['location']}). {i['repair']}" for i in issues]
    raw_mean = {who: round(sum(raw[who].values()) / len(DIMENSIONS), 2) for who in raw}
    return {'raw': {'J1': p1, 'J2': p2, 'scores': raw, 'means': raw_mean,
                    'stricter_mean': round(sum(min(raw['J1'][n], raw['J2'][n]) for n in DIMENSIONS) / len(DIMENSIONS), 2)},
            'capped': capped, 'caps_applied': caps, 'top_issues': issues[:10], 'verdict': verdict}


def raw_passes(scores):
    """Whether a set of raw stricter scores would pass the owner's thresholds with no caps and no hard failures."""
    mean = sum(scores.values()) / len(DIMENSIONS)
    return mean >= PASS_SCORE and all(scores[k] >= 7 for k in CRITICAL)


def judge(candidate, *, anchors, facts, what=LID_WHAT, spec='', engine_issues=(), direction_idea='', operation_prefix, destination_dir,
          rubric_version='v1', times=1, effort='high', reservation_prefix=None, reservation_cap=None, proof=None, client=None):
    """Both jurors on one candidate (``times`` × each; the median of the raw scores stands when times > 1). ``proof``:
    the build's finish proof (rubric v2p, D-D9-6): both jurors see it, and the verdict keeps its path and sha256.
    ``client``: as in ``ask``."""
    destination_dir = Path(destination_dir); destination_dir.mkdir(parents=True, exist_ok=True)
    records = {'J1': [], 'J2': []}
    for n in range(times):
        for juror in ('J1', 'J2'):
            suffix = f'-{n + 1}' if times > 1 else ''
            records[juror].append(ask(juror, candidate, anchors=anchors, facts=facts, what=what, spec=spec, engine_issues=engine_issues,
                                      direction_idea=direction_idea, operation=f'{operation_prefix}/{juror}{suffix}',
                                      destination=destination_dir / f'{juror}{suffix}.json', rubric_version=rubric_version,
                                      effort=effort, reservation_prefix=reservation_prefix, reservation_cap=reservation_cap,
                                      proof=proof, client=client))
    chosen = {juror: _median_record(records[juror]) for juror in records}
    combined = combine(chosen['J1'], chosen['J2'])
    # the gate review of Day 8 (judge|or_default): one call of unknown cost makes the verdict's cost None, never $0
    combined.update({'schema_version': SCHEMA, 'candidate': str(candidate), 'candidate_sha256': _sha(candidate),
                     'times': times, 'rubric_version': rubric_version, 'model': chosen['J1'].get('model'),
                     'cost_usd': _total_cost(r.get('cost_usd') for rs in records.values() for r in rs),
                     'records': {j: [str(destination_dir / (f'{j}-{i + 1}' if times > 1 else j)) + '.json' for i in range(len(rs))] for j, rs in records.items()}})
    if proof is not None:                         # Day 9: the proof both jurors saw; a Day 8 verdict carries no such keys
        combined.update(proof=str(proof), proof_sha256=_sha(proof))
    (destination_dir / 'verdict.json').write_text(json.dumps(combined, ensure_ascii=False, indent=2) + '\n')
    return combined


def _median_record(records):
    """When a juror scored more than once, the record whose raw mean is the median (an actual record, never a blend)."""
    complete = [r for r in records if isinstance(r.get('payload'), dict) and isinstance(r['payload'].get('dimensions'), dict)]
    if not complete:
        return records[-1]
    if len(complete) == 1:
        return complete[0]
    means = []
    for r in complete:
        scores = [float((r['payload']['dimensions'].get(n) or {}).get('score') or 0) for n in DIMENSIONS]
        means.append(sum(scores) / len(DIMENSIONS))
    target = statistics.median(means)
    return min(complete, key=lambda r: abs(sum(float((r['payload']['dimensions'].get(n) or {}).get('score') or 0) for n in DIMENSIONS) / len(DIMENSIONS) - target))


# --- the sketch ranking and the idea check (J1 only) ---------------------------------------------------------------

RANK_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'properties': {'ranking': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                                                     'properties': {'sketch': {'type': 'integer'}, 'rank': {'type': 'integer'},
                                                                                    'score': {'type': 'number'}, 'why': {'type': 'string'},
                                                                                    'banned_motif_seen': {'type': 'string'},
                                                                                    'copy_present': {'type': 'boolean'},
                                                                                    'ai_artefacts': {'type': 'string'}},
                                                                     'required': ['sketch', 'rank', 'score', 'why', 'banned_motif_seen', 'copy_present', 'ai_artefacts']}},
                              'best_two': {'type': 'array', 'items': {'type': 'integer'}},
                              'note': {'type': 'string'}},
               'required': ['ranking', 'best_two', 'note']}


def rank_sketches(sketches, *, anchors, facts, spec, direction_idea, operation, destination, rubric_version='v1', effort='medium',
                  reservation_prefix=None, reservation_cap=None, model=None, checks=None):
    """J1 ranks a direction's sketches side by side with the fixed anchors; the best two go on (Stage 1). ``checks``:
    one line per sketch of what the code measured on it (the copy OCR found), set under its picture."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Jury observations are immutable per attempt: %s' % destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blocks, anchor_record = anchors
    content = [{'type': 'text', 'text': 'SKETCHES. Six ideas for the same direction, flat lid artwork, numbered 1–6 in order. '
                                        'They are IDEAS from an image model, never the printed design: judge the idea, the layout '
                                        'and the artwork\'s craft; the words will be reset by the engine, so judge copy only as '
                                        'present or not and the Arabic only for its size and placement.'}]
    for i, path in enumerate(sketches, 1):
        content += [{'type': 'text', 'text': f'Sketch {i}:'}, _block(resized_png(path, long_edge=1024)[0])]
        if checks:
            content.append({'type': 'text', 'text': f'Measured by code on sketch {i}: {checks[i - 1]}'})
    content.append({'type': 'text', 'text': 'THE PRODUCT:\n' + facts.strip() + '\n\nTHE DIRECTION\'S SPEC:\n' + spec.strip()
                                              + '\n\nTHE IDEA LINE: ' + direction_idea.strip()
                                              + '\n\nRank all six (1 = best) on the scale, with a score each, one reason each, any banned '
                                                'motif seen, whether the copy is present, and any AI artefacts; name the best two.'})
    model = model or jury_model()
    response = paid_operation(_client().messages.create, provider='anthropic', operation=operation, reservation_prefix=reservation_prefix,
                              reservation_cap=reservation_cap, model=model, max_tokens=MAX_OUTPUT_TOKENS,
                              output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': RANK_SCHEMA}},
                              system=_system(rubric_version), messages=[{'role': 'user', 'content': blocks + [_role('J1')] + content}])
    text = ''.join(b.text for b in response.content if getattr(b, 'type', '') == 'text')
    payload = None
    if response.stop_reason == 'end_turn':
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
    if isinstance(payload, dict) and isinstance(payload.get('best_two'), list):
        payload['best_two'] = payload['best_two'][:2]
    usage = response.model_dump(mode='json').get('usage') or {}
    record = {'schema_version': SCHEMA, 'juror': 'J1', 'kind': 'sketch_ranking', 'model': model, 'rubric_version': rubric_version,
              'sketches': [{'path': str(p), 'sha256': _sha(p)} for p in sketches], 'checks': list(checks or []), 'anchors': anchor_record,
              'stop_reason': response.stop_reason, 'payload': payload, 'usage': usage, 'cost_usd': cost_usd(model, usage),
              'reservation_id': getattr(response, '_rescue_reservation_id', None)}
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


IDEA_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'properties': {'reaches_nine_if_executed_perfectly': {'type': 'boolean'}, 'ceiling': {'type': 'number'},
                              'why': {'type': 'string'}, 'what_would_lift_it': {'type': 'string'}},
               'required': ['reaches_nine_if_executed_perfectly', 'ceiling', 'why', 'what_would_lift_it']}


def idea_check(spec_text, *, anchors, facts, operation, destination, rubric_version='v1', effort='high', model=None,
               reservation_prefix=None, reservation_cap=None):
    """J1 reads a direction's spec beside the anchors, no candidate yet: executed perfectly, would it reach 9?"""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Jury observations are immutable per attempt: %s' % destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blocks, anchor_record = anchors
    content = [{'type': 'text', 'text': 'IDEA CHECK. There is no candidate yet. Read this direction\'s spec beside the launched anchors. '
                                        'Executed perfectly by a senior designer, would the lid reach 9 on the scale? Give the ceiling you '
                                        'see, why, and the one change that would lift it.\n\nTHE PRODUCT:\n' + facts.strip()
                                        + '\n\nTHE SPEC:\n' + spec_text.strip()}]
    model = model or jury_model()
    response = paid_operation(_client().messages.create, provider='anthropic', operation=operation, reservation_prefix=reservation_prefix,
                              reservation_cap=reservation_cap, model=model, max_tokens=MAX_OUTPUT_TOKENS,
                              output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': IDEA_SCHEMA}},
                              system=_system(rubric_version), messages=[{'role': 'user', 'content': blocks + [_role('J1')] + content}])
    text = ''.join(b.text for b in response.content if getattr(b, 'type', '') == 'text')
    payload = None
    if response.stop_reason == 'end_turn':
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
    usage = response.model_dump(mode='json').get('usage') or {}
    record = {'schema_version': SCHEMA, 'juror': 'J1', 'kind': 'idea_check', 'model': model, 'rubric_version': rubric_version,
              'anchors': anchor_record, 'stop_reason': response.stop_reason, 'payload': payload, 'usage': usage,
              'cost_usd': cost_usd(model, usage), 'reservation_id': getattr(response, '_rescue_reservation_id', None)}
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


# --- Day 9: the sketch ranking v2 and the idea check v2 (J1 only; Day 8's ``rank_sketches`` and ``idea_check`` above are
# kept as they were) ---------------------------------------------------------------------------------------------------

SKETCH_EDGE_PX = 1024                 # the long edge a sketch is shown at (Day 8's ranking used the same)
#: Day 8's rankings wrote 1,310 to 2,283 output tokens of 4,000 with one reason a sketch; v2 asks three more answers a
#: sketch (each word-limited), and an answer cut at the ceiling is paid for and unread (its payload None)
RANK_V2_MAX_OUTPUT_TOKENS = 6000
#: what the build must make with the engine rather than keep from a sketch's picture (D-D9-4)
MUST_REBUILD = ('lettering', 'logo', 'foil_or_metallic', 'geometric_structure', 'painted_relief')
#: D-D9-2 and D-D9-4 in one paragraph: how a Day 9 sketch or spec becomes a build
BUILD_RULES = ('In the build the image model is the illustrator and our engine the typesetter, the engraver and the '
               'foil-maker: the picture stays a raster, and the lettering, the logo, every gold or metallic element (foil '
               'or metallic ink), anything countable or geometric (cells, frames, borders, rules, guilloché, girih) and '
               'all relief (emboss and deboss plates) are made by the engine, never kept from the picture.')
RANKS_LOWER = 'A sketch whose richness lives in model-drawn lettering, painted gold or fake engraving ranks lower.'
IDEA_V2_WORDS = ('IDEA CHECK (Day 9). There is no candidate yet. Read this idea\'s spec beside the launched anchors. '
                 + BUILD_RULES + ' Answer three questions. (1) Executed perfectly by a senior designer, would the lid '
                 'reach 9 on the scale? Give the ceiling you see. (2) Would she, the audience named in your role, buy the '
                 'palette partly for its lid? (3) Could another brand own this idea: would a shopper credit it to another '
                 'house as readily as to this one? True means it is NOT ownable. Then why (at most 150 words) and the one '
                 'change that would lift it (at most 40 words).')

#: one item shape for every sketch, flat fields only (no nested object: the compiled grammar stays small): Day 8's seven
#: fields first, then desirability (D-D9-7) and buildability (D-D9-4)
_RANK_V2_ROW = {'sketch': {'type': 'integer'}, 'rank': {'type': 'integer'}, 'score': {'type': 'number'},
                'why': {'type': 'string'}, 'banned_motif_seen': {'type': 'string'}, 'copy_present': {'type': 'boolean'},
                'ai_artefacts': {'type': 'string'}, **DESIRABILITY_FIELDS,
                'must_rebuild': {'type': 'array', 'items': {'type': 'string', 'enum': list(MUST_REBUILD)}},
                'richness_survives_rebuild': {'type': 'boolean'}, 'buildability_why': {'type': 'string'}}
RANK_SCHEMA_V2 = {'type': 'object', 'additionalProperties': False,
                  'properties': {'ranking': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                                                        'properties': _RANK_V2_ROW,
                                                                        'required': list(_RANK_V2_ROW)}},
                                 'best_two': {'type': 'array', 'items': {'type': 'integer'}},
                                 'note': {'type': 'string'}},
                  'required': ['ranking', 'best_two', 'note']}

_IDEA_V2 = {'reaches_nine_if_executed_perfectly': {'type': 'boolean'}, 'ceiling': {'type': 'number'},
            'would_buy_partly_for_the_lid': {'type': 'boolean'}, 'another_brand_could_own_it': {'type': 'boolean'},
            'why': {'type': 'string'}, 'what_would_lift_it': {'type': 'string'}}
IDEA_SCHEMA_V2 = {'type': 'object', 'additionalProperties': False, 'properties': _IDEA_V2, 'required': list(_IDEA_V2)}


def _attribute(obj, name):
    """``obj.name``, or None when the object has none (a response the spend reservation never marked)."""
    return getattr(obj, name) if hasattr(obj, name) else None


def _parsed(text):
    """The answer's JSON and '', or None and the parse error (its first 200 characters) when the text is not JSON."""
    try:
        return json.loads(text), ''
    except ValueError as exc:
        return None, str(exc)[:200]


def _new_record_path(destination):
    """The record's path, refused when a record is already there: a jury observation is written once per attempt."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Jury observations are immutable per attempt: %s' % destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _ask_j1(content, *, schema, max_tokens, anchors, operation, rubric_version, effort, model, reservation_prefix,
            reservation_cap, client):
    """One Day 9 J1 call (the sketch ranking v2, the idea check v2): the fixed anchors, J1's role with the audience
    (D-D9-7), the content and one strict schema, through the spend reservation. Returns the record's answer fields: the
    stop reason, the payload (None unless the turn ended and its text parsed), the parse error, the usage, its cost, the
    reservation and the response artifact (None when the reservation never marked the response)."""
    create = _client().messages.create if client is None else client.messages.create
    response = paid_operation(create, provider='anthropic', operation=operation, reservation_prefix=reservation_prefix,
                              reservation_cap=reservation_cap, model=model, max_tokens=max_tokens,
                              output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
                              system=_system(rubric_version),
                              messages=[{'role': 'user', 'content': anchors[0] + [_role('J1', audience=True)] + content}])
    text = ''.join(b.text for b in response.content if _attribute(b, 'type') == 'text')
    payload, parse_error = _parsed(text) if response.stop_reason == 'end_turn' else (None, '')
    usage = response.model_dump(mode='json').get('usage') or {}
    return {'stop_reason': response.stop_reason, 'parse_error': parse_error, 'payload': payload, 'usage': usage,
            'cost_usd': cost_usd(model, usage), 'reservation_id': _attribute(response, '_rescue_reservation_id'),
            'response_artifact': _attribute(response, '_rescue_response_artifact')}


def _rank_v2_words(count):
    """What J1 answers for each sketch, every free-text field word-limited (an answer cut at the ceiling is unread)."""
    return (f'Rank all {count} (1 = best) on the scale, with a score each. For each sketch: why it ranks there (at most '
            '40 words); any banned motif seen; whether the copy is present; any AI artefacts (at most 15 words). Its '
            'desirability, answering for her, the audience named in your role: would_buy_partly_for_the_lid (would she '
            'buy the palette partly for this lid), would_photograph_it (would she photograph it) and desirability_why (at '
            'most 15 words). Its buildability: must_rebuild (which of lettering, logo, foil or metallic, geometric '
            'structure and painted relief the engine must rebuild from this sketch), richness_survives_rebuild (whether '
            'its richness survives once they are rebuilt) and buildability_why (at most 15 words). Then name the best '
            'two; the note in at most 25 words.')


def _ranked_every_sketch_once(payload, count):
    """Whether J1's ranking names every sketch 1 to ``count`` exactly once; None when there is no ranking to read."""
    rows = payload.get('ranking') if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    numbers = [row.get('sketch') if isinstance(row, dict) else None for row in rows]
    return (all(isinstance(n, int) and not isinstance(n, bool) for n in numbers)
            and sorted(numbers) == list(range(1, count + 1)))


def rank_sketches_v2(sketches, *, anchors, facts, spec, direction_idea, operation, destination, checks=None,
                     rubric_version='v2', effort='medium', reservation_prefix=None, reservation_cap=None, model=None,
                     client=None):
    """Day 9's sketch ranking: J1 ranks a direction's sketches side by side with the fixed anchors, as Day 8's
    ``rank_sketches`` does, and answers two more things per sketch: desirability for the palette's audience
    (``would_buy_partly_for_the_lid``, ``would_photograph_it``, ``desirability_why``; D-D9-7) and buildability
    (``must_rebuild``, each from ``MUST_REBUILD``; ``richness_survives_rebuild``; ``buildability_why``; D-D9-4). A sketch
    whose richness lives in model-drawn lettering, painted gold or fake engraving ranks lower. ``checks``: one line per
    sketch of what the code measured on it, set under its picture. Returns the record (kind ``sketch_ranking_v2``): its
    ``payload`` is J1's answer (``best_two`` cut to two), ``ranked_every_sketch_once`` whether the ranking names each
    sketch exactly once. ``client``: as in ``ask``. Day 8's ``rank_sketches`` is kept as it was."""
    _pair_rubric_and_proof(rubric_version, None)
    count = len(sketches)
    if not count:
        raise ValueError('No sketches to rank.')
    if checks is not None and len(checks) != count:
        raise ValueError(f'One measured line per sketch: {len(checks)} lines for {count} sketches.')
    destination = _new_record_path(destination)
    content = [{'type': 'text', 'text': f'SKETCHES (Day 9). {count} ideas for the same direction, flat lid artwork, numbered '
                                        f'1–{count} in order. They are IDEAS from an image model, never the printed design: '
                                        'judge the idea, the layout and the artwork\'s craft; the words will be reset by the '
                                        'engine, so judge copy only as present or not and the Arabic only for its size and '
                                        'placement. ' + BUILD_RULES + ' ' + RANKS_LOWER}]
    for i, path in enumerate(sketches, 1):
        content += [{'type': 'text', 'text': f'Sketch {i}:'}, _block(resized_png(path, long_edge=SKETCH_EDGE_PX)[0])]
        if checks is not None:
            content.append({'type': 'text', 'text': f'Measured by code on sketch {i}: {checks[i - 1]}'})
    content.append({'type': 'text', 'text': 'THE PRODUCT:\n' + facts.strip() + '\n\nTHE DIRECTION\'S SPEC:\n' + spec.strip()
                                              + '\n\nTHE IDEA LINE: ' + direction_idea.strip() + '\n\n' + _rank_v2_words(count)})
    model = model or jury_model()
    answer = _ask_j1(content, schema=RANK_SCHEMA_V2, max_tokens=RANK_V2_MAX_OUTPUT_TOKENS, anchors=anchors,
                     operation=operation, rubric_version=rubric_version, effort=effort, model=model,
                     reservation_prefix=reservation_prefix, reservation_cap=reservation_cap, client=client)
    payload = answer['payload']
    if isinstance(payload, dict) and isinstance(payload.get('best_two'), list):
        payload['best_two'] = payload['best_two'][:2]
    record = {'schema_version': SCHEMA, 'juror': 'J1', 'kind': 'sketch_ranking_v2', 'model': model,
              'rubric_version': rubric_version, 'effort': effort, 'audience': AUDIENCE,
              'sketches': [{'path': str(p), 'sha256': _sha(p)} for p in sketches],
              'checks': [] if checks is None else list(checks), 'anchors': anchors[1], 'operation': operation,
              **answer, 'ranked_every_sketch_once': _ranked_every_sketch_once(payload, count)}
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


def idea_check_v2(spec_text, *, anchors, facts, operation, destination, rubric_version='v2', effort='high', model=None,
                  reservation_prefix=None, reservation_cap=None, client=None):
    """Day 9's idea check: J1 reads an idea's spec beside the anchors, no candidate yet, and answers three questions —
    executed perfectly, would it reach 9 (``reaches_nine_if_executed_perfectly``, with the ``ceiling`` it sees); would
    she, the palette's audience, buy it partly for the lid (``would_buy_partly_for_the_lid``); could another brand own
    it (``another_brand_could_own_it``: True is bad, the idea is not ownable) — with ``why`` and ``what_would_lift_it``.
    Returns the record (kind ``idea_check_v2``). ``client``: as in ``ask``. Day 8's ``idea_check`` is kept as it was."""
    _pair_rubric_and_proof(rubric_version, None)
    destination = _new_record_path(destination)
    content = [{'type': 'text', 'text': IDEA_V2_WORDS + '\n\nTHE PRODUCT:\n' + facts.strip() + '\n\nTHE SPEC:\n' + spec_text.strip()}]
    model = model or jury_model()
    answer = _ask_j1(content, schema=IDEA_SCHEMA_V2, max_tokens=MAX_OUTPUT_TOKENS, anchors=anchors, operation=operation,
                     rubric_version=rubric_version, effort=effort, model=model, reservation_prefix=reservation_prefix,
                     reservation_cap=reservation_cap, client=client)
    record = {'schema_version': SCHEMA, 'juror': 'J1', 'kind': 'idea_check_v2', 'model': model,
              'rubric_version': rubric_version, 'effort': effort, 'audience': AUDIENCE, 'anchors': anchors[1],
              'operation': operation, **answer}
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


# --- calibration (§3b): on RAW scores, before the caps -------------------------------------------------------------

def calibration_summary(results, *, repeat_label=None, order=('D1', 'D2', 'D3')) -> dict:
    """``results``: ``[{label, kind: negative|positive, verdict: judge()-record}]``. Reports raw (stricter juror, no caps,
    no hard failures) and capped side by side; every negative must fail on raw scores; at least 75 % of the positives
    must pass on raw scores; the spread and order of ``order``; the repeatability of ``repeat_label`` (its scored runs'
    raw stricter means; a run never scored is pending, named by its run)."""
    rows = []
    for r in results:
        v = r['verdict']
        raw = (v.get('raw') or {}).get('scores') or {}
        stricter = {n: min(raw['J1'][n], raw['J2'][n]) for n in DIMENSIONS} if raw.get('J1') and raw.get('J2') else None
        rows.append({'label': r['label'], 'kind': r['kind'], 'run': r.get('run', 1),
                     'raw_mean_J1': (v.get('raw') or {}).get('means', {}).get('J1'),
                     'raw_mean_J2': (v.get('raw') or {}).get('means', {}).get('J2'),
                     'raw_stricter_mean': (v.get('raw') or {}).get('stricter_mean'),
                     'raw_passes': raw_passes(stricter) if stricter else None,
                     'raw_criticals_min': min(stricter[k] for k in CRITICAL) if stricter else None,
                     'capped_mean': (v.get('verdict') or {}).get('score'),
                     'capped_passes': (v.get('verdict') or {}).get('passed'),
                     'caps_applied': v.get('caps_applied') or [],
                     'hard_failures': (v.get('verdict') or {}).get('hard_failures') or [],
                     'cost_usd': v.get('cost_usd')})
    first = [x for x in rows if x['run'] == 1]
    negatives = [x for x in first if x['kind'] == 'negative']
    positives = [x for x in first if x['kind'] == 'positive']
    neg_pass = [x['label'] for x in negatives if x['raw_passes']]
    pos_pass = [x['label'] for x in positives if x['raw_passes']]
    # the gate review of Day 8: an item whose review never came back (raw_passes None) is pending, named under its
    # kind, never counted as failing: all_fail_on_raw holds only when every negative was scored and failed, and the
    # positives' share, the 75 % check and calibrated_on_the_positive_side wait for every positive
    neg_pending = [x['label'] for x in negatives if x['raw_passes'] is None]
    pos_pending = [x['label'] for x in positives if x['raw_passes'] is None]
    pos_measured = bool(positives) and not pos_pending
    ordered = [next((x['raw_stricter_mean'] for x in first if x['label'] == lab), None) for lab in order]
    repeat = [x['raw_stricter_mean'] for x in rows if x['label'] == repeat_label and x['raw_stricter_mean'] is not None]
    movement = round(max(repeat) - min(repeat), 2) if len(repeat) >= 2 else None
    # Day 8 residual: a run of repeat_label whose review never came back was dropped unseen, and fewer than two scored
    # runs read as finalists_scored_three_times False ('stable, score finalists once') with nothing measured. The runs
    # never scored are named under pending, and the decision is None (unmeasured) until it is measured
    repeat_pending = [x['run'] for x in rows if x['label'] == repeat_label and x['raw_stricter_mean'] is None]
    if movement is None:                                # fewer than two scored runs: no movement measured
        three_times = None
    elif movement > 0.5:                                # more runs only widen the spread: True whatever is pending
        three_times = True
    else:                                               # 0.5 or less is False only when every run was scored
        three_times = None if repeat_pending else False
    return {
        'schema': 'critic_calibration/2', 'thresholds': {'mean': PASS_SCORE, 'criticals': 7, 'critical_dimensions': list(CRITICAL)},
        'rows': rows,
        'negatives': {'count': len(negatives), 'raw_passes': neg_pass, 'pending': neg_pending,
                      'all_fail_on_raw': not neg_pass and not neg_pending and bool(negatives)},
        'positives': {'count': len(positives), 'raw_passes': pos_pass, 'pending': pos_pending,
                      'share_passing': round(len(pos_pass) / len(positives), 2) if pos_measured else None,
                      'meets_75_percent': (len(pos_pass) / len(positives) >= 0.75) if pos_measured else None,
                      'calibrated_on_the_positive_side': pos_measured},
        'order': {'labels': list(order), 'raw_stricter_means': ordered,
                  'spread': round(max(o for o in ordered if o is not None) - min(o for o in ordered if o is not None), 2)
                  if all(o is not None for o in ordered) else None,
                  'owner_order_held': all(o is not None for o in ordered) and all(ordered[i] > ordered[i + 1] for i in range(len(ordered) - 1))},
        'repeatability': {'label': repeat_label, 'raw_stricter_means': repeat, 'pending': repeat_pending, 'movement': movement,
                          'finalists_scored_three_times': three_times},
        'cost_usd': _total_cost(x['cost_usd'] for x in rows),      # the gate review of Day 8: an unknown cost is never $0
    }
