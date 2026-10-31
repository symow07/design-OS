"""Worker-only design operations for a product round.

No provider is called on import. Context owns payment, durable responses, the
single truncation retry and advisory reading re-ask. Operations resume pinned calls.
"""
from itertools import combinations
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw

from . import round_calls as image_guard, rank_round, round_sheet
from .round_balm_calls import sha
from .round_flow import write_json as write
from .round_balm_sheet import protected_edit
from .whole_object_check import COPY_KEYS, STATES, has_words
from .round_product import typed_content, printed_copy, content_fields

QUESTION = (rank_round.QUESTION.rstrip('?') +
            '; and does the idea come from the product, or could it sit on any box?')
FAMILIES = dict(zip('ABCD', ('action', 'overlooked', 'craft', 'free')))
COPY_START = '<COPY_PRINT_VERBATIM>'
COPY_END = '</COPY_PRINT_VERBATIM>'
BODY_IDS = ('body_front', 'body_back', 'body_left', 'body_right')


def read(path):
    return json.loads(Path(path).read_text())


@contextmanager
def _validation(ctx, destination):
    """Only provider-schema failures invalidate a settled reply for app retry."""
    try:
        yield
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        ctx.reject_result(destination, str(exc))
        raise


def _seed_rows(payload, brief):
    rows = payload.get('seeds')
    expected = {f'{f}{n}' for f in FAMILIES for n in range(1, 6)}
    if not isinstance(rows, list) or len(rows) != 20 or {r.get('id') for r in rows} != expected:
        raise ValueError('Seeds must be exactly the twenty named IDs')
    for row in rows:
        if row.get('family') != FAMILIES[row['id'][0]] or not has_words(row.get('seed')) or not 1 <= len(row['seed'].split()) <= 15:
            raise ValueError('Invalid seed family or word count: '+row['id'])
        if not has_words(row.get('link')) or not row['link'].lower().startswith('because ') or not 1 <= len(row['link'].split()) <= 8:
            raise ValueError('Every seed needs its product-truth link of at most eight words')
        if image_guard.competitor_in(row['seed']+' '+row['link']):
            raise ValueError('Competitor reference in seed')
        zones = row.setdefault('opaque_zones', [])
        clear = {p['id'] for p in brief['panels'] if p.get('surface') == 'clear_acrylic'}
        if not isinstance(zones, list) or any(not isinstance(z, dict) or set(z) != {'panel', 'zone', 'reason'} or
                z['panel'] not in clear or not has_words(z['zone']) or not has_words(z['reason']) or
                len(z['reason'].split()) > 12 for z in zones):
            raise ValueError('Opaque material exceptions need a clear panel, localized zone and short reason')
    return rows


def _candidate_dir(ctx, key):
    parts = key.split('/')
    if len(parts) == 1 and key in {f'{f}{n}' for f in FAMILIES for n in range(1, 6)}:
        return ctx.root/'sketches'/key
    if len(parts) == 2 and parts[0] in {f'{f}{n}' for f in FAMILIES for n in range(1, 6)} and parts[1] in ('A', 'B'):
        return ctx.root/'developments'/parts[0]/parts[1]
    raise ValueError('Unknown candidate ID')


def seeds(ctx):
    brief = ctx.brief
    prompt = '''Return JSON only: {"seeds":[{"id":"A1","family":"action","seed":"...","link":"because a ...","opaque_zones":[]}]}.
Exactly twenty seeds: A1–A5 action, B1–B5 overlooked, C1–C5 craft, D1–D5 free.
Each seed is at most 15 whitespace-delimited words: a mood, one constraint, where
invention may live. No written-out idea, layout, hex, font, copy list or collection
name. Across twenty never repeat a mood or material. Pictures discover the idea.
Every seed MUST begin from this product's truth. Give its separate link in at most
EIGHT whitespace-delimited words, beginning "because a [product] ...". Link its
ritual, material, colour, applicator or moment of use to the seed. A seed without a
link will not be sketched. The link is an idea, never a banned literal motif.
Families: action = opening/using/closing; overlooked = an overlooked panel leads;
craft = one named medium governs every panel; free = what a stranger repeats.
No competitor, earlier design, reference picture, inherited style or rescue name.
Opaque zones default to NONE on clear material. If the idea requires a deliberate
opaque zone, declare the material exception separately in opaque_zones as
{"panel":"panel ID","zone":"short localized area","reason":"at most 12 words"}.
This is material-exception metadata, not a written-out design. No opaque wrap.
PRODUCT TRUTH: ''' + json.dumps({k: brief.get(k) for k in ('name', 'material', 'dimensions_mm', 'truths', 'audience', 'bar', 'banned')}, ensure_ascii=False)
    prompt += '\nCLEAR PANELS: '+', '.join(p['id'] for p in brief['panels'] if p.get('surface') == 'clear_acrylic')
    rec = ctx.text_call('seeds', prompt, ctx.root/'seeds-call.json', max_tokens=16384, ceiling=.80)
    with _validation(ctx, ctx.root/'seeds-call.json'):
        rows = _seed_rows(rec['payload'], brief)
    result = {'schema': 'round_seeds/1', 'seeds': rows, 'source': 'seeds-call.json'}
    write(ctx.root/'seeds.json', result)
    write(ctx.root/'critic-calibration.json', {'schema': 'round_critic_calibration/1', 'rule': QUESTION,
          'marks': [], 'picks': [], 'departures': [], 'format': 'Ordinal judgments; no inherited scores, caps or anchors.'})
    return result


def _copy_block(brief):
    return '\n'.join(path + ': ' + json.dumps(value, ensure_ascii=False)
                     for path, value in printed_copy(brief).items())


def _instruction_text(value):
    # Only the COPY block uses quotation marks to specify literal lettering.
    return str(value).translate(str.maketrans('', '', "\"'“”‘’„«»"))


def _seal_image_prompt(brief, words):
    """The shared image boundary also handles quoted owner/fork guidance."""
    if words.count(COPY_START) != 1 or words.count(COPY_END) != 1:
        raise ValueError('A typed image prompt needs exactly one literal COPY block')
    before, rest = words.split(COPY_START)
    quoted, after = rest.split(COPY_END)
    if quoted.strip() != _copy_block(brief):
        raise ValueError('Image lettering differs from the explicitly typed COPY fields')
    return _instruction_text(before) + COPY_START + '\n' + _copy_block(brief) + '\n' + COPY_END + _instruction_text(after)


def _typed_image_words(ctx, seed, opaque_zones):
    brief = ctx.brief
    panels = read(ctx.root/'sheet.json')['panels']
    shade = brief['shades'][0]['hex']
    lines = [
        'INSTRUCTION — everything outside COPY_PRINT_VERBATIM guides the design and must never be printed.',
        'Only COPY values are quoted lettering. Do not print field names, seed text, readings, directions or labels.',
        'Edit only unprotected engine windows at their exact common scale. One complete ' + brief['name'] + '.',
        'Flat printed artwork on the physical material: no scene, mockup, shadow, invented view or geometry.',
        'Use only the approved BBROSE logo image for the house mark. Arabic equal or leading.',
        'Material: ' + brief['material'], 'Audience: ' + brief['audience'], 'Creative direction: ' + brief['bar'],
        'The liquid must stay visible through the print; print is flat zones on clear.',
        'The liquid colour ' + shade + ' is behind the clear acrylic, not a pink painted background or opaque wrap.',
        'Keep walls, highlights and gold caps protected. Caps remain gold; never paint them.',
        'Preserved borders, highlights and thin liquid-edge reveals alone do not satisfy the clear-area requirement.',
        'Relate the four faces through one idea, with four different printed compositions, not the same stripe/logo on every side.',
        'Shade names in COPY are literal. The first shade is shown; its hex controls the liquid, not a flood of ink.',
    ]
    if seed:
        lines += ['Seed guidance, never lettering: ' + seed['seed'],
                  'Product-truth guidance, never lettering: ' + seed['link']]
    fields = content_fields(brief)
    for path, role in brief['content_roles'].items():
        if path.startswith('copy.') and role == 'INSTRUCTION' and fields[path]:
            lines.append(path + ' — INSTRUCTION, never print these words: ' + fields[path])
    face_roles = {
        'body_front': ('Print a focal seed-derived flat mark or line with the selected brand/product COPY in localized zones.',
                       'Leave a broad connected clear area around and between those printed zones.'),
        'body_back': ('Print a secondary composition and selected net/product COPY in separate small zones; do not repeat the front layout.',
                      'Leave the main interior clear between the secondary marks and words.'),
        'body_left': ('Print a sparse counterpoint of interrupted lines or small flat zones; avoid a repeated front logo/copy band.',
                      'Leave most of the interior unprinted, including the gaps between the sparse marks.'),
        'body_right': ('Print a different resolving line or separated flat accent with its own arrangement; do not duplicate the left, back or front.',
                       'Leave broad clear negative space on both sides of the accent and through its gaps.'),
    }
    for key, panel in panels.items():
        lines.append('Panel ' + key + ': mm=' + str(panel['mm']) + '; pixel box=' + str(panel['box_px']) + '.')
        if panel.get('decoration'):
            lines.append(key + ' decoration guidance: ' + panel['decoration'])
        if panel.get('reserved_reason'):
            lines.append(key + ' protected material: ' + panel['reserved_reason'])
        if panel.get('surface') == 'clear_acrylic':
            if key in face_roles:
                printing, clear = face_roles[key]
            else:
                printing = 'Choose a face-specific composition of localized flat zones, lines and selected COPY.'
                clear = 'Leave a broad unprinted part of the printable interior clear.'
            lines.append(key + ' — PRINT: ' + printing + ' Printable interior=' + str(panel['printable_box_px']) + '.')
            lines.append(key + ' — STAYS CLEAR: ' + clear + ' The liquid must be visible through this clear area in shade ' + shade +
                         '; do not fill it with paint, a label ground, simulated pink ink or an opaque band.')
    zones = seed.get('opaque_zones', []) if seed else (opaque_zones or [])
    lines.append('Only these preregistered localized opacity exceptions are allowed; all remaining clear areas stay clear:')
    for zone in zones:
        lines.append(zone['panel'] + ': ' + zone['zone'] + '; design reason: ' + zone['reason'])
    if not zones:
        lines.append('No declared opaque zones.')
    lines += ['No leaflet artwork today. Never invent ingredients, claims, barcode bars or digits.',
              'Banned motifs: ' + ', '.join(brief['banned']) + '. No competitor names.']
    return _seal_image_prompt(brief, '\n'.join(lines) + '\n' + COPY_START + '\n' + _copy_block(brief) + '\n' + COPY_END +
                              '\nINSTRUCTION — any following preservation or fork text is guidance, never lettering.\n')


def _image_words(ctx, seed=None, opaque_zones=None):
    if typed_content(ctx.brief):
        return _typed_image_words(ctx, seed, opaque_zones)
    panels = read(ctx.root/'sheet.json')['panels']
    brief = ctx.brief
    words = ('Edit only the unprotected engine panel windows. One complete '+brief['name']+
             ', one idea across EVERY printable panel at the exact common scale. '
             'Engine-reserved material grounds stay unchanged and are not blank artwork to fill. Printed flat artwork, '
             'no scene, mockup, 3D, shadow or invented product view. Keep guides and construction '
             'outside windows unchanged. Do not move, stretch, add or remove panels. '
             'Only the approved BBROSE logo image supplies the house mark. Arabic equal or leading.\n'+
             brief['bar']+'\n')
    if seed:
        words += 'Seed: '+seed['seed']+'\nProduct-truth link: '+seed['link']+'\n'
    words += 'Panel contract: '+json.dumps({k: {'mm': p['mm'], 'box_px': p['box_px'],
                     'surface': p.get('surface'), 'decoration': p.get('decoration'),
                     'printable_box_px': p.get('printable_box_px'), 'reserved_reason': p.get('reserved_reason')} for k, p in panels.items()}, ensure_ascii=False)
    words += ('\nShades (the first is shown; an idea may rename all three): '+json.dumps(brief['shades'], ensure_ascii=False)+
              '\nThe liquid colour '+brief['shades'][0]['hex']+' is visible behind print through every clear-body face. '
              'The liquid must stay visible through the print; print is flat zones on clear. '
              'Keep the engine-drawn transparent wall edges, liquid column and highlights readable. '
              'Clear acrylic walls remain clear. Screen print, hot foil on flat zones or clear label only. '
              'No opaque wrap. The ONLY allowed deliberate opaque zones are declared below; all other clear material stays visible. '
              'Gold metal cap stays gold; its reserved panels are protected outside the edit mask. '
              'Do not add paint or opaque artwork over the cap. Any later cap marks are engraving, hot foil or deboss only. '
              'These material limits apply to panels identified clear_acrylic or gold_metal.\n'
              'Provisional copy: '+json.dumps(brief['copy'], ensure_ascii=False)+
              '\nCopy zones have flat readable grounds. Carton back short EN/ES/AR lines and leaflet reference, '
              'INCI owner-to-supply placeholder, batch and EAN frame. Never invent ingredients, claims, bars or digits. '
              'No leaflet artwork in this day-one sheet.\nBanned motifs: '+', '.join(brief['banned'])+'. No competitor names.')
    zones = seed.get('opaque_zones', []) if seed else (opaque_zones or [])
    words += '\nPreregistered deliberate opaque zones: '+json.dumps(zones, ensure_ascii=False)
    return words


def _declarations(ctx, key):
    return next(r.get('opaque_zones', []) for r in read(ctx.root/'seeds.json')['seeds'] if r['id'] == key.split('/')[0])


def _edit(ctx, key, words, parent=None, mask=None):
    if typed_content(ctx.brief):
        words = _seal_image_prompt(ctx.brief, words)
    dest = _candidate_dir(ctx, key)
    target = Path(parent) if parent else ctx.root/'sheet.png'
    mask = Path(mask) if mask else ctx.root/'sheet-mask.png'
    if not round_sheet.verify(ctx.root)['passes']:
        raise ValueError('Invalid engine sheet')
    if image_guard.competitor_in(words):
        raise ValueError('Competitor in image prompt')
    if parent and target != _candidate_dir(ctx, key.split('/')[0])/'picture.png':
        raise ValueError('Fork parent must be its marked sketch')
    if (dest/'result.json').exists() and (dest/'picture.png').exists():
        prior = read(dest/'result.json')
        if prior.get('prompt_sha256') != hashlib.sha256(words.encode()).hexdigest() or prior.get('mask_sha256') != sha(mask):
            raise ValueError('Resumed candidate inputs changed')
        if prior.get('output_sha256') != sha(dest/'picture.png'):
            raise ValueError('Pinned candidate changed')
        round_sheet.crops_and_drawing(dest, ctx.root)
        return prior
    rec = ctx.image_call('image/'+key, words, dest, target=target, mask=mask,
                         logo=Path(image_guard.APPROVED_LOGO[0]), sheet=ctx.root/'sheet.png' if parent else None)
    invariant = protected_edit(target, dest/'raw.png', mask, dest/'picture.png')
    result = dict(rec, prompt_sha256=hashlib.sha256(words.encode()).hexdigest(),
                  mask_sha256=sha(mask), output_sha256=sha(dest/'picture.png'), invariant=invariant)
    write(dest/'result.json', result)
    round_sheet.crops_and_drawing(dest, ctx.root)
    return result


def sketches(ctx):
    rows = read(ctx.root/'seeds.json')['seeds']
    for seed in rows:
        _edit(ctx, seed['id'], _image_words(ctx, seed))
    return {'candidates': [r['id'] for r in rows], 'initial_image_edits': 20}


def _images(ctx, key, with_reading=False):
    dest = _candidate_dir(ctx, key)
    caption = key+' — entire engine sheet'
    if with_reading:
        reading = read(dest/'blind.json')
        caption = key+': '+reading['idea_in_ten_words']+'; '+reading['proof_panel']+': '+reading['proof']
        if reading.get('over_length'):
            caption += '\nReading format: over length (retained as written; not an eligibility gate).'
        inspection = read(dest/'whole-object.json')
        caption += '\nRecorded whole-object findings (not automatic disqualifications): '+json.dumps(inspection['findings'], ensure_ascii=False)
    return [(caption, dest/'picture.png'), (key+' — exact flat product faces', dest/'drawing.png')]


def _declared_blanks(ctx, panels):
    declared = {panel['id']: panel['blank_reason'] for panel in ctx.brief['panels'] if has_words(panel.get('blank_reason'))}
    for key, panel in panels.items():
        if has_words(panel.get('reserved_reason')):
            declared[key] = panel['reserved_reason']
    return declared


def _inspection_decision(payload, crop, panels, declared_blanks, *, copy_keys=COPY_KEYS, content_contract=False, body_ids=()):
    """Only missing/undeclared blank panels, banned motifs and aspect disqualify.

    Declarations come from the brief or protected engine grounds before the
    call, never from a critic's explanation after seeing a blank panel.
    """
    inspected = payload.get('panels')
    if not isinstance(inspected, dict) or set(inspected) != set(panels):
        raise ValueError('Inspection must name every product panel exactly once')
    reasons, findings = [], []
    for name, panel in inspected.items():
        if not isinstance(panel, dict) or panel.get('state') not in STATES | {'missing'} or not has_words(panel.get('evidence')):
            raise ValueError('Invalid panel inspection: '+name)
        state = panel['state']
        observation = name+': '+state+' — '+panel['evidence']
        if state == 'missing' or (state == 'blank' and name not in declared_blanks):
            reasons.append(observation)
        elif state in {'generic', 'different design', 'blank'}:
            findings.append(observation)
        elif state == 'quiet' and not has_words(panel.get('explained_by')):
            findings.append(name+': quiet but unexplained')
    presence = payload.get('copy_presence')
    if not isinstance(presence, dict) or set(presence) != set(copy_keys) or any(v not in ('present', 'absent', 'unclear') for v in presence.values()):
        raise ValueError('Invalid copy presence inspection')
    for field in ('banned_motifs', 'material_issues', 'opaque_zones', 'undeclared_opaque_zones'):
        if not isinstance(payload.get(field), list) or any(not has_words(v) for v in payload[field]):
            raise ValueError('Inspection omitted '+field)
    reasons += ['banned motif: '+v for v in payload['banned_motifs']]
    if not crop['qualifies']:
        reasons.append('Engine crop/aspect mismatch over 2%')
    copy_gaps = [k+': '+v for k, v in presence.items() if v != 'present']
    findings += ['material: '+v for v in payload['material_issues']]
    findings += ['undeclared opaque zone: '+v for v in payload['undeclared_opaque_zones']]
    findings += ['copy: '+v for v in copy_gaps]
    result = {'eligible': not reasons, 'reasons': reasons, 'findings': findings,
            'inspection': payload, 'copy_gaps': copy_gaps, 'declared_blank_panels': declared_blanks,
            'not_certified': 'Provisional raster copy; live type, fit and leaflet on day two.'}
    if content_contract:
        leakage = payload.get('instruction_text_printed')
        if not isinstance(leakage, list) or any(not has_words(item) for item in leakage):
            raise ValueError('Inspection must explicitly observe instruction text printed')
        findings += ['instruction text printed: ' + item for item in leakage]
        if body_ids:
            audit = payload.get('body_face_audit')
            if (not isinstance(audit, dict) or not isinstance(audit.get('distinct'), bool)
                    or not isinstance(audit.get('identical_on_all_four'), bool)
                    or not has_words(audit.get('comparison_evidence'))
                    or not isinstance(audit.get('faces'), dict) or set(audit['faces']) != set(body_ids)
                    or (audit['distinct'] and audit['identical_on_all_four'])):
                raise ValueError('Inspection must compare all four printed body-face compositions')
            for key, face in audit['faces'].items():
                if (not isinstance(face, dict) or not isinstance(face.get('partly_clear'), bool)
                        or not isinstance(face.get('liquid_visible'), bool) or not has_words(face.get('evidence'))):
                    raise ValueError('Inspection must observe the printable interior of each body face')
                if not face['liquid_visible']:
                    findings.append('liquid not visible: ' + key + ' — ' + face['evidence'])
            if audit['identical_on_all_four']:
                findings.append('body faces identical on all four sides: ' + audit['comparison_evidence'])
            result['body_face_audit'] = dict(audit, distinct_partly_clear=(audit['distinct'] and
                all(face['partly_clear'] and face['liquid_visible'] for face in audit['faces'].values())))
    return result


def _check(ctx, key):
    dest = _candidate_dir(ctx, key)
    panels = read(ctx.root/'sheet.json')['panels']
    if set(panels) != {panel['id'] for panel in ctx.brief['panels']}:
        raise ValueError('Engine sheet panel inventory differs from product brief')
    declared_blanks = _declared_blanks(ctx, panels)
    typed = typed_content(ctx.brief)
    copy = ctx.brief['copy']
    copy_keys = COPY_KEYS
    body_ids = ()
    if typed:
        copy = printed_copy(ctx.brief)
        copy_keys = tuple(copy)
        if all(key in panels and panels[key]['surface'] == 'clear_acrylic' for key in BODY_IDS):
            body_ids = BODY_IDS
    words = ('Inspect the COMPLETE '+ctx.brief['name']+' object. Read only images; no seed, artist or ranking is supplied. '
             'Classify every panel present / quiet / blank / generic / different design / missing. '
             'Use missing when the expected panel is absent from the image; still include its ID in the inspection. '
             'Quiet is distinct from blank: describe the visible restraint and any named panel relationship. '
             'Only a missing panel, an undeclared blank panel, a banned motif or aspect error over 2% disqualifies. '
             'Material problems, copy gaps, generic or different-design panels and unexplained quiet are findings for the jury, not disqualifications. '
             'Construction and captions outside print windows are not artwork. No score, repair or typography-size certification. '
             'The approved BBROSE glyph is not itself a banned flower motif.\n'
             'Copy presence only, not a live-type fit certification: '+json.dumps(copy, ensure_ascii=False)+
             '\nBanned motifs: '+', '.join(ctx.brief['banned'])+
             '\nInspect material compliance: clear liquid remains visible on each clear_acrylic face; '
             'opaque zones are allowed ONLY where preregistered before generation; never invent a post-hoc justification. '
             'A gold_metal cap is gold and has engraving/hot-foil/deboss marks only, never painted. '
             'Each material issue needs visible panel evidence.\n'
             'Return JSON only: {"panels":{ID:{"state":"present|quiet|blank|generic|different design|missing",'
             '"evidence":"<=12 words","explained_by":"named panel relationship or empty"}},'
             '"copy_presence":{KEY:"present|absent|unclear"},"banned_motifs":[], '
             '"material_issues":[],"opaque_zones":[],"undeclared_opaque_zones":[],"object_relationship":"one sentence"}.\n'
             'Preregistered deliberate opaque zones: '+json.dumps(_declarations(ctx, key), ensure_ascii=False)+'\n'
             'Preregistered blank or protected panel grounds: '+json.dumps(declared_blanks, ensure_ascii=False)+'\n'
             'COPY KEYS: '+', '.join(copy_keys)+'\nPANELS AND PIXEL BOXES: '+
             json.dumps({k: {'box': p['box_px'], 'surface': p.get('surface')} for k, p in panels.items()}))
    ceiling = .50
    if typed:
        original_prompt_bytes = len(words.encode())
        fields = content_fields(ctx.brief)
        instructions = {path: fields[path] for path, role in ctx.brief['content_roles'].items()
                        if role == 'INSTRUCTION' and isinstance(fields[path], str) and fields[path]}
        words += ('\nTyped intake: only the COPY KEYS above are literal lettering requirements. '
                  'Directions are never required copy. Add instruction_text_printed: [] to the JSON, '
                  'with visible panel evidence and the words actually printed for each leaked instruction. '
                  'Detect full sentences and recognizable fragments, including naming/leaflet directions, seeds and design guidance. '
                  'Do not flag ordinary COPY solely because it also appears inside a direction. '
                  'The finding instruction text printed is advisory for the jury, never a disqualification. '
                  '\nReference instructions, never lettering: ' + json.dumps(instructions, ensure_ascii=False))
        if body_ids:
            words += ('\nCompare the four body faces inside their printable interiors, ignoring shared walls, '
                      'highlights and thin protected liquid-edge reveals. Related artwork is allowed; identical layouts are not distinct. '
                      'Add body_face_audit: {"distinct":true|false,"identical_on_all_four":true|false,'
                      '"comparison_evidence":"visible differences or repetition",'
                      '"faces":{ID:{"partly_clear":true|false,"liquid_visible":true|false,"evidence":"visible print and clear region"}}}. '
                      'distinct means all four printed compositions differ. partly_clear requires both printed marks and a broad '
                      'unprinted region within that face\'s printable interior; protected borders alone do not qualify. '
                      'liquid_visible means the gloss is seen through that unprinted clear area in shade ' + ctx.brief['shades'][0]['hex'] +
                      ', not an opaque pink ink band. Report observations honestly, including uncertainty as false with evidence. '
                      'The findings body faces identical on all four sides and liquid not visible go to the jury, never disqualify. '
                      'BODY FACE INTERIORS: ' + json.dumps({key: panels[key]['printable_box_px'] for key in body_ids}))
        # Preserve the original check allowance and price only the added
        # diagnostic instructions. The paid boundary still reserves its actual
        # two-attempt estimate and enforces the unchanged total round budget.
        from .cost_ledger import claude_cost_usd
        from .round_calls import TEXT_MODEL
        added_tokens = (len(words.encode()) - original_prompt_bytes) / 2
        ceiling += float(claude_cost_usd(TEXT_MODEL, added_tokens, 0)) * 2 * 1.1
    rec = ctx.text_call('check/'+key, words, dest/'whole-object-call.json', images=_images(ctx, key), max_tokens=8192, ceiling=ceiling)
    with _validation(ctx, dest/'whole-object-call.json'):
        result = _inspection_decision(rec['payload'], read(dest/'crop.json'), panels, declared_blanks,
                                      copy_keys=copy_keys, content_contract=typed, body_ids=body_ids)
    write(dest/'whole-object.json', result)
    return result


def checks(ctx):
    rows = read(ctx.root/'seeds.json')['seeds']
    results = {r['id']: _check(ctx, r['id']) for r in rows}
    result = {'eligible': [key for key, value in results.items() if value['eligible']], 'results': results}
    if typed_content(ctx.brief):
        audited = {key: value['body_face_audit'] for key, value in results.items() if 'body_face_audit' in value}
        if audited:
            count = sum(value['distinct_partly_clear'] for value in audited.values())
            result['body_face_summary'] = {'assessed': len(audited), 'distinct_partly_clear': count,
                'share': count / len(audited), 'source': 'Recorded whole-object observations; advisory, not eligibility.'}
    write(ctx.root/'eligibility.json', result)
    return result


def _blind(ctx, key):
    dest = _candidate_dir(ctx, key)
    panels = read(ctx.root/'sheet.json')['panels']
    proof_ids = [p for p in panels if p not in ('front', 'body_front', 'cap_front') and not panels[p].get('reserved_reason')]
    if not proof_ids:
        proof_ids = [p for p in panels if not panels[p].get('reserved_reason')]
    if not proof_ids:
        raise ValueError('A blind reading needs a printable panel with visible artwork')
    words = ('What idea does a stranger see in this complete '+ctx.brief['name']+'? Images only; '
             'no seed or designer intent. Say the idea in at most TEN words; describe the visible invention, '
             'never propose improvement. Name the non-front panel proving it and its decisive relationship. '
             'Also name ONE visible artwork fragment worth preserving inside a printable face, in one short line. '
             'Engine-protected wall highlights and reserved gold cap grounds are not candidate artwork. '
             'JSON only: {"idea_in_ten_words":"...","proof_panel":"...","proof":"one sentence",'
             '"preserve":"one visible fragment and panel"}. Allowed proof_panel: '+', '.join(proof_ids))
    rec = ctx.text_call('blind/'+key, words, dest/'blind-call.json', images=[('Complete object', dest/'picture.png')],
                        max_tokens=8192, ceiling=.65)
    with _validation(ctx, dest/'blind-call.json'):
        payload = rec['payload']
        if not has_words(payload.get('idea_in_ten_words')):
            raise ValueError('Blind reading needs its observed idea')
        if payload.get('proof_panel') not in proof_ids or any(not has_words(payload.get(k)) for k in ('proof', 'preserve')):
            raise ValueError('Blind reading needs a non-front proof and visible preservation fragment')
    count = len(payload['idea_in_ten_words'].split())
    payload = dict(payload, word_count=count, over_length=count > 10,
                   length_reasked='reading_length' in rec and rec['reading_length']['reasked'])
    write(dest/'blind.json', payload)
    return payload


def readings(ctx):
    ids = read(ctx.root/'eligibility.json')['eligible']
    return {'readings': {key: _blind(ctx, key) for key in ids}}


def _jury_images(ctx, ids):
    # The full panel sheet is the judging unit. Drawings remain on the owner's
    # page and in the completeness check; never double the jury's image input.
    return [_images(ctx, key, with_reading=True)[0] for key in ids]


def _role(ctx, juror):
    return ('You are the '+('creative director' if juror == 'J1' else 'senior packaging designer')+
            ' of a global prestige beauty house, reading complete '+ctx.brief['name']+' objects.\n'+QUESTION+'\n')


def coarse(ctx):
    ids = read(ctx.root/'eligibility.json')['eligible']
    if len(ids) < 8:
        raise ValueError('Fewer than eight eligible objects; a page cannot be fabricated')
    rankings, appeal, reasons = {}, {}, {}
    for juror in ('J1', 'J2'):
        words = (_role(ctx, juror)+'Order every candidate best first. '+rank_round.APPEAL+
                 '\nJSON only: {"order":[IDs],"reasons":{ID:"decisive relationship beyond front and product truth"},'
                 '"appeal":{ID:{"answer":"yes|no|uncertain","reason":"short sentence"}}}.'
                 '\nNo scores, execution penalties, repairs, caps or anchors. IDs: '+', '.join(ids))
        rec = ctx.text_call('coarse/'+juror, words, ctx.root/'jury/coarse'/f'{juror}.json',
                            images=_jury_images(ctx, ids), max_tokens=16384, ceiling=2.0)
        with _validation(ctx, ctx.root/'jury/coarse'/f'{juror}.json'):
            payload = rec['payload']
            rankings[juror] = rank_round.validate_rank(payload.get('order'), ids)
            rank_round.validate_appeal(payload.get('appeal'), ids)
            why = payload.get('reasons')
            if not isinstance(why, dict) or set(why) != set(ids) or any(not has_words(v) for v in why.values()):
                raise ValueError('Each coarse candidate needs a decisive relationship')
        appeal[juror], reasons[juror] = payload['appeal'], why
    result = rank_round.coarse_cut(rankings['J1'], rankings['J2'], keep=10)
    result.update(jurors=rankings, appeal=appeal, reasons=reasons, question=QUESTION)
    write(ctx.root/'jury/coarse/result.json', result)
    return result


def _batches(ids, size):
    if size <= 9:
        return rank_round.pair_batches(ids, size)
    if size != 10:
        raise ValueError('Only the owner-authorized ten-pair budget fallback is allowed')
    pairs = list(combinations(ids, 2))
    return [pairs[n:n+10] for n in range(0, len(pairs), 10)]


def _pairwise(ctx, ids, stage, rank_sum):
    size = getattr(ctx, 'pair_batch_size', 9)
    batches = _batches(ids, size)
    answers, appeals = {}, {}
    for juror in ('J1', 'J2'):
        rows, appeals[juror] = [], []
        for i, batch in enumerate(batches, 1):
            shown = [key for key in ids if any(key in pair for pair in batch)]
            words = (_role(ctx, juror)+'Choose exactly one winner per pair. '+rank_round.APPEAL+
                     '\nJSON only: {"pairs":[{"pair":[ID,ID],"winner":ID,"relationship":"ONE sentence; panel relationship and product truth"}],'
                     '"appeal":{ID:{"answer":"yes|no|uncertain","reason":"short sentence"}}}.'
                     '\nNo scores, execution penalties, repairs, caps or anchors. Pairs: '+json.dumps(batch))
            rec = ctx.text_call(f'pairwise/{stage}/{juror}/{i}', words, ctx.root/'jury'/stage/f'{juror}-{i}.json',
                                images=_jury_images(ctx, shown), max_tokens=16384, ceiling=1.30)
            with _validation(ctx, ctx.root/'jury'/stage/f'{juror}-{i}.json'):
                payload = rec['payload']
                rank_round.validate_pairs(payload.get('pairs'), batch)
                rank_round.validate_appeal(payload.get('appeal'), shown)
            rows.extend(payload['pairs']); appeals[juror].append(payload['appeal'])
        answers[juror] = rows
    result = rank_round.fine_order(ids, answers['J1'], answers['J2'], rank_sum)
    result.update(pairs=answers, appeal=appeals, batches=batches, question=QUESTION)
    write(ctx.root/'jury'/stage/'result.json', result)
    return result


def _calibration(ctx, **fields):
    path = ctx.root/'critic-calibration.json'
    value = read(path)
    value.update(fields)
    write(path, value)


def _publication(ctx, state, order, *, pool_summary=None):
    candidates, files = {}, {}
    for key in order:
        dest = _candidate_dir(ctx, key)
        card = {'id': key, 'directory': str(dest.relative_to(ctx.root)), 'reading': read(dest/'blind.json'), 'panels': []}
        for kind in ('picture', 'drawing'):
            path = dest/(kind+'.png'); relative = str(path.relative_to(ctx.root))
            card[kind], card[kind+'_sha256'] = relative, sha(path)
            files[relative] = sha(path)
        for name, row in read(dest/'crop.json')['panels'].items():
            path = dest/row['file']; relative = str(path.relative_to(ctx.root))
            card['panels'].append({'id': name, 'path': relative, 'sha256': sha(path), 'mm': row['mm']})
            files[relative] = sha(path)
        candidates[key] = card
    result = {'schema': 'round_publication/1', 'state': state, 'order': order,
              'candidates': candidates, 'files': files, 'question': QUESTION}
    if pool_summary is not None:
        result['pool_summary'] = pool_summary
    write(ctx.root/'publication.json', result)
    return result


def pairwise(ctx):
    previous = read(ctx.root/'jury/coarse/result.json')
    ids = previous['shortlist']
    result = _pairwise(ctx, ids, 'shortlist', {key: previous['rank_sum'][key] for key in ids})
    order = result['order'][:8]
    write(ctx.root/'cut.json', {'order': order})
    _calibration(ctx, coarse=previous, shortlist_pairwise=result, cut_to_eight=order)
    publication = _publication(ctx, 'marks', order)
    return dict(result, full_order=result['order'], order=order,
                publication=publication, publication_sha256=sha(ctx.root/'publication.json'))


def marks_fallback(ctx):
    ids = read(ctx.root/'cut.json')['order'][:3]
    marks = [{'id': key, 'preserve': read(_candidate_dir(ctx, key)/'blind.json')['preserve']} for key in ids]
    return {'marks': marks, 'source': {'kind': 'jury timeout fallback',
            'preservation_lines': 'Visible fragments from the blind readings; not owner marks.'}}


def _fork_mask(ctx, polygons):
    """Every engine-editable pixel remains open unless the owner fragment covers it."""
    if not round_sheet.verify(ctx.root)['passes']:
        raise ValueError('Invalid engine sheet before fork localization')
    panels = read(ctx.root/'sheet.json')['panels']
    if set(panels) != {panel['id'] for panel in ctx.brief['panels']}:
        raise ValueError('Fork mask panel inventory differs from product brief')
    mask = Image.open(ctx.root/'sheet-mask.png').convert('RGBA')
    original = np.asarray(mask)[..., 3] == 0
    draw = ImageDraw.Draw(mask)
    for polygon in polygons:
        draw.polygon([tuple(point) for point in polygon], fill=(255, 255, 255, 255))
    editable = np.asarray(mask)[..., 3] == 0
    fragment = original & ~editable
    coverage = {}
    for key, panel in panels.items():
        x0, y0, x1, y1 = panel['box_px']
        before = int(original[y0:y1, x0:x1].sum())
        protected = int(fragment[y0:y1, x0:x1].sum())
        after = int(editable[y0:y1, x0:x1].sum())
        gold = 'surface' in panel and panel['surface'] == 'gold_metal'
        if (gold and before) or (not gold and not before):
            raise ValueError('Fork base mask must open every non-gold panel: '+key)
        if after != before-protected:
            raise ValueError('Fork mask lost panel pixels outside the owner fragment: '+key)
        coverage[key] = {'gold_protected': gold, 'engine_editable_pixels': before,
                         'fragment_pixels': protected, 'fork_editable_pixels': after}
    return mask, fragment, coverage


def _fragment(ctx, mark):
    key = mark['id']; parent = _candidate_dir(ctx, key)/'picture.png'
    folder = ctx.root/'developments'/key
    if (folder/'fragment.json').exists():
        record = read(folder/'fragment.json')
        if record['parent_sha256'] != sha(parent) or record['mask_sha256'] != sha(folder/'fragment-mask.png') or record['preservation_line'] != mark['preserve']:
            raise ValueError('Preregistered fragment or parent changed')
        expected, _, _ = _fork_mask(ctx, record['polygons_px'])
        if not np.array_equal(np.asarray(expected), np.asarray(Image.open(folder/'fragment-mask.png').convert('RGBA'))):
            raise ValueError('Saved fork mask coverage changed outside the owner fragment')
        return record
    _fork_mask(ctx, [])  # Check every panel before purchasing localization.
    panels = read(ctx.root/'sheet.json')['panels']
    prompt = ('Locate precisely the owner-marked visible fragment in this sheet. Protect only that fragment; '
              'the rest must remain editable. Return absolute sheet pixel polygons around ALL pieces of it. '
              'Do not reinterpret or replace the owner line. Also propose two incompatible meanings for '
              'the preserved fragment, A and B: true concept forks, never colour/scale variants or repairs. '
              'JSON only: {"polygons_px":[[[x,y],[x,y],[x,y]]],"evidence":"what each polygon protects",'
              '"intents":{"A":"one line","B":"one incompatible line"}}. '
              'Sheet is 1536×1024. Owner line: '+mark['preserve']+'\nPanel boxes: '+
              json.dumps({k: p['box_px'] for k, p in panels.items()}))
    rec = ctx.text_call('fragment/'+key, prompt, folder/'fragment-call.json', images=[('Marked parent sheet', parent)],
                        max_tokens=16384, ceiling=.85)
    with _validation(ctx, folder/'fragment-call.json'):
        payload = rec['payload']; polygons = payload.get('polygons_px'); intents = payload.get('intents')
        if not isinstance(polygons, list) or not polygons or not isinstance(intents, dict) or set(intents) != {'A', 'B'} or any(not has_words(v) for v in intents.values()) or intents['A'] == intents['B']:
            raise ValueError('Fragment localization needs polygons and incompatible fork intents')
        for poly in polygons:
            if not isinstance(poly, list) or len(poly) < 3 or any(not isinstance(p, list) or len(p) != 2 or any(not isinstance(v, (int, float)) for v in p) or not (0 <= p[0] < 1536 and 0 <= p[1] < 1024) for p in poly):
                raise ValueError('Fragment polygon outside the sheet')
    mask, fragment, coverage = _fork_mask(ctx, polygons)
    with _validation(ctx, folder/'fragment-call.json'):
        if not np.any(fragment) or not np.any(np.asarray(mask)[..., 3] == 0):
            raise ValueError('Fragment must protect artwork and leave the rest editable')
    folder.mkdir(parents=True, exist_ok=True); mask.save(folder/'fragment-mask.png')
    pixels = np.asarray(Image.open(parent).convert('RGBA'))[fragment]
    record = {'parent': key, 'parent_sha256': sha(parent), 'preservation_line': mark['preserve'],
              'polygons_px': polygons, 'evidence': payload.get('evidence'), 'intents': intents,
              'mask_sha256': sha(folder/'fragment-mask.png'), 'fragment_pixels': int(fragment.sum()),
              'fragment_rgba_sha256': hashlib.sha256(pixels.tobytes()).hexdigest(), 'source': 'automatic visual localization',
              'mask_contract': 'all_panels_minus_fragment/1', 'panel_coverage': coverage}
    write(folder/'fragment.json', record)
    for fork, intent in intents.items():
        dest = folder/fork; dest.mkdir(parents=True, exist_ok=True); (dest/'intent.txt').write_text(intent+'\n')
    return record


def forks(ctx):
    marks = read(ctx.root/'marks.json')['marks']
    count = getattr(ctx, 'forks_per_mark', 2)
    if count not in (1, 2):
        raise ValueError('Owner cut order permits one or two forks per mark')
    results = {}
    for mark in marks:
        key = mark['id']; fragment = _fragment(ctx, mark)
        folder = ctx.root/'developments'/key; mask = folder/'fragment-mask.png'
        for fork in ('A', 'B')[:count]:
            child = key+'/'+fork
            reading = read(_candidate_dir(ctx, key)/'blind.json')['idea_in_ten_words']
            words = (_image_words(ctx, opaque_zones=_declarations(ctx, key))+'\nThe first image is the parent, the extra engine sheet fixes geometry. '
                     'Preserve every protected fragment pixel.\nBlind reading: '+reading+
                     '\nPreserved fragment: '+mark['preserve']+'\nFork intent: '+fragment['intents'][fork])
            if 'mask_contract' in fragment:
                editable_panels = [panel for panel, row in fragment['panel_coverage'].items() if row['fork_editable_pixels']]
                words += ('\nDevelop the complete object across every open printable panel: '+', '.join(editable_panels)+'. '
                          'This includes the carton top_end and bottom_end wherever open. Retain or create visible artwork '
                          'on both ends; do not erase them to blank grounds. Only preregistered blank panels may remain blank. '
                          'Gold caps, clear walls, engine guides and the owner fragment stay protected.')
            _edit(ctx, child, words, parent=_candidate_dir(ctx, key)/'picture.png', mask=mask)
            base = np.asarray(Image.open(ctx.root/'sheet-mask.png').convert('RGBA'))[..., 3]
            protected = (base == 0) & (np.asarray(Image.open(mask))[..., 3] != 0)
            pixels = np.asarray(Image.open(_candidate_dir(ctx, child)/'picture.png').convert('RGBA'))[protected]
            digest = hashlib.sha256(pixels.tobytes()).hexdigest()
            if digest != fragment['fragment_rgba_sha256']:
                raise ValueError('Owner fragment pixels changed')
            proof = {'byte_identical': True, 'pixels': int(protected.sum()), 'parent_and_fork_rgba_sha256': digest}
            write(_candidate_dir(ctx, child)/'fragment-proof.json', proof)
            checked = _check(ctx, child)
            if checked['eligible']:
                _blind(ctx, child)
            results[child] = checked
    result = {'candidates': list(results), 'results': results, 'forks_per_mark': count}
    write(ctx.root/'forks.json', result)
    _calibration(ctx, marks=read(ctx.root/'marks.json'), forks=result)
    return result


def final_pairwise(ctx):
    marks = read(ctx.root/'marks.json')['marks']
    forks_record = read(ctx.root/'forks.json')
    ids = []
    for mark in marks:
        ids.append(mark['id'])
        ids.extend(key for key, result in forks_record['results'].items() if key.startswith(mark['id']+'/') and result['eligible'])
    if not ids:
        raise ValueError('Final ranking needs at least one marked parent')
    marked = {mark['id'] for mark in marks}
    excluded = {key: row['reasons'] for key, row in forks_record['results'].items()
                if key.split('/')[0] in marked and not row['eligible']}
    summary = {'marked_parents': len(marks), 'eligible_forks': len(ids)-len(marks),
               'excluded_forks': excluded, 'available': len(ids), 'display_limit': 6, 'shortfall_reason': ''}
    if len(ids) < 6:
        summary['shortfall_reason'] = (
            f'Showing all {len(ids)} available candidates from the marked parents and their eligible forks. '
            f'Forks disqualified: {len(excluded)}. Six is a maximum; unmarked sketches are not added.')
    result = _pairwise(ctx, ids, 'final', None)
    full = result['order']
    result.update(full_order=full, order=full[:6], pool=ids, added_cut_survivors=[], pool_summary=summary,
                  pool_rule='Only marked parents and their eligible forks; show at most six, with no backfill.',
                  rank_sum_basis='Competition ranks from each final juror pairwise wins; no coarse rank inherited by forks.')
    write(ctx.root/'final-order.json', result)
    _calibration(ctx, final_pairwise=result, final_six=result['order'], pick_status='pending')
    return result


def pick_page(ctx):
    final = read(ctx.root/'final-order.json')
    return _publication(ctx, 'pick', final['order'], pool_summary=final.get('pool_summary'))


def run_step(name, context):
    context.root = Path(context.root)
    context.root.mkdir(parents=True, exist_ok=True)
    if name == 'sheet':
        return round_sheet.build(context.brief, context.root)
    operations = {'seeds': seeds, 'sketches': sketches, 'checks': checks, 'readings': readings,
                  'coarse': coarse, 'pairwise': pairwise, 'marks_fallback': marks_fallback,
                  'forks': forks, 'final_pairwise': final_pairwise, 'pick_page': pick_page}
    if name not in operations:
        raise ValueError('Unknown media round step: '+name)
    return operations[name](context)
