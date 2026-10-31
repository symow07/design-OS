"""Day 11, D-D11-7 (and D-D11-8 by the same function) — the lipstick's carton on our own dieline engine, at $0.

THE DIE. A straight tuck end (ECMA A20.20.01.01) from ``apps/dielines``: ``straight_tuck_end_carton`` at its print-ready
version (``registry.print_ready_version``: 1.4, the corrected closure — both tucks hang from the back; 1.0–1.3 drew the
bottom tuck on the front under the straight-tuck name, TRADE_RULES §1), inside 22 × 22 × 83 mm (the lip balm's
20 × 20 × 73), bleed 3, safe 3, board 0.45, the glue flap 12 mm (TRADE_RULES G2's default). The die is drawn as the engine
gives it, on locked cut and crease layers, and read back from the written file within 0.01 mm; its fold check
(``fold_check.check``) is recorded.

THE FACES. Six printing faces: the four body panels and the two tuck lids (the closed carton's ends). A face's ground runs
3 mm past its cut edges and 0.5 mm past its creases, never onto the dust flaps, the glue flap or the tongues
(``palette_box.ground_shape``); those stay clean, measured as ink under 0.5 mm² each at 300 dpi (``palette_box.clean_parts``).

THE FRONT carries the art passed in: a picture (PNG) filling the front to its bleed, and/or engine nodes laid out in the
front's own frame (mm, origin at the panel's top-left, upright as the carton stands). With neither, a flat indigo ground
stands in, NAMED as the placeholder in the record. The foil and relief plates are what the front's nodes carry: none for
the placeholder, and none is ever synthesised. Each node's box is read from its own emitted file (``front_elements``) and
checked like the copy: inside the front's safe area less the thumb notch's keep-out (its radius plus 4 mm), across no
crease. A picture's content is a raster and is not measured: the record says so.

THE BACK AND THE LONG SIDES carry the regulated copy, one language to a panel, set along the panel's length and turned a
quarter counter-clockwise (it reads bottom to top as the carton stands; ``graph`` turn, the shared engine's quarter turn): a 22 mm panel is 16.45 mm wide inside its safe area, too narrow
for the ℮ line (28.5 mm at the 3 mm the sign needs) or for one line of description across it. Every body line shares one
size, from 7 pt down to the 5 pt floor (§W2, D-D11-7) in 0.25 pt steps until all three panels hold their copy: a line that
does not fit gets smaller, never dropped and never moved (D-D8-9); at the floor whatever still does not fit is drawn and
reported line by line, nothing hidden. The back closes on the ℮ line (the house's sign, ``lid_master.sign_segments``, at
the figures' cap height, 3 mm, never larger than its neighbours — D-D11-6) and the batch and expiry write-in fields; a
long side carries the EAN-13's placeholder frame (no number) in ladder orientation, its bars' height cut to the panel's
safe width — listed "truncated — owner to confirm". Which language stands on which panel, and which side takes the EAN,
is measured (``plan``): of the twelve ways, the one whose copy fits at the largest size, then the one with the fewest
lines run past a cut edge (cut off in print), then the fewest lines over, on a tie the house's order (English on the back,
Spanish on the left side, Arabic on the right, the EAN on the right); the fit report says where each overflowing line lies
on the flat. THE ENDS carry the approved logo (``lid_master.logo_parts``), the top end's turned 180° so it reads from the
front, each read back from the file inside its safe area. The ℮ is read back from the file too, its height against the
figures' own ink.

THE COPY. English in this module (the owner's words and the builder's drafts named below); Spanish and Arabic from the
translations file the lead makes with the house's ``panel_translate`` (``docs/audit/rescue_runtime/day11/
carton_translate_run.py``, never run from here). Until that file exists for this English, the copy panels are refused —
no translation is invented. The Arabic claims follow D-D11-6 at build time, by the sticker's own rule
(``palette_sticker.arabic_claims`` on ``Brand.claims``): the house's line printed exactly when every row is confirmed,
otherwise the owner's fallback line marked "owner to confirm" — so the carton and the sticker never print different
claims. The words drawn are checked against the written file's ActualText, word for word, each language against its own
spans (``palette_sticker.copy_check``).

Files: carton-artwork.pdf (page 1 the artwork on the die, cut and crease on locked layers; page 2 the foil plate; page 3
the relief plate), carton-artwork.ai (layers), carton-flat.png (300 PPI), carton-fold-check.json, carton-1to1-A4.pdf (100 %
on A4 with crop and fold marks and a 100 mm ruler) and carton-fit-report.json. The four drawn files are written into
``engine/staging`` and moved into place only once the shipped PDF carries its copy word for word; a refused build leaves
them there, never beside the records.

[Day 13, §1.1 and §1.3] THE NARROW PANELS. The owner: "the layout engine, for panels under 25 mm, sets the regulated copy
in columns inside the safe area or runs it vertically along the long sides; the fold check must report zero crossings";
and "the Arabic panel's copy cleared from the net line by one line's space". Both sticks' panels are under 25 mm (22.45
and 20.45). The copy already runs along the panels; what the balm lacked was room (six lines across its 14.45 mm, the ℮
line and the EAN each taking the whole width for 29 mm). So each band carries its one zone and the copy is set in columns
inside the safe area round it (``lay``): a row beside a zone runs to it less its clearance, a row past a part-width zone
runs the panel's whole safe length. The copy stands ZONE_GAP_MM plus one line's pitch (at the size set) clear of the ℮
line and the write-in fields. ``plan`` measures, besides Day 12's twelve ways, the fields moved to the far end of the long
side without the EAN (the ℮ line then alone on the back, part width) and the INCI placeholder run on after the
description; a way that sets a line across a crease or onto another face ranks after one that sets none (a box wholly on
another face counts as a crossing, ``content_rows``), and on a tie Day 12's layout is kept. What the rule did to each
carton is said in its fit report (``narrow_panels``), with the clearance read back from the file (``foot_clearance``).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_box as pb
from apps.pipeline.services import palette_sticker as ps

SCHEMA = 'day13_carton/2'                   # [Day 13] a crossing counts a box on another face; the zero-crossings block
FIT_SCHEMA = 'day13_carton_fit/2'           # [Day 13] the columns, the narrow-panel rule, the clearance read back
TRANSLATIONS_SCHEMA = 'day11_carton_translations/1'
TRANSLATIONS_NAME = 'carton-translations.json'
SURFACE = 'apps/pipeline/services/stick_carton.py::build'
DAY11 = lm.REPO / 'docs' / 'audit' / 'day-11'
RUNNER = 'docs/audit/rescue_runtime/day11/carton_translate_run.py'

TEMPLATE = 'straight_tuck_end_carton'
TEMPLATE_VERSION = '1.4'            # the print-ready version: both tucks on the back (the corrected closure)
BLEED_MM = 3.0                      # D-D11-7
SAFE_MM = 3.0                       # D-D11-7 (the schema's own minimum)
BOARD_MM = 0.45                     # D-D11-7: the lipstick's board
GLUE_TAB_MM = 12.0                  # TRADE_RULES G2's default (the schema's 10 mm is the older default)
DIE_TOL_MM = 0.01                   # every cut and crease segment read back from the file within 0.01 mm
NOTCH_CLEAR_MM = 4.0                # the thumb notch's keep-out: its radius plus 4 mm (palette_box's 13 mm for r 9)

BODY_START_PT = 7.0
BODY_FLOOR_PT = 5.0                 # §W2, D-D11-7: the floor; type shrinks to it and never drops
BODY_STEP_PT = 0.25
LEAD = 1.25                         # line pitch as a share of the size (palette_sticker's)
PARA_GAP = 0.0                      # a paragraph opens a new line with no gap: the 16.45 mm band holds seven lines
#                                     at the floor, and a quarter-line gap per paragraph costs the seventh
MM_PER_PT = 25.4 / 72.0
SIGN_MM = 3.0                       # the ℮ at 3 mm (D-D11-6: at the line's cap height, never larger than its neighbours)
ZONE_GAP_MM = 3.0                   # the copy stands this far clear of the foot or the EAN frame along the panel
FIELD_PT = 6.0                      # the write-in fields' labels
FIELD_BOX_MM = (18.0, 3.2)          # each write-in box: long enough for a coder's batch or date, one row tall
FIELD_GAP_MM = 1.0                  # between the ℮ line and the fields, and between the fields
FIELD_LABEL_GAP_MM = 1.5            # a field's label stands this far before its box
FIELD_LABEL_LIFT_MM = 0.6           # a label's baseline above its box's lower edge
FIELD_STROKE_MM = 0.15
NARROW_PANEL_MM = 25.0              # [Day 13, §1.3] a copy panel narrower than this sets its copy in columns (``lay``)
FOOT_CLEAR_LINES = 1                # [Day 13, §1.1] the copy stands one more line's space clear of the ℮ line and the
#                                     fields: ZONE_GAP_MM plus one line's pitch at the size set, along the panel
ZONE_ACROSS_MM = FIELD_GAP_MM       # [Day 13] across the panel a row stands this far clear of a part-width zone: the
#                                     foot's own gap between the ℮ line and its fields
FIELDS_AT = ('under_net', 'side_near', 'side_far')   # [Day 13] the write-in fields under the ℮ line on the back (Day 12's
#                                     foot), or at the far end of the long side without the EAN, on its first rows or last
EAN_MM = ps.EAN_MM                 # the symbol's frame at 80 % (29.83 × 20.74 mm): Day 10's, the smallest magnification
EAN_PT = 6.0
EAN_STROKE_MM = 0.15
END_LOGO_W_MM = 12.0                # the logo on each end, 12 mm wide (2.5 mm tall), inside both sticks' 14 mm safe ends
CONTRAST_MIN = 7.0                  # the copy against its ground (D-D11-4's rule for the box's copy zone, taken here)
A4_MM = (210.0, 297.0)
FOLD_MARK_MM = 4.0
A4_SCALE_TOL = 0.001                # the A4 sheet's measured scale (a crease's drawn length over its own) within 0.1 %
CREASE_RGB = (0.0, 0.6, 0.9)        # the crease's colour as ``draw_die`` strokes it
CUT_RGB = (0.85, 0.0, 0.55)         # the cut's
READ_TOL_MM = 0.02                  # a box read back from the file stands where it should within 0.02 mm
COLOUR_TOL = 0.01                   # a fill read back is the colour asked for within 0.01 a channel
SIGN_BOX_MM = (1.0, 6.0)            # a filled path read as the ℮: its height between these (palette_sticker's reading)
STAGING = ('engine', 'staging')     # where the four drawn files wait until the shipped PDF's copy holds
DELIVERABLES = ('carton-artwork.pdf', 'carton-artwork.ai', 'carton-flat.png', 'carton-1to1-A4.pdf')
#: Day 11's entry (2026-10-23 19:01 Asia/Shanghai): the owner's $0.20 for the day's translations counts from here
DAY11_ENTRY_UTC = datetime(2026, 10, 23, 11, 1, tzinfo=timezone.utc)
TRANSLATE_CAP_USD = 0.20
LANGS = ('en', 'es', 'ar')
ARABIC_RE = re.compile('[؀-ۿ]')
FIGURE_RE = re.compile(r'\d')                 # [Day 12, the eye's r0] a word with a figure and no letter is a number
LETTER_RE = re.compile(r'[^\W\d_]')
#: [Day 12, D-D12-8] a number's unit in a Latin line: it rides with its number, and the pair keeps the word after it
UNIT_WORDS = frozenset(('g', 'mg', 'kg', 'ml', 'l', 'oz', 'fl', 'mm', 'cm', 'm'))

# The placeholder colours until the lead passes the Ẓilāl master's measured ones (``build(colours=…)``): the indigo
# ground (D-D11-7: "the indigo ground", #1B2148-ish), a cream for the copy, a rose gold for the logo's ink, white
# behind the barcode (a symbol prints dark bars on a light ground; on indigo it needs its own light box).
PLACEHOLDER_COLOURS = {'ground': '#1B2148', 'ink': '#F2E8D8', 'logo': '#C9977F', 'ean_ground': '#FFFFFF'}

PRODUCTS = {
    'lipstick': {'key': 'lipstick', 'decision': 'D-D11-7', 'inside_mm': (22.0, 22.0, 83.0), 'name': 'Lipstick',
                 'shade': 'Wild Rose', 'net': ('3.5 g', '0.12 oz'), 'out': DAY11 / 'lipstick' / 'carton'},
    'lip_balm': {'key': 'lip_balm', 'decision': 'D-D11-8', 'inside_mm': (20.0, 20.0, 73.0), 'name': 'Lip Balm',
                 'shade': 'Rosewater', 'net': ('4.5 g', '0.15 oz'), 'out': DAY11 / 'lip-balm' / 'carton'},
}

# THE ENGLISH COPY. The owner's words: "Made in UAE." and the net (D-D11-7, D-D11-8). The house's: the four claims
# (Brand.claims, §BH55(a), as Day 10's sticker printed them). THE BUILDER'S DRAFT, FOR HIS REVIEW: the description, how
# to use and the warnings — no brief gives them for the sticks; they claim nothing (no finish, benefit or ingredient).
ENGLISH = {
    'lipstick': {'description': 'Enchanted Rose lipstick in the shade Wild Rose.',
                 'how_to_use': 'Apply directly to the lips from the centre outwards; layer for more colour.',
                 'warnings': 'For external use only. Stop use if irritation occurs.'},
    'lip_balm': {'description': 'Enchanted Rose lip balm in the tint Rosewater.',
                 'how_to_use': 'Apply to the lips as often as needed.',
                 'warnings': 'For external use only. Stop use if irritation occurs.'},
}
MADE_IN_EN = 'Made in UAE.'
HEADS_EN = {'how_to_use': 'How to use', 'warnings': 'Warnings'}
INCI_PLACEHOLDER = 'INCI: owner to supply'      # ⟪PROVISIONAL⟫ in the record only: the emitter refuses the marker
# The claims are never sent to translation: the English is the house's; the Spanish is the owner's line verbatim
# (D-D11-6). The Arabic is not held here: it is resolved at build time by D-D11-6's rule (``palette_sticker.
# arabic_claims`` on Brand.claims) — the house's line when every row is confirmed, else the owner's fallback line, marked
# "owner to confirm" — the same rule, and so the same line, as the sticker's.
CLAIMS = {'en': ps.ENGLISH['claims'],
          'es': 'No testado en animales · 100 % vegano · Probado dermatológicamente · Larga duración'}
NET_ONCE = ('the ℮ line stands once, on the back (its figures and sign need no translation), not in each language\'s '
            'panel: Day 10\'s review and D-D11-4 kept it verbatim in every language column, and D-D11-7 lists the net '
            'among each panel\'s regulated copy — owner to confirm')
ORDER = ('description', 'ingredients', 'how_to_use', 'warnings', 'made_in', 'claims')   # "Made in UAE." closes a
#                                                     sentence, so the claims run on after it and end the copy
PARA_STARTS = ('description', 'ingredients', 'how_to_use')   # a field that opens a new line; the rest run on
# [Day 13, §1.3] the paragraphs a band may take on a narrow panel: Day 12's, or the INCI placeholder run on after the
# description ("… Rosewater. INCI: owner to supply"), which saves its line — nothing dropped or moved. Latin-script
# bands only: in a right-to-left line the description's Latin tail and the Latin INCI after it are set segment by
# segment from the right, so they would read in reverse ("INCI: owner to supply Rosewater."); the Arabic keeps Day 12's
PARAGRAPHS = {'as_set': PARA_STARTS, 'inci_run_on': ('description', 'how_to_use')}
REGULATED = ('ingredients', 'how_to_use', 'warnings', 'claims', 'made_in')
DRAFT = 'the builder\'s draft — for review'      # Day 11-12's wording (D-D13-6 makes it the owner's draft)
# [Day 13, D-D13-6] the owner: "the English my draft (I will edit it on the page before Day 15 if I choose), the Spanish
# and Arabic machine drafts 'for review', the INCI a placeholder 'owner to supply', the Arabic claims 'owner to confirm'"
OWNER_DRAFT = 'the owner\'s draft (D-D13-6: his to edit on the page before Day 15)'
MACHINE_DRAFT = 'machine translation — for review'
SOURCES_EN = {'description': OWNER_DRAFT, 'how_to_use': OWNER_DRAFT, 'warnings': OWNER_DRAFT,   # [Day 13, D-D13-6]
              'made_in': 'the owner\'s words (D-D11-7)',
              'claims': 'the house\'s four claims (Brand.claims, §BH55(a))',
              'ingredients': 'placeholder — owner to supply (⟪PROVISIONAL⟫, never invented)'}
# where each translated key of the lead's file lands in the copy (panel_translate's own keys, as Day 10 sent them)
LANDS = {('prose', 'description'): 'description', ('prose', 'how_to_use'): 'how_to_use',
         ('prose', 'warnings'): 'warnings', ('short lines', 'description'): 'made_in',
         ('short lines', 'how_to_use'): 'head:how_to_use', ('short lines', 'warnings'): 'head:warnings'}
FIELDS = (('BATCH', 'batch'), ('EXP', 'expiry'))


class TranslationsMissing(Exception):
    """The Spanish and Arabic are not on disk for this English: the copy panels are refused, never invented."""


class CopyRefused(Exception):
    """The written file does not carry the copy word for word (a line dropped, moved or changed)."""


# --- the die and its faces -------------------------------------------------------------------------------------------

def die_input(product):
    """The engine's input for the product's straight tuck end."""
    from apps.dielines.validators.schema import DielineInputJSON
    w, d, h = product['inside_mm']
    return DielineInputJSON(template=TEMPLATE, template_version=TEMPLATE_VERSION, unit='mm',
                            dimensions={'width_mm': w, 'depth_mm': d, 'height_mm': h},
                            print_settings={'bleed_mm': BLEED_MM, 'safe_margin_mm': SAFE_MM},
                            construction={'glue_tab_mm': GLUE_TAB_MM, 'board_thickness_mm': BOARD_MM, 'kerf_mm': 0.0,
                                          'thickness_compensation': True},
                            metadata={'product_name': product['name'], 'product_type': 'stick carton', 'notes': ''})


def die(product):
    """The die from our engine at the template's print-ready version (refused if that is not 1.4, the version whose
    faces this module reads), with both tucks on the back (the corrected closure): coordinates in mm, origin at the
    flat's top-left; and its fold check."""
    from apps.dielines import registry
    from apps.dielines.geometry import fold_check
    from apps.dielines.geometry.engine import calculate_dieline
    ready = registry.print_ready_version(TEMPLATE)
    if ready != TEMPLATE_VERSION:
        raise ValueError('the straight tuck end\'s print-ready version is %s, not %s' % (ready, TEMPLATE_VERSION))
    coords = calculate_dieline(die_input(product))
    hung = sorted({t['panel'] for t in coords.derived['tucks']})
    if hung != ['back']:
        raise ValueError('the tucks hang from %s, not both from the back' % hung)
    return coords, fold_check.check(coords)


def faces(coords):
    """The six printing faces (x0, y0, x1, y1 mm) with their cut edges (where the ground bleeds 3 mm; the rest are
    creases), their 3 mm safe boxes and their grounds' boxes. On the straight tuck end both lids hang from the back, so
    the back is all creases, the front is cut at its top (the thumb notch) and bottom, the right side at its free edge,
    and each end (a lid) at its left and right. The front's safe area is its box less the thumb notch's keep-out (a disc
    of the notch's radius plus NOTCH_CLEAR_MM about its centre, ``keep_out``): the notch's cut alone reaches past the
    plain 3 mm box (r 4.04 at the lipstick's top edge)."""
    panels = {p.name: (p.x, p.y, p.x + p.width, p.y + p.height) for p in coords.panels}
    tucks = {t['end']: t for t in coords.derived['tucks']}
    top, bottom = tucks['top'], tucks['bottom']
    out = {'back': {'box': panels['back'], 'cut': ()},
           'side_left': {'box': panels['side_left'], 'cut': ()},
           'front': {'box': panels['front'], 'cut': ('top', 'bottom')},
           'side_right': {'box': panels['side_right'], 'cut': ('right',)},
           'top_end': {'box': (top['x_l'], top['fold_y'], top['x_r'], top['hinge_y']), 'cut': ('left', 'right')},
           'bottom_end': {'box': (bottom['x_l'], bottom['hinge_y'], bottom['x_r'], bottom['fold_y']),
                          'cut': ('left', 'right')}}
    for f in out.values():
        x0, y0, x1, y1 = f['box']
        f['safe'] = (x0 + SAFE_MM, y0 + SAFE_MM, x1 - SAFE_MM, y1 - SAFE_MM)
        grow = {side: pb.CREASE_OVER_MM for side in ('left', 'top', 'right', 'bottom')}
        for side in f['cut']:
            grow[side] = BLEED_MM
        f['ground'] = (x0 - grow['left'], y0 - grow['top'], x1 + grow['right'], y1 + grow['bottom'])
        f['keep_out'] = None
    notch = coords.derived['thumb_notch']
    out[notch['panel']]['keep_out'] = {'cx': notch['cx'], 'cy': notch['y'], 'r_mm': notch['r'] + NOTCH_CLEAR_MM}
    return out


def keep_out_clear_mm(box, keep_out):
    """How far a flat box stands from a keep-out disc's centre, less its radius (mm; negative when it reaches into the
    disc) — palette_box's distance from the notch, against the radius plus 4 mm."""
    import math
    cx, cy = keep_out['cx'], keep_out['cy']
    d = math.hypot(max(box[0] - cx, 0.0, cx - box[2]), max(box[1] - cy, 0.0, cy - box[3]))
    return d - keep_out['r_mm']


def flat_box(local, panel_box):
    """A box in a copy band's own frame (u along the panel's length from its bottom, v across from its left edge) on
    the flat, the band turned a quarter counter-clockwise: flat x = X0 + v, flat y = Y1 − u."""
    u0, v0, u1, v1 = local
    x0, y0, x1, y1 = panel_box
    return (x0 + v0, y1 - u1, x0 + v1, y1 - u0)


def band_turn(panel_box):
    """The engine's turn (a, b, c, d, e, f) that stands a band laid out along the panel's length on the panel."""
    x0, y0, x1, y1 = panel_box
    return (0.0, -1.0, 1.0, 0.0, x0, y1)


# --- the copy ----------------------------------------------------------------------------------------------------------

def translations_path(product):
    return product['out'] / TRANSLATIONS_NAME


def translation_request(product):
    """What the lead's runner sends to ``panel_translate.translate_panel_info`` (Day 10's two shapes): the prose, then
    the short line and the two heads. INCI, the claims, the ℮ line and the field labels are never sent."""
    en = ENGLISH[product['key']]
    return {'prose': {'description': en['description'], 'how_to_use': en['how_to_use'], 'warnings': en['warnings']},
            'short lines': {'description': MADE_IN_EN, 'how_to_use': HEADS_EN['how_to_use'],
                            'warnings': HEADS_EN['warnings']}}


def load_translations(product, path):
    """The Spanish and Arabic from the lead's file — refused (``TranslationsMissing``) when the file is absent, is for
    another product, or was translated from other English than this module's; the Arabic set unvowelled (harakat out,
    as printed labels are and as Day 10's sticker set it)."""
    path = Path(path)
    if not path.exists():
        raise TranslationsMissing('%s does not exist: the Spanish and Arabic copy panels are not built (no translation '
                                  'is invented); the lead runs %s' % (path, RUNNER))
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise TranslationsMissing('%s is not JSON (%s)' % (path, exc)) from exc
    if not isinstance(data, dict) or 'schema' not in data or data['schema'] != TRANSLATIONS_SCHEMA:
        raise TranslationsMissing('%s is not a %s file' % (path, TRANSLATIONS_SCHEMA))
    if 'product' not in data or data['product'] != product['key']:
        raise TranslationsMissing('%s is not the %s\'s translations' % (path, product['key']))
    if 'calls' not in data or not isinstance(data['calls'], dict):
        raise TranslationsMissing('%s holds no calls: re-run the translation' % path)
    out = {'es': {}, 'ar': {}}
    for call, english in translation_request(product).items():
        if call not in data['calls'] or not isinstance(data['calls'][call], dict):
            raise TranslationsMissing('%s holds no %r call: re-run the translation' % (path, call))
        entry = data['calls'][call]
        for part in ('english', 'translations'):
            if part not in entry:
                raise TranslationsMissing('%s\'s %r call says no %s: re-run the translation' % (path, call, part))
        if entry['english'] != english:
            raise TranslationsMissing('%s holds no %r call translated from this English: re-run the translation' %
                                      (path, call))
        gaps = call_gaps(english, entry['translations'])
        if gaps:
            raise TranslationsMissing('%s has no %s for %r' % (path, ', '.join('%s %s' % g for g in gaps), call))
        got = entry['translations']
        for lang in ('es', 'ar'):
            for key in english:
                text = ' '.join(got[lang][key].split())
                if lang == 'ar':
                    text = ps.HARAKAT.sub('', text)
                out[lang][LANDS[(call, key)]] = text
    for key in ('model', 'spend'):
        if key not in data:
            raise TranslationsMissing('%s does not say its %s' % (path, key))
    return out, {'file': str(path), 'model': data['model'], 'spend': data['spend']}


def call_gaps(english, got):
    """What one translate call left out: each (language, key) of ``english`` with no non-empty Spanish or Arabic string
    in ``got`` (panel_translate drops an empty or unknown value without a word, so a gap is only seen here)."""
    gaps = []
    for lang in ('es', 'ar'):
        block = None
        if isinstance(got, dict) and lang in got:
            block = got[lang]
        for key in english:
            if not isinstance(block, dict) or key not in block or not isinstance(block[key], str) \
                    or not block[key].strip():
                gaps.append((lang, key))
    return gaps


def write_partial(path, data):
    """The lead's file as paid for, written beside ``path`` under a stamped partial name (never ``path`` itself, so a
    run refused afterwards can be made again without a deletion): the record of what was paid."""
    path = Path(path)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    partial = path.with_name('%s.%s.partial' % (path.name, stamp))
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return partial


def write_translations(product, data, path):
    """The translations file written whole or not at all: ``data`` written to a partial name (``write_partial``), read
    back by ``load_translations`` there — every key of every call, in both languages, non-empty — and moved onto
    ``path`` only when it loads. Refused (``TranslationsMissing``) otherwise: ``path`` stays absent, so the run can be
    made again, and the partial file stays as the record of what was paid. Returns the loader's (copy, provenance)."""
    path = Path(path)
    if path.exists():
        raise FileExistsError('%s exists: a translations file is never overwritten' % path)
    partial = write_partial(path, data)
    load_translations(product, partial)
    os.replace(partial, path)
    return load_translations(product, path)


def spent_since(rows, since):
    """The settled spend (USD, and the count) of ledger rows — (accounted micro-dollars, started_at, state) — whose call
    started at or after ``since`` (an aware datetime). The rows are compared as instants, never as strings: the ledger
    writes its times with their +08:00 offset, so Day 10's calls at 11:13+08:00 (03:13 UTC) fall before Day 11's entry
    at 11:01 UTC though their text sorts after it. A reserved row is not settled and is not counted."""
    total, count = 0, 0
    for accounted, started_at, state in rows:
        at = datetime.fromisoformat(started_at)
        if at.tzinfo is None:
            raise ValueError('a ledger row\'s start carries no offset: %r' % started_at)
        if state != 'reserved' and at >= since:
            total += accounted
            count += 1
    return total / 1e6, count


def copy(product, translated, model, ar_claims):
    """Each language's sections in order: {lang, field, head, text, script, source, review, regulated, verbatim,
    para} — English from this module, Spanish and Arabic from ``translated`` (``load_translations``), the Arabic claims
    as D-D11-6's rule gives them (``ar_claims``: ``palette_sticker.arabic_claims``' (text, source, owner_to_confirm,
    why)), printed exactly."""
    ar_text, ar_source, ar_confirm, _ = ar_claims
    out = {}
    for lang in LANGS:
        rows = []
        for field in ORDER:
            head = None
            if field in HEADS_EN and lang == 'en':
                head = HEADS_EN[field]
            elif field in HEADS_EN:
                head = translated[lang]['head:' + field]
            review = None
            if field == 'ingredients':
                text, source, verbatim = INCI_PLACEHOLDER, SOURCES_EN['ingredients'], True
                review = 'placeholder — owner to supply'
            elif field == 'claims' and lang == 'ar':
                text, source, verbatim = ar_text, ar_source, True
                if ar_confirm:
                    review = ps.OWNER_TO_CONFIRM
            elif field == 'claims':
                text, verbatim = CLAIMS[lang], True
                source = {'en': SOURCES_EN['claims'], 'es': 'the owner\'s words, verbatim (D-D11-6)'}[lang]
            elif field == 'made_in' and lang == 'en':
                text, source, verbatim = MADE_IN_EN, SOURCES_EN['made_in'], True
            elif lang == 'en':
                text, source, verbatim = ENGLISH[product['key']][field], SOURCES_EN[field], False
                review = OWNER_DRAFT                      # [Day 13, D-D13-6] (Day 12: the builder's draft — for review)
            else:
                text, verbatim = translated[lang][field], False
                source = 'machine translation (panel_translate, %s)' % model
                review = MACHINE_DRAFT
            script = 'latin'
            if lang == 'ar' and field != 'ingredients':
                script = 'arabic'
            rows.append({'lang': lang, 'field': field, 'head': head, 'text': text, 'script': script, 'source': source,
                         'review': review, 'regulated': field in REGULATED, 'verbatim': verbatim,
                         'para': field in PARA_STARTS})
        out[lang] = rows
    return out


# --- setting the copy --------------------------------------------------------------------------------------------------

def face_metrics(fc):
    """Each face's ascender, descender and cap height (em), as the file's reader (PyMuPDF) and the font say them:
    the ascender and descender bound a line's box, the cap height sizes the ℮ line."""
    import fitz
    from fontTools.ttLib import TTFont
    out = {}
    for key, face in fc.items():
        f = fitz.Font(fontfile=str(face['path']))
        tt = TTFont(str(face['path']), lazy=True)
        out[key] = {'asc_em': float(f.ascender), 'desc_em': -float(f.descender),
                    'cap_em': tt['OS/2'].sCapHeight / tt['head'].unitsPerEm}
    return out


def is_number(word):
    """A word that carries a figure and no letter ('100%', '3.5')."""
    return FIGURE_RE.search(word) is not None and LETTER_RE.search(word) is None


def tokens(row):
    """A section's words as (field, face key, word); its head (medium for Latin, the Arabic face for Arabic) first,
    with its colon. A word with no letter and no figure ('·', '%') is bound to the one before it, so no line opens on it
    (D-D11-6: no line opens on "·"). [Day 12, the eye's r0] In Arabic a number is bound to the word before it — its
    word: "نباتي 100%" is one claim — unless that word closes a claim with "·": the line breaker never parts them
    (a no-break; the space drawn between them is the copy's own, so the file's words read back as written).
    [Day 12, D-D12-8] In a Latin line a number (with its "%" or its unit) is bound to the word AFTER it — "100 % vegano"
    is one claim, as the Arabic's is with the word before — unless the number closes a claim with "·"."""
    body = 'regular'
    if row['script'] == 'arabic':
        body = 'arabic'
    raw = []
    if row['head'] is not None:
        head_face = 'medium'
        if ARABIC_RE.search(row['head']):
            head_face = 'arabic'
        raw += [(row['field'], head_face, w) for w in (row['head'] + ':').split()]
    raw += [(row['field'], body, w) for w in row['text'].split()]
    out = []
    forward = False                      # the last token a Latin number (or its unit) still waiting for its word
    for field, face, word in raw:
        bound = bool(out) and out[-1][1] == face
        if bound and not re.search(r'\w', word):
            out[-1] = (field, face, out[-1][2] + ' ' + word)
            forward = forward and '·' not in word
        elif bound and row['script'] == 'arabic' and is_number(word) and not out[-1][2].endswith('·'):
            out[-1] = (field, face, out[-1][2] + ' ' + word)
        elif bound and forward:
            out[-1] = (field, face, out[-1][2] + ' ' + word)
            forward = word.strip('.,;:').lower() in UNIT_WORDS
        else:
            out.append((field, face, word))
            forward = row['script'] != 'arabic' and is_number(word)
    return out


def splits_a_number(text, next_text, rtl):
    """Whether the break between a line (``text``) and the next line of its paragraph (``next_text``) parts a number
    from its word: in a Latin line the line ends on the number (its "%" or unit with it) and its word opens the next;
    in an Arabic line the next line opens on the number, its word ending this one. A claim closed by "·" is no split."""
    if not next_text:
        return False
    if rtl:
        return is_number(next_text.split()[0]) and not text.rstrip().endswith('·')
    words = text.split()
    while words and not re.search(r'\w', words[-1]) and words[-1] != '·':
        words.pop()                                    # the number's own "%" (or a bracket) rides with it
    if words and words[-1].strip('.,;:').lower() in UNIT_WORDS and len(words) > 1 and is_number(words[-2]):
        return True
    return bool(words) and words[-1] != '·' and is_number(words[-1])


def merge(line):
    """Consecutive words of one field in one face joined into one segment (one TextRun)."""
    segs = []
    for field, face, word in line:
        if segs and segs[-1][0] == field and segs[-1][1] == face:
            segs[-1] = (field, face, segs[-1][2] + ' ' + word)
        else:
            segs.append((field, face, word))
    return segs


_WIDTHS = {}                         # [Day 13] palette_sticker.width_mm remembered: the plan sets 72 ways, not 12


def drawn_mm(text, face, size_pt):
    """``palette_sticker.width_mm`` (the width the emitter draws), remembered by text, face and size."""
    key = (text, face['label'], size_pt)
    if key not in _WIDTHS:
        _WIDTHS[key] = ps.width_mm(text, face, size_pt)
    return _WIDTHS[key]


def line_width(segs, size_pt, fc):
    """A line's drawn width (mm): its segments as the emitter draws them, a space after each but the last."""
    total = 0.0
    for i, (field, face, text) in enumerate(segs):
        total += drawn_mm(text, fc[face], size_pt)
        if i < len(segs) - 1:
            total += drawn_mm(' ', fc[face], size_pt)
    return total


def wrap(rows, length_mm, size_pt, fc):
    """One paragraph's sections run on and wrapped to the line's length on their words: lines of segments."""
    lines = [[]]
    for tok in [t for r in rows for t in tokens(r)]:
        if lines[-1] and line_width(merge(lines[-1] + [tok]), size_pt, fc) > length_mm:
            lines.append([tok])
        else:
            lines[-1].append(tok)
    return [merge(line) for line in lines if line]


def paragraphs(rows, starts=None):
    """The sections grouped into paragraphs: a field in PARA_STARTS opens one (the rows' own ``para``), the rest run on;
    [Day 13] or a field in ``starts`` (``PARAGRAPHS``) when it is given."""
    paras = []
    for r in rows:
        opens = r['para']
        if starts is not None:
            opens = r['field'] in starts
        if opens or not paras:
            paras.append([])
        paras[-1].append(r)
    return paras


def row_run(cut, baseline, asc_mm, desc_mm, area, last):
    """[Day 13, §1.3] A row's run along the panel (u0, u1) at ``baseline``: the area's whole length, cut at the zone less
    its gap along when the row's box meets the zone across the panel (within its clearance across); a row past the
    area's far edge keeps ``last``, the run of the last row inside it. With no ``cut``, the area's length (Day 12)."""
    u0, v0, u1, v1 = area
    if cut is None:
        return u0, u1
    top, bottom = baseline - asc_mm, baseline + desc_mm
    if bottom > v1 + 1e-6:
        return last
    zu0, zv0, zu1, zv1 = cut['zone']
    if top < zv1 + cut['across_mm'] and bottom > zv0 - cut['across_mm']:
        return u0, min(u1, zu0 - cut['along_mm'])
    return u0, u1


def lay(rows, area, size_pt, fc, metrics, rtl, cut=None, starts=None):
    """The language's lines in its band's frame: each paragraph wrapped to the copy area's length, the baselines down
    from the area's top (its first at the faces' ascender), a paragraph's gap between paragraphs; a right-to-left
    language set against the area's right end. Every line kept; its overflow past the area said, never hidden.
    [Day 13, §1.3] With ``cut`` (``row_cut``: the band's zone and its clearances) the area is the band's safe area and
    the copy is set in columns inside it: each line is wrapped to its own row's run (``row_run``) — beside a part-width
    zone the run stops short of it, past the zone it is the safe area's whole length — and a right-to-left line set
    against its own run's end. ``starts``: the fields that open a paragraph (the rows' own ``para`` when None)."""
    u0, v0, u1, v1 = area
    asc_mm = max(m['asc_em'] for m in metrics.values()) * size_pt * MM_PER_PT
    desc_mm = max(m['desc_em'] for m in metrics.values()) * size_pt * MM_PER_PT
    pitch_mm = size_pt * MM_PER_PT * LEAD
    out = []
    baseline = v0 + asc_mm
    last = (u0, u1)

    def flush(line, baseline, run, p):
        segs = merge(line)
        width = line_width(segs, size_pt, fc)
        a, b = run
        start = a
        if rtl:
            start = b - width
        box = (start, baseline - asc_mm, start + width, baseline + desc_mm)
        out.append({'segments': segs, 'baseline': baseline, 'start': start, 'width_mm': width, 'box': box,
                    'para': p, 'run': (a, b), 'overflow_mm': max(box[3] - v1, box[2] - b, a - box[0], 0.0)})

    for p, para in enumerate(paragraphs(rows, starts)):
        if p:
            baseline += PARA_GAP * pitch_mm
        line = []
        run = row_run(cut, baseline, asc_mm, desc_mm, area, last)
        for tok in [t for r in para for t in tokens(r)]:
            while run[1] - run[0] <= 0.0:                      # a row with no room is passed over, never drawn on
                baseline += pitch_mm
                run = row_run(cut, baseline, asc_mm, desc_mm, area, last)
            if line and line_width(merge(line + [tok]), size_pt, fc) > run[1] - run[0]:
                flush(line, baseline, run, p)
                if baseline + desc_mm <= v1 + 1e-6:
                    last = run
                baseline += pitch_mm
                run = row_run(cut, baseline, asc_mm, desc_mm, area, last)
                line = [tok]
            else:
                line.append(tok)
        if line:
            flush(line, baseline, run, p)
            if baseline + desc_mm <= v1 + 1e-6:
                last = run
            baseline += pitch_mm
    height = 0.0
    if out:
        height = out[-1]['box'][3] - v0
    return out, height


def need_at_floor(rows, fc):
    """A language's copy at the floor, as the length of line it would take run on in one line (mm)."""
    return sum(line_width(merge(tokens(r)), BODY_FLOOR_PT, fc) for r in rows)


def sizes():
    """The body sizes tried, largest first: 7 pt down to the 5 pt floor in 0.25 pt steps."""
    steps = int(round((BODY_START_PT - BODY_FLOOR_PT) / BODY_STEP_PT))
    return [BODY_START_PT - i * BODY_STEP_PT for i in range(steps + 1)]


def net_measures(product, fc, metrics):
    """The ℮ line: the figures in the medium face at the size whose cap height is the sign's 3 mm, so the sign is
    never larger than its neighbours (D-D11-6); widths in mm. ``neighbour_ink_mm``: each figure's ink above the
    baseline at that size, from the face's own outlines (``text_metrics.ink_extent_em``) — what the sign read back from
    the file is held against (``signs_on_the_back``)."""
    from apps.ire.text_metrics import ink_extent_em
    cap_em = metrics['medium']['cap_em']
    size_pt = SIGN_MM / MM_PER_PT / cap_em
    left, right = product['net']
    gap = ps.width_mm(' ', fc['medium'], size_pt)
    lw = ps.width_mm(left, fc['medium'], size_pt)
    rw = ps.width_mm(right, fc['medium'], size_pt)
    _, sign = lm.sign_segments((0.0, 0.0, 1.0, SIGN_MM))
    neighbours = {}
    for text in (left, right):
        ink = ink_extent_em(text, str(fc['medium']['path']))
        if ink is None:
            raise ValueError('the ℮ line\'s %r has no ink to measure in %s' % (text, fc['medium']['path']))
        neighbours[text] = ink[0] * size_pt * MM_PER_PT
    return {'size_pt': size_pt, 'gap': gap, 'left': lw, 'right': rw, 'sign_w': sign['width_mm'],
            'total': lw + gap + sign['width_mm'] + gap + rw,
            'cap_mm': metrics['medium']['cap_em'] * size_pt * MM_PER_PT, 'sign_mm': SIGN_MM,
            'neighbour_ink_mm': neighbours,
            'asc_mm': metrics['medium']['asc_em'] * size_pt * MM_PER_PT,
            'desc_mm': metrics['medium']['desc_em'] * size_pt * MM_PER_PT}


def foot_length(product, fc, metrics):
    """The back's foot along the panel: the ℮ line, or a field's label, gap and box, whichever is longer."""
    net = net_measures(product, fc, metrics)
    labels = max(ps.width_mm(word, fc['medium'], FIELD_PT) for word, _ in FIELDS)
    return max(net['total'], labels + FIELD_LABEL_GAP_MM + FIELD_BOX_MM[0])


def fields_measures(fc):
    """[Day 13] The write-in fields standing alone: their length along the panel (a label, its gap, its box) and their
    width across it (each field one box tall, FIELD_GAP_MM between them)."""
    labels = max(ps.width_mm(word, fc['medium'], FIELD_PT) for word, _ in FIELDS)
    return (labels + FIELD_LABEL_GAP_MM + FIELD_BOX_MM[0],
            len(FIELDS) * FIELD_BOX_MM[1] + (len(FIELDS) - 1) * FIELD_GAP_MM)


COPY_PANELS = ('back', 'side_left', 'side_right')
EAN_PANELS = ('side_right', 'side_left')       # the EAN on a long side (D-D11-7); the right side preferred on a tie


def bands_for(fc_box, assign, ean_panel, product, fc, metrics, fields_at=FIELDS_AT[0], paragraphs_as='as_set',
              clear_lines=FOOT_CLEAR_LINES):
    """The three copy bands for one assignment of languages to panels: the back's foot (the ℮ line and the write-in
    fields) and the EAN frame each at its band's far end (the panel's top). Each band in its own frame: its length the
    panel's height, its width the panel's; its safe area, its zone and the copy area left.
    [Day 13] Each band carries its one zone (its box in the band's frame, its kind, its clearances: ZONE_GAP_MM along,
    plus FOOT_CLEAR_LINES of the size set for the ℮ line and the fields; ZONE_ACROSS_MM across) and the copy is laid
    round it (``lay``). ``fields_at``: 'under_net' — Day 12's foot, the fields under the ℮ line on the back, the whole
    safe width — or 'side_near' / 'side_far': the fields at the far end of the long side without the EAN, on its first
    rows or its last, the ℮ line then standing alone on the back (part width). ``paragraphs_as``: a PARAGRAPHS key.
    ``clear_lines``: the foot's clearance lines (0 sets Day 12's 3 mm, for ``day12_choice``). ``area``: the copy area
    beside the zone at the floor (the rows past a part-width zone run longer: ``band_rows``)."""
    if fields_at not in FIELDS_AT or paragraphs_as not in PARAGRAPHS:
        raise ValueError('no layout %r / %r: the fields stand %s, the paragraphs %s' % (
            fields_at, paragraphs_as, FIELDS_AT, tuple(PARAGRAPHS)))
    fields_side = [p for p in COPY_PANELS[1:] if p != ean_panel][0]
    out = {}
    for panel, lang in zip(COPY_PANELS, assign):
        x0, y0, x1, y1 = fc_box[panel]['box']
        length, across = y1 - y0, x1 - x0
        safe = (SAFE_MM, SAFE_MM, length - SAFE_MM, across - SAFE_MM)
        zone, kind, clear = None, None, 0
        if panel == 'back' and fields_at == 'under_net':
            kind, clear = 'foot', clear_lines
            zone = (safe[2] - foot_length(product, fc, metrics), safe[1], safe[2], safe[3])
        elif panel == 'back':
            kind, clear = 'net', clear_lines
            net = net_measures(product, fc, metrics)
            zone = (safe[2] - net['total'], safe[1], safe[2], safe[1] + net['asc_mm'] + net['desc_mm'])
        elif panel == ean_panel:
            kind = 'ean'
            zone = (safe[2] - EAN_MM[0], safe[1], safe[2], safe[3])
        elif panel == fields_side and fields_at != 'under_net':
            kind, clear = 'fields', clear_lines
            f_len, f_across = fields_measures(fc)
            top = safe[1]
            if fields_at == 'side_far':
                top = safe[3] - f_across
            zone = (safe[2] - f_len, top, safe[2], top + f_across)
        paras = paragraphs_as
        if lang == 'ar':
            paras = 'as_set'                     # a right-to-left line never runs the INCI on (PARAGRAPHS)
        band = {'panel': panel, 'lang': lang, 'length_mm': length, 'across_mm': across, 'safe': safe,
                'zone': zone, 'zone_kind': kind, 'zone_gap_mm': ZONE_GAP_MM, 'zone_clear_lines': clear,
                'zone_across_mm': ZONE_ACROSS_MM, 'rtl': lang == 'ar', 'fields_at': fields_at,
                'paragraphs': paras, 'starts': PARAGRAPHS[paras]}
        band['area'] = copy_area(band, BODY_FLOOR_PT)
        out[panel] = band
    return out


def pitch_at(size_pt):
    """One line's pitch at ``size_pt`` (mm)."""
    return size_pt * MM_PER_PT * LEAD


def row_cut(band, size_pt):
    """[Day 13] A band's zone as ``lay`` cuts its rows at ``size_pt``: the zone, its gap along the panel (ZONE_GAP_MM
    plus its clearance lines at the size set) and its clearance across; None for a band with no zone (or none said)."""
    if 'zone' not in band or band['zone'] is None:
        return None
    return {'zone': band['zone'], 'along_mm': band['zone_gap_mm'] + band['zone_clear_lines'] * pitch_at(size_pt),
            'across_mm': band['zone_across_mm']}


def copy_area(band, size_pt):
    """The copy area beside the band's zone at ``size_pt`` (the safe area less the zone and its gap along; the whole
    safe area with no zone) — Day 12's copy area. Past a part-width zone the rows run longer (``band_rows``)."""
    cut = row_cut(band, size_pt)
    if cut is None:
        return band['safe']
    s = band['safe']
    return (s[0], s[1], cut['zone'][0] - cut['along_mm'], s[3])


def band_area(band):
    """The rectangle ``lay`` sets a band in: its safe area when it carries a zone (the zone cuts the rows), else its
    copy area (a band given by its area alone, as the fit's controls give one)."""
    if 'zone' in band and band['zone'] is not None:
        return band['safe']
    return band['area']


def lay_band(blocks, band, size_pt, fc, metrics):
    """A band's language laid at ``size_pt``: round its zone, in its paragraphs (``lay``)."""
    starts = None
    if 'starts' in band:
        starts = band['starts']
    return lay(blocks[band['lang']], band_area(band), size_pt, fc, metrics, band['rtl'], cut=row_cut(band, size_pt),
               starts=starts)


def band_rows(band, size_pt, metrics):
    """[Day 13] The band's rows inside its safe area at ``size_pt``: each row's box across the panel and its run along
    it (``row_run``) — the rows the copy can take without leaving the safe area."""
    asc_mm = max(m['asc_em'] for m in metrics.values()) * size_pt * MM_PER_PT
    desc_mm = max(m['desc_em'] for m in metrics.values()) * size_pt * MM_PER_PT
    area = band_area(band)
    cut = row_cut(band, size_pt)
    rows = []
    baseline = area[1] + asc_mm
    while baseline + desc_mm <= area[3] + 1e-6:
        a, b = row_run(cut, baseline, asc_mm, desc_mm, area, (area[0], area[2]))
        rows.append({'v_mm': [baseline - asc_mm, baseline + desc_mm], 'run_mm': [a, b]})
        baseline += pitch_at(size_pt)
    return rows


def columns(rows):
    """[Day 13] The rows grouped into the columns they make inside the safe area: consecutive rows of one run, each
    column's box in the band's frame (mm)."""
    out = []
    for r in rows:
        if out and out[-1]['run_mm'] == r['run_mm']:
            out[-1]['rows'] += 1
            out[-1]['box_mm'][3] = r['v_mm'][1]
        else:
            out.append({'rows': 1, 'run_mm': list(r['run_mm']),
                        'box_mm': [r['run_mm'][0], r['v_mm'][0], r['run_mm'][1], r['v_mm'][1]]})
    return [{'rows': c['rows'], 'length_mm': round(c['run_mm'][1] - c['run_mm'][0], 3),
             'box_mm': [round(v, 3) for v in c['box_mm']]} for c in out]


def day12_choice(fc_box, blocks, fc, product, metrics):
    """[Day 13] Day 12's own choice of panels for this copy, re-measured: the twelve ways set with Day 12's foot (the
    fields under the ℮ line, the copy 3 mm clear of it) and its paragraphs, ranked by Day 12's rule (the largest size
    that fits, the fewest lines past a cut edge, the fewest over; the house's order on a tie). Returns (assign,
    ean_panel) — what ``plan`` counts as no change."""
    import itertools
    best, best_rank = None, None
    for assign in itertools.permutations(LANGS):
        for ean_panel in EAN_PANELS:
            bands = bands_for(fc_box, assign, ean_panel, product, fc, metrics, FIELDS_AT[0], 'as_set', 0)
            size_pt, laid, fits = fit(blocks, bands, fc, metrics)
            r = (fits, size_pt, -lines_past_the_trim(laid, fc_box),
                 -sum(1 for lines, _ in laid.values() for ln in lines if ln['overflow_mm'] > 1e-6))
            if best_rank is None or r > best_rank:
                best, best_rank = (dict(zip(COPY_PANELS, assign)), ean_panel), r
    return best


def plan(fc_box, blocks, fc, product, metrics):
    """Which panel carries which language, measured: every assignment of EN / ES / AR to the back and the two long
    sides, with the EAN frame on either side, set by ``fit``; the one whose copy fits at the largest size wins, then
    the one with the fewest lines run past a cut edge (an overflow off the right side's free edge is cut off in print;
    one across a crease at least stays on the carton), then the fewest lines over — on a tie the first in the house's
    order (English on the back, Spanish on the left side, Arabic on the right, the EAN on the right side). Returns the
    bands, the size, the lines, whether they fit, and every option measured.
    [Day 13, §1.3] On panels under NARROW_PANEL_MM (both sticks') each of the twelve is also set with the write-in
    fields at the far end of the long side without the EAN (on its first rows or its last; the ℮ line then alone on the
    back, the copy running past it) and with the INCI run on after the description: 72 ways. After the lines past a cut
    edge, the fewest lines that leave their panel (across a crease or onto another face) win; after the lines over, the
    fewest changes from Day 12's layout — its paragraphs, its foot, and Day 12's own choice of panels for this copy
    (``day12_choice``) — so a carton keeps what Day 12 gave it wherever the rule allows."""
    import itertools
    narrow = all(fc_box[p]['box'][2] - fc_box[p]['box'][0] < NARROW_PANEL_MM for p in COPY_PANELS)
    places, modes = FIELDS_AT[:1], ('as_set',)
    if narrow:
        places, modes = FIELDS_AT, tuple(PARAGRAPHS)
    kept = day12_choice(fc_box, blocks, fc, product, metrics)
    options = []
    for mode in modes:
        for place in places:
            for assign in itertools.permutations(LANGS):
                for ean_panel in EAN_PANELS:
                    bands = bands_for(fc_box, assign, ean_panel, product, fc, metrics, place, mode)
                    size_pt, laid, fits = fit(blocks, bands, fc, metrics)
                    options.append({'assign': dict(zip(COPY_PANELS, assign)), 'ean_panel': ean_panel,
                                    'fields_at': place, 'paragraphs': mode, 'size_pt': size_pt,
                                    'fits': fits, 'bands': bands, 'laid': laid,
                                    'past_trim_lines': lines_past_the_trim(laid, fc_box),
                                    'crossing_lines': lines_off_their_panel(laid, fc_box),
                                    'overflow_lines': sum(1 for lines, _ in laid.values() for ln in lines
                                                          if ln['overflow_mm'] > 1e-6),
                                    'changes': int(mode != modes[0]) + int(place != places[0])
                                    + int((dict(zip(COPY_PANELS, assign)), ean_panel) != kept)})

    def rank(o):
        return o['fits'], o['size_pt'], -o['past_trim_lines'], -o['crossing_lines'], -o['overflow_lines'], -o['changes']
    best = options[0]
    for o in options[1:]:
        if rank(o) > rank(best):
            best = o
    said = [{'assign': o['assign'], 'ean_panel': o['ean_panel'], 'fields_at': o['fields_at'],
             'paragraphs': o['paragraphs'], 'size_pt': o['size_pt'], 'fits': o['fits'],
             'past_trim_lines': o['past_trim_lines'], 'crossing_lines': o['crossing_lines'],
             'overflow_lines': o['overflow_lines'], 'changes': o['changes']} for o in options]
    best = dict(best, day12_choice={'assign': kept[0], 'ean_panel': kept[1]})
    return best, said


def past_cut_mm(box, face):
    """How far a flat box runs past its face's cut edges (mm; 0.0 when it stays inside them): what the knife takes."""
    x0, y0, x1, y1 = face['box']
    past = {'left': x0 - box[0], 'top': y0 - box[1], 'right': box[2] - x1, 'bottom': box[3] - y1}
    return max([0.0] + [past[side] for side in face['cut']])


def lines_past_the_trim(laid, fc_box):
    """How many laid lines run past their panel's cut edge on the flat (part of them cut off in print)."""
    return sum(1 for panel, (lines, _) in laid.items() for ln in lines
               if past_cut_mm(flat_box(ln['box'], fc_box[panel]['box']), fc_box[panel]) > 1e-6)


def lines_off_their_panel(laid, fc_box):
    """[Day 13] How many laid lines leave their panel on the flat: across a crease, or wholly onto another face (a line
    in its own margin, past the safe area but inside the panel, stays)."""
    return sum(1 for panel, (lines, _) in laid.items() for ln in lines
               if not pb._inside(flat_box(ln['box'], fc_box[panel]['box']), fc_box[panel]['box']))


def fit(blocks, bands, fc, metrics):
    """The one body size: the largest from 7 pt down in 0.25 pt steps at which every panel's lines fit its copy area;
    the floor when none does (fits False — every line still drawn, its overflow said). [Day 13] Each band laid round
    its zone (``lay_band``)."""
    for size_pt in sizes():
        laid = {p: lay_band(blocks, b, size_pt, fc, metrics) for p, b in bands.items()}
        if all(not any(line['overflow_mm'] > 1e-6 for line in lines) for lines, _ in laid.values()):
            return size_pt, laid, True
    laid = {p: lay_band(blocks, b, BODY_FLOOR_PT, fc, metrics) for p, b in bands.items()}
    return BODY_FLOOR_PT, laid, False


def capacity_at_floor(blocks, bands, fc, metrics):
    """Each language's room at the 5 pt floor against its need: lines and line-millimetres. [Day 13] The room is the
    band's rows inside its safe area (``band_rows``: beside a part-width zone a row's run is shorter than past it) and
    the columns they make; ``area_mm`` the copy area beside the zone."""
    out = {}
    for panel, b in bands.items():
        rows = band_rows(b, BODY_FLOOR_PT, metrics)
        u0, v0, u1, v1 = copy_area(b, BODY_FLOOR_PT)
        lines, height = lay_band(blocks, b, BODY_FLOOR_PT, fc, metrics)
        out[b['lang']] = {'panel': panel, 'area_mm': [round(u1 - u0, 2), round(v1 - v0, 2)],
                          'lines_room': len(rows), 'lines_needed': len(lines),
                          'line_mm_room': round(sum(r['run_mm'][1] - r['run_mm'][0] for r in rows), 1),
                          'line_mm_needed': round(sum(line['width_mm'] for line in lines), 1),
                          'height_needed_mm': round(height, 2),
                          'holds': not any(line['overflow_mm'] > 1e-6 for line in lines),
                          'columns': columns(rows)}
    return out


# --- the engine document -----------------------------------------------------------------------------------------------

def poly_segments(geom):
    """A shapely polygon (or its parts) as engine path segments, every ring closed (filled even-odd)."""
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = []
    for part in lm.parts(geom):
        for ring in [part.exterior, *part.interiors]:
            pts = list(ring.coords)
            segs.append(MoveTo(x=float(pts[0][0]), y=float(pts[0][1])))
            segs += [LineTo(x=float(x), y=float(y)) for x, y in pts[1:]]
            segs.append(ClosePath())
    return segs


def band_nodes(band, lines, size_pt, fc, colour):
    """A copy band's lines as TextRuns in its own frame, each segment its own run named '<lang>:<field>'."""
    from apps.ire.graph import TextRun
    nodes = []
    lang = band['lang']
    for line in lines:
        segs = line['segments']
        if band['rtl']:
            x = line['start'] + line['width_mm']
            for field, face, text in segs:
                nodes.append(TextRun(name='%s:%s' % (lang, field), text=text, x=x, y=line['baseline'],
                                     font=fc[face]['role'], size_pt=size_pt, color=colour, align='right',
                                     rtl=face == 'arabic'))
                x -= ps.width_mm(text, fc[face], size_pt) + ps.width_mm(' ', fc[face], size_pt)
        else:
            x = line['start']
            for field, face, text in segs:
                nodes.append(TextRun(name='%s:%s' % (lang, field), text=text, x=x, y=line['baseline'],
                                     font=fc[face]['role'], size_pt=size_pt, color=colour))
                x += ps.width_mm(text, fc[face], size_pt) + ps.width_mm(' ', fc[face], size_pt)
    return nodes


def net_nodes(product, zone, fc, metrics, colour):
    """The ℮ line in its band's frame, at its zone's start and top: its figures and the house's sign, at the figures'
    cap height. Returns nodes, their box and the line's measures."""
    from apps.ire.graph import Group, Path, SolidFill, TextRun
    u0, v0, u1, v1 = zone
    net = net_measures(product, fc, metrics)
    baseline = v0 + net['asc_mm']
    left, right = product['net']
    sx0 = u0 + net['left'] + net['gap']
    segs, _ = lm.sign_segments((sx0, baseline - SIGN_MM, sx0 + net['sign_w'], baseline))
    nodes = [TextRun(name='net:a', text=left, x=u0, y=baseline, font=fc['medium']['role'], size_pt=net['size_pt'],
                     color=colour),
             Group(name='net:sign', actual_text=lm.SIGN, children=[Path(name=lm.SIGN, segments=segs,
                                                                         fill=SolidFill(color=colour),
                                                                         fill_rule='nonzero')]),
             TextRun(name='net:b', text=right, x=sx0 + net['sign_w'] + net['gap'], y=baseline,
                     font=fc['medium']['role'], size_pt=net['size_pt'], color=colour)]
    boxes = {'net': (u0, baseline - net['asc_mm'], u0 + net['total'], baseline + net['desc_mm'])}
    return nodes, boxes, net


def field_nodes(u0, top, fc, colour):
    """The batch and expiry write-in fields in a band's frame, from ``u0`` along and ``top`` across: a label and an
    empty box each, FIELD_GAP_MM between them. Returns nodes and their boxes."""
    from apps.ire.graph import Rect, Stroke, TextRun
    nodes, boxes = [], {}
    label_w = max(ps.width_mm(word, fc['medium'], FIELD_PT) for word, _ in FIELDS)
    bx = u0 + label_w + FIELD_LABEL_GAP_MM
    for word, key in FIELDS:
        bottom = top + FIELD_BOX_MM[1]
        nodes.append(TextRun(name='field:%s' % key, text=word, x=u0, y=bottom - FIELD_LABEL_LIFT_MM,
                             font=fc['medium']['role'], size_pt=FIELD_PT, color=colour))
        nodes.append(Rect(name='field:%s box (write-in)' % key, x=bx, y=top, w=FIELD_BOX_MM[0], h=FIELD_BOX_MM[1],
                          stroke=Stroke(color=colour, width_mm=FIELD_STROKE_MM)))
        boxes['field:%s' % key] = (u0, top, bx + FIELD_BOX_MM[0], bottom)
        top = bottom + FIELD_GAP_MM
    return nodes, boxes


def foot_nodes(product, zone, fc, metrics, colour):
    """The back's foot in its band's frame: the ℮ line (its sign the house's, at the figures' cap height) and the
    batch and expiry write-in fields (a label and an empty box each). Returns nodes and their boxes. [Day 13] The two
    parts drawn by ``net_nodes`` and ``field_nodes``, the fields FIELD_GAP_MM under the ℮ line, as on Day 12."""
    nodes, boxes, net = net_nodes(product, zone, fc, metrics, colour)
    more, fields = field_nodes(zone[0], boxes['net'][3] + FIELD_GAP_MM, fc, colour)
    boxes.update(fields)
    return nodes + more, boxes, net


def ean_nodes(zone, fc, colours):
    """The EAN-13's placeholder frame in its band's frame (no number, none invented): 29.83 mm along the panel — the
    symbol's width at 80 %, its quiet zones inside — by the safe width across it, so on the standing carton its bars
    would run across the panel (ladder orientation) and their height is cut from 20.74 mm to the safe width. White
    inside: a symbol prints dark bars on a light ground."""
    from apps.ire.graph import Color, Rect, SolidFill, Stroke, TextRun
    u0, v0, u1, v1 = zone
    edge = Color.from_hex(colours['ground'])
    frame = Rect(name='EAN-13 placeholder frame (no number; ladder; truncated — owner to confirm)', x=u0, y=v0,
                 w=u1 - u0, h=v1 - v0, fill=SolidFill(color=Color.from_hex(colours['ean_ground'])),
                 stroke=Stroke(color=edge, width_mm=EAN_STROKE_MM))
    label = TextRun(name='ean:label', text='EAN-13', x=(u0 + u1) / 2, y=(v0 + v1) / 2 + EAN_PT * MM_PER_PT / 3,
                    font=fc['regular']['role'], size_pt=EAN_PT, color=edge, align='center')
    return [frame, label]


def logo_aspect():
    """The approved master's ink height over its width."""
    from apps.ire import brand_mark
    master = brand_mark.read_master(lm.LOGO_SVG.read_bytes(), path=str(lm.LOGO_SVG))
    x0, y0, x1, y1 = master.bounds
    return (y1 - y0) / (x1 - x0)


def end_nodes(face, colour, turned):
    """An end's logo: the approved vector (``lid_master.logo_parts``, refused unless it is the master) centred in the
    lid, 12 mm wide, in ink; the top end's turned 180° about the lid's centre so it reads from the front."""
    from apps.ire.graph import Group
    x0, y0, x1, y1 = face['box']
    h = END_LOGO_W_MM * logo_aspect()
    lx, ly = (x0 + x1 - END_LOGO_W_MM) / 2, (y0 + y1 - h) / 2
    turn = None
    if turned:
        turn = (-1.0, 0.0, 0.0, -1.0, x0 + x1, y0 + y1)
    group = Group(name='LOGO', role='logo', turn=turn,
                  children=lm.logo_parts((lx, ly, END_LOGO_W_MM, h), colour, foil_letters=False))
    return group, (lx, ly, lx + END_LOGO_W_MM, ly + h)


def front_nodes(face, ground_geom, picture, nodes, colours):
    """The front: the indigo ground, then the picture passed in (scaled to cover the front's ground box, centred, cut
    to the ground) and the engine nodes passed in (their frame the panel's own, moved onto the flat). With neither,
    the ground alone — the placeholder, named so."""
    from apps.ire.graph import Color, Group, Image, Path as GPath, SolidFill
    from PIL import Image as PILImage
    placeholder = picture is None and nodes is None
    name = 'front ground'
    if placeholder:
        name = 'front: placeholder ground (no art passed)'
    out = [GPath(name=name, segments=poly_segments(ground_geom),
                 fill=SolidFill(color=Color.from_hex(colours['ground'])), fill_rule='evenodd')]
    record = {'placeholder': placeholder, 'ground': colours['ground'], 'picture': None, 'nodes': None}
    if placeholder:
        record['said'] = ('a flat indigo ground (%s) stands in for the front until the lead passes the stones and the '
                          'hero (D-D11-7): a placeholder, not the design' % colours['ground'])
    if picture is not None:
        gx0, gy0, gx1, gy1 = face['ground']
        with PILImage.open(str(picture)) as im:
            px_w, px_h = im.size
        k = max((gx1 - gx0) / px_w, (gy1 - gy0) / px_h)          # mm per pixel: the picture covers the ground
        w, h = px_w * k, px_h * k
        x, y = (gx0 + gx1 - w) / 2, (gy0 + gy1 - h) / 2
        out.append(Image(name='front picture', src=str(Path(picture).resolve()), x=x, y=y, w=w, h=h,
                         clip=poly_segments(ground_geom)))
        record['picture'] = {'path': str(picture), 'sha256': hashlib.sha256(Path(picture).read_bytes()).hexdigest(),
                             'pixels': [px_w, px_h], 'placed_mm': [round(v, 3) for v in (x, y, x + w, y + h)],
                             'ppi': round(25.4 / k, 1), 'ppi_holds': 25.4 / k >= lm.PRINT_PPI_MIN,
                             'cut_to': 'the front\'s ground (its bleed at the top and bottom cuts, 0.5 mm past its '
                                       'creases)',
                             'content_checked': False,
                             'said': 'a raster covering the front to its bleed: what it shows (a hero, a logotype) is '
                                     'NOT checked against the safe area or the thumb notch\'s keep-out — pass them as '
                                     'nodes to have them measured'}
    if nodes is not None:
        out.append(Group(name='FRONT ART', turn=front_turn(face), children=list(nodes)))
        record['nodes'] = {'count': len(nodes), 'frame': 'the front panel\'s own mm, origin at its top-left, upright',
                           'checked': 'each node\'s box read from its own emitted file (engine/front-node-<n>.ai), '
                                      'inside the front\'s safe area less the notch\'s keep-out, across no crease'}
    return out, record


def front_turn(face):
    """The front art's turn: the front panel's own frame (origin its top-left, upright) moved onto the flat."""
    return (1.0, 0.0, 0.0, 1.0, face['box'][0], face['box'][1])


def front_elements(folder, face, nodes, page_mm):
    """Each front node's box on the flat, read from the file: the node emitted alone (``folder``/front-node-<n>.ai,
    kept) under the carton's and the front's turns on the flat's page, its box the union of what it draws — page 1's
    paths (a stroke's half width included), text spans and images, and its plates' paths (a blind finish draws only
    there; a plate page's own text is the emitter's plate label, not the node). A node that draws nothing is refused.
    Returns layout elements (panel 'front', the flat box)."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    k = lm.MM_PER_INCH / 72.0
    out = []
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for i, node in enumerate(nodes):
        doc = Document(page_w=page_mm[0], page_h=page_mm[1], title='front node %d' % (i + 1),
                       metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                       root=Group(name='CARTON', role='artwork', turn=(1.0, 0.0, 0.0, 1.0, BLEED_MM, BLEED_MM),
                                  children=[Group(name='FRONT ART', turn=front_turn(face), children=[node])]))
        path = folder / ('front-node-%d.ai' % (i + 1))
        emit_pdf_ai(doc, str(path))
        rects = []
        with fitz.open(str(path)) as d:
            for number, page in enumerate(d):
                for dr in page.get_drawings():
                    grow = 0.0
                    if dr['type'] in ('s', 'fs') and dr['width'] is not None:
                        grow = dr['width'] / 2
                    r = dr['rect']
                    rects.append((r.x0 - grow, r.y0 - grow, r.x1 + grow, r.y1 + grow))
                if number:
                    continue
                for b in page.get_text('dict')['blocks']:
                    if 'lines' not in b:
                        continue
                    rects += [tuple(sp['bbox']) for ln in b['lines'] for sp in ln['spans'] if sp['text'].strip()]
                rects += [tuple(im['bbox']) for im in page.get_image_info()]
        if not rects:
            raise ValueError('front node %d (%r) draws nothing in %s' % (i + 1, node.name, path))
        box = tuple(v * k - BLEED_MM for v in (min(r[0] for r in rects), min(r[1] for r in rects),
                                                max(r[2] for r in rects), max(r[3] for r in rects)))
        out.append({'panel': 'front', 'element': 'front node %d (%s)' % (i + 1, node.name), 'flat': box,
                    'read_from': str(path)})
    return out


def drawn_names(doc):
    """The names of the nodes that write an ActualText span, in drawing order (each TextRun, and each group that
    names its words: the ℮)."""
    from apps.ire.graph import Group, TextRun
    return [n.name for n, _ in doc.walk() if isinstance(n, TextRun) or (isinstance(n, Group) and n.actual_text)]


def document(product, coords, fc_box, blocks, colours, picture, nodes, fc, metrics):
    """The flat as one engine document (page = the flat plus its 3 mm bleed; the flat's own mm moved onto it): every
    face's ground, the front's art, the three copy bands turned onto their panels, the back's foot, the EAN frame, the
    ends' logos. Returns the document and the layout's record."""
    from apps.ire.graph import Color, Document, Group, Path, SolidFill
    bare = pb.non_printing(coords)
    grounds = {name: pb.ground_shape(fc_box[name], bare) for name in fc_box}
    ground = Color.from_hex(colours['ground'])
    ink = Color.from_hex(colours['ink'])
    children = [Path(name='ground: %s' % name, segments=poly_segments(grounds[name]), fill=SolidFill(color=ground),
                     fill_rule='evenodd') for name in ('back', 'side_left', 'side_right', 'top_end', 'bottom_end')]
    front, front_record = front_nodes(fc_box['front'], grounds['front'], picture, nodes, colours)
    children += front
    need = {lang: need_at_floor(blocks[lang], fc) for lang in LANGS}
    best, options = plan(fc_box, blocks, fc, product, metrics)
    bands, size_pt, laid, fits = best['bands'], best['size_pt'], best['laid'], best['fits']
    elements = []
    foot_record = None
    for panel, band in bands.items():
        lines, height = laid[panel]
        kids = band_nodes(band, lines, size_pt, fc, ink)
        if band['zone_kind'] in ('foot', 'net', 'fields'):          # [Day 13] the foot whole, or its two parts apart
            if band['zone_kind'] == 'foot':
                extra, boxes, foot_record = foot_nodes(product, band['zone'], fc, metrics, ink)
            elif band['zone_kind'] == 'net':
                extra, boxes, foot_record = net_nodes(product, band['zone'], fc, metrics, ink)
            else:
                extra, boxes = field_nodes(band['zone'][0], band['zone'][1], fc, ink)
            kids += extra
            for key, box in boxes.items():
                elements.append({'panel': panel, 'element': key, 'local': box})
        elif band['zone_kind'] == 'ean':
            kids += ean_nodes(band['zone'], fc, colours)
            elements.append({'panel': panel, 'element': 'EAN-13 frame', 'local': band['zone']})
        for i, line in enumerate(lines):
            elements.append({'panel': panel, 'element': '%s line %d' % (band['lang'], i + 1), 'local': line['box']})
        children.append(Group(name='COPY %s (%s)' % (panel, band['lang']), role='info', turn=band_turn(fc_box[panel]['box']),
                              children=kids))
    for end, turned in (('top_end', True), ('bottom_end', False)):
        group, box = end_nodes(fc_box[end], colours['logo'], turned)
        children.append(group)
        elements.append({'panel': end, 'element': 'the logo', 'flat': box})
    for e in elements:
        if 'local' in e:
            e['flat'] = flat_box(e['local'], fc_box[e['panel']]['box'])
    W = coords.cut_polygon.bounds[2] + 2 * BLEED_MM
    H = coords.cut_polygon.bounds[3] + 2 * BLEED_MM
    doc = Document(page_w=W, page_h=H, title='%s carton (straight tuck end)' % product['name'],
                   metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                   root=Group(name='CARTON', role='artwork', turn=(1.0, 0.0, 0.0, 1.0, BLEED_MM, BLEED_MM),
                              children=children))
    layout = {'bands': bands, 'need_at_floor_mm': need, 'options': options, 'size_pt': size_pt, 'laid': laid,
              'fits': fits, 'elements': elements, 'front': front_record, 'foot': foot_record, 'bare': bare,
              'grounds': grounds, 'faces': fc_box, 'page_mm': (W, H),
              'chosen': {k: best[k] for k in ('assign', 'ean_panel', 'fields_at', 'paragraphs', 'size_pt', 'fits',
                                              'past_trim_lines', 'crossing_lines', 'overflow_lines', 'changes',
                                              'day12_choice')}}
    return doc, layout


# --- the files ---------------------------------------------------------------------------------------------------------

def _rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def draw_die(page, coords, px0, py0, oc_cut, oc_crease):
    """The die exactly as the engine gives it: the cut outline and the lock slits (magenta), the creases (cyan,
    dashed), each segment drawn from the engine's own coordinates."""
    import fitz

    def P(x, y):
        return fitz.Point(lm.pt(x - px0), lm.pt(y - py0))
    poly = coords.cut_polygon
    for ring in [poly.exterior] + list(poly.interiors):
        page.draw_polyline([P(x, y) for x, y in ring.coords], color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
    for x1, y1, x2, y2 in coords.slit_lines:
        page.draw_line(P(x1, y1), P(x2, y2), color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
    for x1, y1, x2, y2 in coords.fold_lines:
        page.draw_line(P(x1, y1), P(x2, y2), color=(0, 0.6, 0.9), width=0.4, dashes='[3 1.6] 0', oc=oc_crease)


def die_segments(coords):
    """Every cut, slit and crease segment the engine gives (mm)."""
    want = [tuple(f) for f in coords.fold_lines] + [tuple(s) for s in coords.slit_lines]
    ring = list(coords.cut_polygon.exterior.coords)
    want += [(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1]) for i in range(len(ring) - 1)]
    return want


def die_readback(pdf_path, coords, px0, py0):
    """The die as written: every segment the engine gives found among page 1's drawn lines within 0.01 mm (either
    direction)."""
    import fitz
    k = lm.MM_PER_INCH / 72.0
    drawn = []
    with fitz.open(str(pdf_path)) as d:
        for dr in d[0].get_drawings():
            for item in dr['items']:
                if item[0] == 'l':
                    a, b = item[1], item[2]
                    drawn.append((a.x * k + px0, a.y * k + py0, b.x * k + px0, b.y * k + py0))

    def found(seg):
        for e in drawn:
            if (max(abs(seg[0] - e[0]), abs(seg[1] - e[1]), abs(seg[2] - e[2]), abs(seg[3] - e[3])) <= DIE_TOL_MM
                    or max(abs(seg[0] - e[2]), abs(seg[1] - e[3]), abs(seg[2] - e[0]), abs(seg[3] - e[1])) <= DIE_TOL_MM):
                return True
        return False
    want = die_segments(coords)
    missing = [w for w in want if not found(w)]
    return {'segments': len(want), 'missing_or_moved': len(missing), 'missing': [[round(v, 3) for v in m] for m in missing],
            'tolerance_mm': DIE_TOL_MM, 'holds': not missing}


def plate_pages(usage):
    """The engine's plate pages by kind: foil (and metallic ink) for page 2, relief (emboss, deboss) for page 3."""
    from apps.ire.container_finishes import SCHEMA as FP
    plates = usage[FP]['plates']
    foil = [p for p in plates if p['kind'] in ('foil', 'metallic_ink')]
    relief = [p for p in plates if p['kind'] in ('emboss', 'deboss')]
    return foil, relief


def plate_names(plates):
    """A page label's plates, or 'none' (the placeholder front carries no finish; none is synthesised)."""
    if not plates:
        return 'none'
    return ', '.join(x['plate'] for x in plates)


def write_artwork(out, engine_ai, coords, fc_box, usage, product, *, render_preview=True):
    """carton-artwork.pdf (page 1 the artwork on the die, its cut and crease on locked layers; page 2 the foil plate;
    page 3 the relief plate — each 'none' when the front carries none) and carton-artwork.ai (layers: artwork, foil,
    relief, cut, crease, guides; the die locked)."""
    import fitz
    px0 = py0 = -BLEED_MM
    W = coords.cut_polygon.bounds[2] + 2 * BLEED_MM
    H = coords.cut_polygon.bounds[3] + 2 * BLEED_MM
    trim = fitz.Rect(lm.pt(BLEED_MM), lm.pt(BLEED_MM), lm.pt(W - BLEED_MM), lm.pt(H - BLEED_MM))
    foil, relief = plate_pages(usage)
    src = fitz.open(str(engine_ai))
    full = fitz.Rect(0, 0, lm.pt(W), lm.pt(H))

    pdf = fitz.open()
    layers = {name: pdf.add_ocg(name, on=True) for name in ('artwork', 'cut', 'crease')}
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    p.show_pdf_page(full, src, 0, oc=layers['artwork'])
    draw_die(p, coords, px0, py0, layers['cut'], layers['crease'])
    for group in (foil, relief):
        p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
        for plate in group:
            p.show_pdf_page(full, src, plate['page'] - 1)
    pdf.set_layer(-1, locked=[layers['cut'], layers['crease']])
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 artwork on the die ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 foil plate - %s ' % plate_names(foil), 'style': ''},
                         {'startpage': 2, 'prefix': '3 relief plate - %s ' % plate_names(relief), 'style': ''}])
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(trim)
    pdf.set_metadata({'title': '%s carton on our straight tuck end (%s)' % (product['name'], TEMPLATE_VERSION),
                      'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'carton-artwork.pdf'), garbage=3, deflate=True)
    pdf.close()

    ai = fitz.open()
    layers = {name: ai.add_ocg(name, on=name not in ('foil', 'relief'))
              for name in ('artwork', 'foil', 'relief', 'cut', 'crease', 'guides')}
    p = ai.new_page(width=lm.pt(W), height=lm.pt(H))
    p.show_pdf_page(full, src, 0, oc=layers['artwork'])
    for plate in foil:
        p.show_pdf_page(full, src, plate['page'] - 1, oc=layers['foil'])
    for plate in relief:
        p.show_pdf_page(full, src, plate['page'] - 1, oc=layers['relief'])
    draw_die(p, coords, px0, py0, layers['cut'], layers['crease'])

    def R(box):
        x0, y0, x1, y1 = box
        return fitz.Rect(lm.pt(x0 - px0), lm.pt(y0 - py0), lm.pt(x1 - px0), lm.pt(y1 - py0))
    for f in fc_box.values():
        p.draw_rect(R(f['safe']), color=(0, 0.6, 0.9), width=0.2, dashes='[1 2] 0', oc=layers['guides'])
    notch = coords.derived['thumb_notch']
    p.draw_circle(fitz.Point(lm.pt(notch['cx'] - px0), lm.pt(notch['y'] - py0)), lm.pt(notch['r'] + NOTCH_CLEAR_MM),
                  color=(0.9, 0.5, 0), width=0.2, dashes='[1 2] 0', oc=layers['guides'])
    ai.set_layer(-1, locked=[layers['cut'], layers['crease']])
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    ai.set_metadata({'title': '%s carton (layers)' % product['name'], 'creator': SURFACE})
    lm.tag_srgb(ai)
    ai.save(str(out / 'carton-artwork.ai'), garbage=3, deflate=True)
    ai.close()
    src.close()
    if render_preview:
        with fitz.open(str(out / 'carton-artwork.pdf')) as d:
            pix = d[0].get_pixmap(dpi=300, alpha=False)
            pix.set_dpi(300, 300)
            pix.save(str(out / 'carton-flat.png'))
    return {'foil': [x['plate'] for x in foil], 'relief': [x['plate'] for x in relief]}


def a4(out, coords, product, *, support_face=None):
    """carton-1to1-A4.pdf: the flat at 100 % on A4 portrait, centred, with crop marks at the die's corners and a fold
    mark beyond both ends of every crease, outside the bleed; a 100 mm ruler to prove the scale."""
    import fitz
    aw, ah = A4_MM
    px0 = py0 = -BLEED_MM
    W = coords.cut_polygon.bounds[2] + 2 * BLEED_MM
    H = coords.cut_polygon.bounds[3] + 2 * BLEED_MM
    ox, oy = (aw - W) / 2, (ah - H) / 2
    doc = fitz.open()
    p = doc.new_page(width=lm.pt(aw), height=lm.pt(ah))
    with fitz.open(str(out / 'carton-artwork.pdf')) as src:
        p.show_pdf_page(fitz.Rect(lm.pt(ox), lm.pt(oy), lm.pt(ox + W), lm.pt(oy + H)), src, 0)
    cx0, cy0, cx1, cy1 = coords.cut_polygon.bounds
    lm.crop_marks(p, (ox + cx0 - px0, oy + cy0 - py0, ox + cx1 - px0, oy + cy1 - py0))
    marks = 0
    for x1, y1, x2, y2 in coords.fold_lines:
        if abs(x1 - x2) < 1e-6:
            for y, s in ((cy0, -1), (cy1, 1)):
                X, Y = ox + x1 - px0, oy + y - py0 + s * (BLEED_MM + 1)
                p.draw_line(fitz.Point(lm.pt(X), lm.pt(Y)), fitz.Point(lm.pt(X), lm.pt(Y + s * FOLD_MARK_MM)),
                            color=(0, 0, 0), width=0.25, dashes='[1 1] 0')
                marks += 1
        else:
            for x, s in ((cx0, -1), (cx1, 1)):
                X, Y = ox + x - px0 + s * (BLEED_MM + 1), oy + y1 - py0
                p.draw_line(fitz.Point(lm.pt(X), lm.pt(Y)), fitz.Point(lm.pt(X + s * FOLD_MARK_MM), lm.pt(Y)),
                            color=(0, 0, 0), width=0.25, dashes='[1 1] 0')
                marks += 1
    support = support_face or lm.line_face('descriptor_en')['path']
    lm.label(p, '%s carton at 100 %% on our straight tuck end (%s, inside %g x %g x %g mm): crop marks at the die\'s '
                'corners, dashed marks at each fold. Print at actual size; the ruler is 100 mm.' % (
                    product['name'], TEMPLATE_VERSION, *product['inside_mm']), 10, ah - 16, support)
    lm._ruler(p, 10, ah - 12)
    doc.save(str(out / 'carton-1to1-A4.pdf'), garbage=3, deflate=True)
    doc.close()
    return {'page_mm': list(A4_MM), 'placed_at_mm': [round(ox, 2), round(oy, 2)], 'fold_marks': marks,
            'ruler_mm': 100, 'scale': a4_scale(out / 'carton-1to1-A4.pdf', coords)}


def a4_scale(pdf_path, coords):
    """The A4 sheet's scale, measured: the longest crease across and the longest along, as the sheet draws them (the
    artwork's crease colour, read through the placed page), each over the engine's own length (mm)."""
    import fitz
    k = lm.MM_PER_INCH / 72.0
    drawn = []
    with fitz.open(str(pdf_path)) as d:
        for dr in d[0].get_drawings():
            if dr['color'] is None or max(abs(a - b) for a, b in zip(dr['color'], CREASE_RGB)) > COLOUR_TOL:
                continue
            drawn += [((it[1].x * k, it[1].y * k), (it[2].x * k, it[2].y * k)) for it in dr['items'] if it[0] == 'l']
    out = {}
    for axis, along in (('x', 0), ('y', 1)):
        across = 1 - along
        mine = [abs(b[along] - a[along]) for a, b in drawn if abs(b[across] - a[across]) < 1e-3]
        engine = [abs(f[2 + along] - f[along]) for f in coords.fold_lines if abs(f[2 + across] - f[across]) < 1e-6]
        if not mine or not engine:
            raise ValueError('no crease along %s to measure the A4 sheet\'s scale by' % axis)
        out[axis] = {'drawn_mm': round(max(mine), 4), 'engine_mm': round(max(engine), 4),
                     'scale': round(max(mine) / max(engine), 5)}
    out['holds'] = all(abs(out[a]['scale'] - 1.0) <= A4_SCALE_TOL for a in ('x', 'y'))
    out['tolerance'] = A4_SCALE_TOL
    return out


def content_rows(layout, coords, fc_box):
    """Every element drawn on a panel (each copy line, the ℮ line, the fields, the EAN frame, the logos as laid out and
    as read from the file, the front's nodes as read from theirs): inside its panel's safe area — on the front, the safe
    box less the thumb notch's keep-out (``faces``) — and across no crease. [Day 13] A box that lies, wholly or in part,
    outside its own panel's box (``on_another_face``: the balm's Arabic line 9 on Day 12 lay wholly past its crease, on
    the front, and no crease line ran through it) counts as a crossing too."""
    rows = []
    for e in layout['elements']:
        b = e['flat']
        face = fc_box[e['panel']]
        in_box = pb._inside(b, face['safe'])
        off = not pb._inside(b, face['box'])
        row = {'panel': e['panel'], 'element': e['element'], 'box_mm': [round(v, 3) for v in b],
               'inside_safe_box': in_box, 'notch_clear': True, 'inside_safe': in_box,
               'crosses_a_crease': any(pb._crosses(b, f) for f in coords.fold_lines) or off,
               'on_another_face': off}
        if face['keep_out'] is not None:
            clear_mm = keep_out_clear_mm(b, face['keep_out'])
            row.update(notch_clear_mm=round(clear_mm, 3), notch_clear=clear_mm >= -1e-6,
                       inside_safe=in_box and clear_mm >= -1e-6)
        if 'read_from' in e:
            row['read_from'] = e['read_from']
        rows.append(row)
    return rows


def zero_crossings(fold_record, rows, ends_hold):
    """[Day 13, §1.3] "The fold check must report zero crossings", as four readings of the record: the die's fold check
    passed; every element inside its panel's safe area; no box across a crease; no box on another face. Each said, and
    the elements that fail one named."""
    across = [r['element'] for r in rows if r['crosses_a_crease'] and not r['on_another_face']]
    other = [r['element'] for r in rows if r['on_another_face']]
    outside = [r['element'] for r in rows if not r['inside_safe']]
    out = {'fold_check_passed': bool(fold_record['passed']), 'all_inside_safe': not outside and ends_hold,
           'nothing_across_a_crease': not across and not other, 'no_box_on_another_face': not other,
           'across_a_crease': across, 'on_another_face': other, 'outside_the_safe_area': outside}
    out['holds'] = bool(out['fold_check_passed'] and out['all_inside_safe'] and out['nothing_across_a_crease']
                        and out['no_box_on_another_face'])
    out['crossings'] = len(across) + len(other)
    out['said'] = ('the crossings counted: a box a crease line runs through, and a box that lies (wholly or in part) on '
                   'a face not its own; an element past its safe area but inside its own panel (in its margin) is not '
                   'a crossing and is named under outside_the_safe_area')
    return out


def line_rows(layout, blocks):
    """The fit report's lines: every drawn line, its language, fields, words, size, width, room, overflow."""
    out = []
    size_pt = layout['size_pt']
    for panel, band in layout['bands'].items():
        lines, _ = layout['laid'][panel]
        reviews = {r['field']: r['review'] for r in blocks[band['lang']]}
        for i, line in enumerate(lines):
            fields = []
            for field, _, _ in line['segments']:
                if field not in fields:
                    fields.append(field)
            out.append({'lang': band['lang'], 'panel': panel, 'line': i + 1, 'fields': fields,
                        'text': ' '.join(t for _, _, t in line['segments']), 'size_pt': size_pt,
                        'width_mm': round(line['width_mm'], 2), 'room_mm': round(line['run'][1] - line['run'][0], 2),
                        'run_mm': [round(v, 3) for v in line['run']],
                        'overflow_mm': round(line['overflow_mm'], 3), 'fits': line['overflow_mm'] <= 1e-6,
                        'shrunk': size_pt < BODY_START_PT, 'opens_on_dot': line['segments'][0][2].startswith('·'),
                        'opens_on_a_number': band['rtl'] and is_number(line['segments'][0][2].split()[0]),
                        'number_word_split': splits_a_number(
                            ' '.join(t for _, _, t in line['segments']),
                            ' '.join(t for _, _, t in lines[i + 1]['segments'])
                            if i + 1 < len(lines) and lines[i + 1]['para'] == line['para'] else '', band['rtl']),
                        'review': [reviews[f] for f in fields if reviews[f] is not None],
                        'direction': 'right to left' if band['rtl'] else 'left to right'})
            if line['overflow_mm'] > 1e-6:
                out[-1]['overflow_lies'] = overflow_lies(line['box'], panel, layout)
    return out


def overflow_lies(local, panel, layout):
    """Where an overflowing line lies on the flat: how far it runs past its panel's cut edge (cut off in print), the
    other faces it runs onto across a crease, and which of their elements (copy lines, the ℮ line, the EAN frame) it
    lands on — or that it stays inside its own panel, in the margin past the safe area."""
    fc_box = layout['faces']
    box = flat_box(local, fc_box[panel]['box'])
    past = past_cut_mm(box, fc_box[panel])

    def overlaps(a, b):
        return min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6
    onto = sorted(name for name, f in fc_box.items() if name != panel and overlaps(box, f['box']))
    on_copy = [{'panel': e['panel'], 'element': e['element']} for e in layout['elements']
               if e['panel'] != panel and overlaps(box, e['flat'])]
    said = 'inside its own panel, in the margin past the safe area'
    if past > 1e-6:
        said = 'past the trim: %.2f mm of it is cut off in print' % past
    elif on_copy:
        said = 'across the crease onto %s\'s drawn elements' % ', '.join(sorted({x['panel'] for x in on_copy}))
    elif 'front' in onto:
        said = 'across the crease onto the front, the display face (over its ground and any picture)'
    elif onto:
        said = 'across the crease onto %s, clear of its copy' % ', '.join(onto)
    return {'flat_box_mm': [round(v, 3) for v in box], 'past_the_trim_mm': round(past, 3), 'cut_off': past > 1e-6,
            'onto_faces': onto, 'on_other_copy': on_copy, 'said': said}


def copy_checked(pdf, blocks, names, product):
    """Word for word from the written file: each language's sections against its own ActualText spans
    (``palette_sticker.copy_check``), and the ℮ line once, whole. The sticker's ``net_in_every_language`` stays as it
    reads (False: the carton prints the ℮ line once, on the back), with the placement said beside it (``NET_ONCE``)."""
    checked = ps.copy_check(pdf, blocks, names)
    spans = lm.actual_texts(pdf, 0)
    net = [sp for n, sp in zip(names, spans) if n.split(':')[0] == 'net']
    left, right = product['net']
    checked['net'] = {'spans': net, 'found': net == [left, lm.SIGN, right]}
    fields = [sp for n, sp in zip(names, spans) if n.split(':')[0] == 'field']
    checked['fields'] = {'spans': fields, 'found': fields == [word for word, _ in FIELDS]}
    checked['net_placement'] = {'once_on_the_back': checked['net']['found'],
                                'in_every_language': checked['net_in_every_language'], 'said': NET_ONCE}
    return checked


def signs_on_the_back(pdf_path, ink_hex, back_box, net):
    """The ℮ as page 1 draws it (D-D11-6, read back): every path filled in the copy's ink whose centre is on the back
    and whose box is a sign's (1–6 mm tall, no wider than palette_sticker's 1.5 times its height). The back's band is
    turned a quarter, so a sign's height is its box's extent ACROSS the panel (flat x) and its width the extent along
    it (flat y). Each one held against the line's cap height and its neighbours' ink (``net['neighbour_ink_mm']``, the
    figures' own outlines), within 0.02 mm."""
    import fitz
    k = lm.MM_PER_INCH / 72.0
    ink = _rgb(ink_hex)
    bx0, by0, bx1, by1 = back_box
    rows = []
    with fitz.open(str(pdf_path)) as d:
        for dr in d[0].get_drawings():
            if dr['fill'] is None or max(abs(a - b) for a, b in zip(dr['fill'], ink)) > COLOUR_TOL:
                continue
            r = dr['rect']
            x0, y0, x1, y1 = (r.x0 * k - BLEED_MM, r.y0 * k - BLEED_MM, r.x1 * k - BLEED_MM, r.y1 * k - BLEED_MM)
            if not (bx0 <= (x0 + x1) / 2 <= bx1 and by0 <= (y0 + y1) / 2 <= by1):
                continue
            h, w = x1 - x0, y1 - y0
            if not (SIGN_BOX_MM[0] <= h <= SIGN_BOX_MM[1] and w <= ps.SIGN_ASPECT_MAX * h):
                continue
            rows.append({'box_mm': [round(v, 3) for v in (x0, y0, x1, y1)], 'height_mm': round(h, 4),
                         'width_mm': round(w, 4),
                         'at_the_cap_height': bool(abs(h - net['cap_mm']) <= READ_TOL_MM),
                         'at_least_3_mm': bool(h >= SIGN_MM - READ_TOL_MM),
                         'never_larger_than_its_neighbours': bool(h <= min(net['neighbour_ink_mm'].values())
                                                                  + READ_TOL_MM)})
    return rows


def logos_on_the_ends(pdf_path, logo_hex, fc_box):
    """Each end's logo as page 1 draws it: the union of the paths filled in the logo's ink whose centre lies on that end
    (the front's art may share the ink; only the ends are read), against the end's safe box within 0.02 mm. The top
    end's logo is drawn under a nested 180° turn the layout never sees: this is where the file puts it."""
    import fitz
    k = lm.MM_PER_INCH / 72.0
    ink = _rgb(logo_hex)
    parts = {'top_end': [], 'bottom_end': []}
    with fitz.open(str(pdf_path)) as d:
        for dr in d[0].get_drawings():
            if dr['fill'] is None or max(abs(a - b) for a, b in zip(dr['fill'], ink)) > COLOUR_TOL:
                continue
            r = dr['rect']
            box = (r.x0 * k - BLEED_MM, r.y0 * k - BLEED_MM, r.x1 * k - BLEED_MM, r.y1 * k - BLEED_MM)
            for end in parts:
                x0, y0, x1, y1 = fc_box[end]['box']
                if x0 <= (box[0] + box[2]) / 2 <= x1 and y0 <= (box[1] + box[3]) / 2 <= y1:
                    parts[end].append(box)
    out = {}
    for end, boxes in parts.items():
        if not boxes:
            out[end] = {'parts': 0, 'box_mm': None, 'inside_safe': False}
            continue
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        s = fc_box[end]['safe']
        out[end] = {'parts': len(boxes), 'box_mm': [round(v, 3) for v in box],
                    'inside_safe': bool(box[0] >= s[0] - READ_TOL_MM and box[1] >= s[1] - READ_TOL_MM
                                        and box[2] <= s[2] + READ_TOL_MM and box[3] <= s[3] + READ_TOL_MM)}
    return out


def refuse_unless_whole(checked):
    """The build stops when a line is dropped, moved or changed in the written file."""
    if checked['dropped'] or checked['moved'] or not checked['all_found'] or not checked['net']['found'] \
            or not checked['fields']['found']:
        raise CopyRefused('the written carton does not carry its copy word for word: dropped %s, moved %s, not found %s'
                          % (checked['dropped'], checked['moved'],
                             [(r['lang'], r['field']) for r in checked['rows'] if not r['found']]))


def collection_faces():
    """D-D14-2: the lid's Tajawal Medium for both Latin copy roles; retain its Arabic presentation-form face.

    This explicit collection choice leaves historical generic carton builds reproducible.
    Resolution still verifies the GRANTED source through the ordinary font-authority seam.
    """
    from apps.ire import font_roles
    latin = font_roles.resolve_line_face('Tajawal-Medium', 500.0)
    arabic = font_roles.resolve_line_face(*ps.ARABIC)
    if any(f.get('refused') for f in (latin, arabic)):
        raise ValueError('D-D14-2 collection face did not verify through font authority')
    return {'regular': latin, 'medium': latin, 'arabic': arabic}


def build(out_dir, *, product, translations=None, picture=None, nodes=None, colours=None, claims=None,
          copy_faces=None, render_previews=True):
    """The carton at $0 into ``out_dir``: refused before anything is drawn when the Spanish and Arabic are not on disk
    for this English (``translations``, default the product's own file). ``picture`` (a PNG) and ``nodes`` (engine
    nodes in the front's frame) are the front's art; ``colours`` overrides the placeholder colours by key; ``claims``
    (Brand.claims rows — the database's, read now, when None) decide the Arabic claims by D-D11-6's rule
    (``palette_sticker.arabic_claims``, the sticker's own). The four drawn files are written into engine/staging, the
    shipped PDF's copy checked there, and only then moved into place: a refused build leaves no deliverable beside the
    records. ``copy_faces`` supplies a verified collection face map. ``render_previews=False`` obeys D-D14-9:
    write PDFs and vector/text readbacks only, with the omitted pixel checks explicitly recorded."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    out = Path(out_dir)
    if translations is None:
        translations = translations_path(product)
    translated, provenance = load_translations(product, translations)
    if claims is None:
        claims = ps.house_claims()
    ar_claims = ps.arabic_claims(claims)
    pal = dict(PLACEHOLDER_COLOURS)
    if colours is not None:
        pal.update(colours)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    coords, fold_record = die(product)
    fc_box = faces(coords)
    blocks = copy(product, translated, provenance['model'], ar_claims)
    fc = copy_faces if copy_faces is not None else ps.faces()
    metrics = face_metrics(fc)
    doc, layout = document(product, coords, fc_box, blocks, pal, picture, nodes, fc, metrics)
    if nodes is not None:
        layout['elements'] += front_elements(out / 'engine', fc_box['front'], nodes, layout['page_mm'])
    usage = {}
    engine_ai = out / 'engine' / 'carton-engine.ai'
    emit_pdf_ai(doc, str(engine_ai), usage_out=usage,
                initial_font_role=fc['medium']['role'] if copy_faces is not None else None)
    names = drawn_names(doc)
    refuse_unless_whole(copy_checked(engine_ai, blocks, names, product))     # before a deliverable is written
    stage = out.joinpath(*STAGING)
    stage.mkdir(parents=True, exist_ok=True)
    plates = write_artwork(stage, engine_ai, coords, fc_box, usage, product, render_preview=render_previews)
    sheet = a4(stage, coords, product, support_face=fc['medium']['path'] if copy_faces is not None else None)
    checked = copy_checked(stage / 'carton-artwork.pdf', blocks, names, product)   # and again from the file shipped
    refuse_unless_whole(checked)
    deliverables = tuple(n for n in DELIVERABLES if render_previews or n != 'carton-flat.png')
    for name in deliverables:                                                       # only now into place
        os.replace(stage / name, out / name)

    ends = logos_on_the_ends(out / 'carton-artwork.pdf', pal['logo'], fc_box)
    for end, read in ends.items():
        if read['box_mm'] is not None:
            layout['elements'].append({'panel': end, 'element': 'the logo, read from the file',
                                       'flat': tuple(read['box_mm'])})
    rows = content_rows(layout, coords, fc_box)
    ends_hold = all(r['inside_safe'] for r in ends.values())
    record = {'schema': SCHEMA, 'product': product['key'], 'decision': product['decision'],
              'die': {'template': TEMPLATE, 'version': TEMPLATE_VERSION, 'ecma': coords.derived['ecma_code'],
                      'closure': coords.derived['style_words'], 'inside_mm': list(product['inside_mm']),
                      'crease_mm': coords.derived['crease_mm'], 'bleed_mm': BLEED_MM, 'safe_mm': SAFE_MM,
                      'board_mm': BOARD_MM, 'glue_tab_mm': coords.derived['glue']['width_mm'],
                      'glue_why': 'TRADE_RULES G2\'s default (12 mm)',
                      'flat_mm': [coords.flat_width_mm, coords.flat_height_mm], 'notes': coords.derived['notes'],
                      'thumb_notch': coords.derived['thumb_notch'],
                      'notch_keep_out_mm': round(coords.derived['thumb_notch']['r'] + NOTCH_CLEAR_MM, 3)},
              'fold_check': {'passed': fold_record['passed'], 'failed': fold_record['failed'],
                             'checks': len(fold_record['findings']), 'findings': fold_record['findings']},
              'faces': {k: {'box_mm': [round(v, 3) for v in f['box']], 'safe_mm': [round(v, 3) for v in f['safe']],
                            'cut': list(f['cut']), 'keep_out': f['keep_out']} for k, f in fc_box.items()},
              'content': rows, 'all_inside_safe': all(r['inside_safe'] for r in rows) and ends_hold,
              'nothing_across_a_crease': not any(r['crosses_a_crease'] for r in rows),
              'zero_crossings': zero_crossings(fold_record, rows, ends_hold),
              'notch_clear': all(r['notch_clear'] for r in rows),
              'logos_read_from_the_file': {'ends': ends, 'holds': ends_hold},
              'die_untouched': die_readback(out / 'carton-artwork.pdf', coords, -BLEED_MM, -BLEED_MM),
              'clean': (pb.clean_parts(engine_ai, layout['bare'], fc_box, -BLEED_MM, -BLEED_MM) if render_previews else
                        {'status': 'NOT_RUN', 'holds': None, 'reason': 'D-D14-9: no rendering; pixel ink check omitted'}),
              'front': layout['front'], 'plates': plates, 'a4': sheet, 'colours': pal,
              'colours_placeholder': sorted(k for k in pal if k not in (colours or {})),
              'staging': {'folder': str(stage), 'moved': list(deliverables),
                          'said': 'drawn into the staging folder and moved into place after the shipped PDF\'s copy '
                                  'held word for word'},
              'orientation': 'the copy set along each panel\'s length and turned a quarter counter-clockwise: it reads '
                             'bottom to top as the carton stands; the EAN frame turned with it (ladder); the top end\'s '
                             'logo turned 180° so it reads from the front, the bottom end\'s as laid'}
    lm.write_json(out / 'carton-fold-check.json', record)

    report = fit_report(out, product, layout, blocks, checked, names, provenance, pal, fc, metrics, ar_claims)
    return record, report


def zone_clear(band, size_pt):
    """[Day 13] A band's zone clearances at ``size_pt`` (mm): along the panel and across it; None with no zone."""
    cut = row_cut(band, size_pt)
    if cut is None:
        return None
    return {'along': round(cut['along_mm'], 3), 'across': round(cut['across_mm'], 3),
            'along_said': 'ZONE_GAP_MM %.1f + %d line(s) of %.3f mm at %.2f pt' % (
                band['zone_gap_mm'], band['zone_clear_lines'], pitch_at(size_pt), size_pt)}


FIELDS_SAID = {'side_near': 'its first rows', 'side_far': 'its last rows'}


def narrow_record(layout):
    """[Day 13, §1.3] The narrow-panel rule as it stood on this carton: the panels' widths against NARROW_PANEL_MM, the
    way the plan chose, and what that changed from Day 12's layout, in words."""
    bands = layout['bands']
    chosen = layout['chosen']
    widths = {p: round(b['across_mm'], 3) for p, b in bands.items()}
    applies = all(w < NARROW_PANEL_MM for w in widths.values())
    pitch = pitch_at(layout['size_pt'])
    did = ['the copy beside the foot stands %.3f mm clear of it along the panel (ZONE_GAP_MM %.1f + one line of '
           '%.3f mm at %.2f pt; Day 12: %.1f mm) — the owner\'s "cleared from the net line by one line\'s space"'
           % (ZONE_GAP_MM + FOOT_CLEAR_LINES * pitch, ZONE_GAP_MM, pitch, layout['size_pt'], ZONE_GAP_MM)]
    if chosen['fields_at'] == 'under_net':
        did.append('the batch and expiry fields stay under the ℮ line on the back (Day 12\'s foot, the whole safe width)')
    else:
        side = [p for p, b in bands.items() if b['zone_kind'] == 'fields'][0]
        did.append('the batch and expiry fields moved off the back to the far end of %s, on %s; the ℮ line stands alone '
                   'at the back\'s far end (part width): the copy beside it runs to it less the clearance, the rows past '
                   'it the back\'s whole safe length — columns inside the safe area' % (side, FIELDS_SAID[chosen['fields_at']]))
    if chosen['paragraphs'] == 'inci_run_on':
        did.append('the INCI placeholder runs on after the description in English and Spanish (Day 12 opened its own '
                   'line for it); nothing dropped, moved or changed. The Arabic keeps it on its own line: run on after '
                   'the description\'s Latin tail in a right-to-left line, the two would read in reverse')
    else:
        did.append('the paragraphs as Day 12 set them (description, INCI, how to use each open a line)')
    did.append('the EAN-13 on %s, ladder-wise and truncated as before' % chosen['ean_panel'])
    if chosen['overflow_lines']:
        did.append('%d line(s) still over at the %.0f pt floor, %d of them leaving their panel: listed line by line '
                   'with where each lies (overflow)' % (chosen['overflow_lines'], BODY_FLOOR_PT, chosen['crossing_lines']))
    return {'threshold_mm': NARROW_PANEL_MM, 'panel_width_mm': widths, 'applies': applies,
            'rule': 'the owner (Day 13, §1.3): for panels under 25 mm the regulated copy in columns inside the safe '
                    'area or run vertically along the long sides; the fold check zero crossings; the EAN ladder-wise '
                    'and truncated; type down to the 5 pt floor, any overflow listed. The copy already ran along the '
                    'panels; the engine now sets it in columns round each zone and measures the foot\'s parts and '
                    'the paragraphs as placements (plan: %d ways)' % len(layout['options']),
            'chosen': chosen, 'did': did}


def foot_clearance(pdf_path, layout, product, ink_hex):
    """[Day 13, §1.1] How far the copy stands from the ℮ line and the write-in fields along the panel, read from page 1
    of the written file: each foot part as drawn (the ℮ line's figure spans and its sign — every path in the copy's ink
    between them; the fields' label spans and their boxes' strokes) on its panel, and every copy span on that panel
    whose extent across the panel meets the part's — the least gap between them along the panel, against ZONE_GAP_MM
    plus FOOT_CLEAR_LINES of the size set (within READ_TOL_MM). The least gap across to the spans past the part is said
    beside it."""
    import fitz
    k = lm.MM_PER_INCH / 72.0
    fc_box = layout['faces']
    left, right = product['net']
    labels = [w for w, _ in FIELDS]
    ink = _rgb(ink_hex)

    def flat(r):
        return (r[0] * k - BLEED_MM, r[1] * k - BLEED_MM, r[2] * k - BLEED_MM, r[3] * k - BLEED_MM)

    def on(box, panel):
        x0, y0, x1, y1 = fc_box[panel]['box']
        return x0 <= (box[0] + box[2]) / 2 <= x1 and y0 <= (box[1] + box[3]) / 2 <= y1

    def union(boxes):
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    spans, paths = [], []
    with fitz.open(str(pdf_path)) as d:
        for b in d[0].get_text('dict')['blocks']:
            if 'lines' not in b:
                continue
            spans += [(sp['text'].strip(), flat(tuple(sp['bbox']))) for ln in b['lines'] for sp in ln['spans']
                      if sp['text'].strip()]
        for dr in d[0].get_drawings():
            for key in ('fill', 'color'):
                if dr[key] is not None and max(abs(a - b) for a, b in zip(dr[key], ink)) <= COLOUR_TOL:
                    paths.append((key, flat(tuple(dr['rect']))))
    parts = []
    net_spans = [b for t, b in spans if t in (left, right) and on(b, 'back')]
    if net_spans:
        box = union(net_spans)
        sign = [b for key, b in paths if key == 'fill' and on(b, 'back') and b[0] >= box[0] - READ_TOL_MM
                and b[2] <= box[2] + READ_TOL_MM and b[1] >= box[1] - READ_TOL_MM and b[3] <= box[3] + READ_TOL_MM]
        parts.append(('net', 'back', union(net_spans + sign)))
    field_panels = [p for p in COPY_PANELS if any(t in labels and on(b, p) for t, b in spans)]
    for panel in field_panels:
        drawn = [b for t, b in spans if t in labels and on(b, panel)]
        drawn += [b for key, b in paths if key == 'color' and on(b, panel)
                  and abs((b[3] - b[1]) - FIELD_BOX_MM[0]) <= 0.5 and abs((b[2] - b[0]) - FIELD_BOX_MM[1]) <= 0.5]
        parts.append(('fields', panel, union(drawn)))
    size_pt = layout['size_pt']
    want = ZONE_GAP_MM + FOOT_CLEAR_LINES * pitch_at(size_pt)
    out = []
    for name, panel, box in parts:
        copy_spans = [b for t, b in spans if on(b, panel) and t not in (left, right) and t not in labels
                      and t != 'EAN-13']
        beside = [b for b in copy_spans if min(b[2], box[2]) - max(b[0], box[0]) > 1e-6]
        past = [b for b in copy_spans if min(b[2], box[2]) - max(b[0], box[0]) <= 1e-6]
        along = [max(b[1] - box[3], box[1] - b[3]) for b in beside]
        across = [max(b[0] - box[2], box[0] - b[2]) for b in past]
        least, least_across = None, None
        if along:
            least = round(min(along), 3)
        if across:
            least_across = round(min(across), 3)
        out.append({'part': name, 'panel': panel, 'box_mm': [round(v, 3) for v in box], 'spans_beside': len(beside),
                    'least_gap_along_mm': least, 'least_gap_across_mm': least_across,
                    'holds': least is None or least >= want - READ_TOL_MM})
    read_from = str(Path(pdf_path).resolve())
    if read_from.startswith(str(lm.REPO) + os.sep):
        read_from = lm.rel(pdf_path)
    return {'want_along_mm': round(want, 3), 'size_pt': size_pt, 'parts': out,
            'holds': bool(out) and all(p['holds'] for p in out), 'read_from': read_from,
            'measured': 'page 1\'s text spans and the ink\'s paths, each on the panel holding its centre: the gap along '
                        'the panel (flat y) between a foot part and each copy span sharing its extent across (flat x)'}


def marked(blocks, ar_claims):
    """[Day 13, D-D13-6] The copy as the owner marks it for the prototypes, field by field and language by language:
    the English his draft, the Spanish and Arabic machine drafts for review, the INCI a placeholder, the Arabic claims
    to confirm — the words printed as they stand, nothing invented to fill a gap."""
    out = {}
    for lang in LANGS:
        out[lang] = {}
        for r in blocks[lang]:
            mark = r['review']
            if mark is None:
                mark = r['source']
            out[lang][r['field']] = mark
    return {'decision': 'D-D13-6', 'by_field': out, 'arabic_claims_owner_to_confirm': ar_claims[2],
            'said': 'the carton copy prints on the prototypes as it stands, marked: the English the owner\'s draft '
                    '(his to edit on the page before Day 15), the Spanish and Arabic machine drafts "for review", the '
                    'INCI a placeholder "owner to supply", the Arabic claims "owner to confirm"; nothing is invented '
                    'to fill a gap'}


def fit_report(out, product, layout, blocks, checked, names, provenance, pal, fc, metrics, ar_claims):
    """carton-fit-report.json: the body size, each language's capacity at the 5 pt floor, every line (its size, width,
    room and overflow, and where an overflow lies on the flat), the ℮ line's measures and its sign read back from the
    file, the EAN's truncation, the Arabic claims' rule, the copy's sources and what is for review."""
    import fitz
    lines = line_rows(layout, blocks)
    sizes_drawn = []
    with fitz.open(str(out / 'carton-artwork.pdf')) as d:
        for b in d[0].get_text('dict')['blocks']:
            if 'lines' not in b:
                continue
            for ln in b['lines']:
                for sp in ln['spans']:
                    sizes_drawn.append(round(float(sp['size']), 3))
        fonts = {f[3]: {'embedded': f[1] not in ('', 'n/a'), 'type': f[2]} for f in d[0].get_fonts(full=True)}
    foot = layout['foot']
    ean_panel = [p for p, b in layout['bands'].items() if b['zone_kind'] == 'ean'][0]
    fields_panel = [p for p, b in layout['bands'].items() if b['zone_kind'] in ('foot', 'fields')][0]
    band = layout['bands'][ean_panel]
    drawn_h = band['zone'][3] - band['zone'][1]
    contrast = lm.contrast_ratio(pal['ink'], pal['ground'])
    desc_lines = {lang: len([ln for ln in lines if ln['lang'] == lang and 'description' in ln['fields']])
                  for lang in LANGS}
    desc_text = {lang: [r['text'] for r in blocks[lang] if r['field'] == 'description'][0] for lang in LANGS}
    net_text = '%s %s %s' % (product['net'][0], lm.SIGN, product['net'][1])
    signs = signs_on_the_back(out / 'carton-artwork.pdf', pal['ink'], layout['faces']['back']['box'], foot)
    one_sign = len(signs) == 1
    overflow = [ln for ln in lines if not ln['fits']]
    review = [{'lang': r['lang'], 'field': r['field'], 'text': r['text'], 'review': r['review']}
              for lang in LANGS for r in blocks[lang] if r['review'] is not None]
    review += [{'lang': lang, 'field': 'description_lines', 'text': desc_text[lang],
                'review': 'the description runs to %d lines: D-D11-7 asks one line each — to shorten or to rule'
                          % desc_lines[lang]} for lang in LANGS if desc_lines[lang] != 1]
    review.append({'lang': 'all', 'field': 'net', 'text': net_text, 'review': NET_ONCE})
    provisional = ['⟪PROVISIONAL⟫ INCI: owner to supply (every language)',
                   '⟪PROVISIONAL⟫ the EAN-13: a frame, no number; its bars cut to the safe width',
                   '⟪PROVISIONAL⟫ the facts of %s (the owner\'s to correct)' % product['decision'],
                   '⟪PROVISIONAL⟫ %s' % NET_ONCE]
    if layout['front']['picture'] is not None:
        provisional.append('⟪PROVISIONAL⟫ the front picture\'s content (a raster) is not checked against the safe area '
                           'or the thumb notch\'s keep-out')
    text, source, confirm, why = ar_claims
    report = {
        'schema': FIT_SCHEMA, 'product': product['key'],
        'body': {'size_pt': layout['size_pt'], 'start_pt': BODY_START_PT, 'floor_pt': BODY_FLOOR_PT,
                 'step_pt': BODY_STEP_PT, 'fits': layout['fits'], 'lead': LEAD, 'para_gap_lines': PARA_GAP},
        'capacity_at_floor': capacity_at_floor(blocks, layout['bands'], fc, metrics),
        'need_at_floor_mm': {k: round(v, 1) for k, v in layout['need_at_floor_mm'].items()},
        'panels': {p: {'lang': b['lang'], 'band_mm': [round(b['length_mm'], 3), round(b['across_mm'], 3)],
                       'copy_area_mm': [round(v, 3) for v in copy_area(b, layout['size_pt'])], 'zone': b['zone_kind'],
                       'zone_mm': None if b['zone'] is None else [round(v, 3) for v in b['zone']],
                       'zone_clear_mm': zone_clear(b, layout['size_pt']),
                       'columns': columns(band_rows(b, layout['size_pt'], metrics)),
                       'paragraphs': b['paragraphs']}
                   for p, b in layout['bands'].items()},
        'lines': lines, 'overflow': overflow,
        'overflow_cut_off': [{'panel': ln['panel'], 'lang': ln['lang'], 'line': ln['line'],
                              'past_the_trim_mm': ln['overflow_lies']['past_the_trim_mm']}
                             for ln in overflow if ln['overflow_lies']['cut_off']],
        'every_line_inside_its_area': all(ln['fits'] for ln in lines),
        'no_line_opens_on_dot': not any(ln['opens_on_dot'] for ln in lines),
        'no_arabic_line_opens_on_a_number': not any(ln['opens_on_a_number'] for ln in lines),
        'no_line_opens_on_a_number_word_split': {lang: not any(ln['number_word_split'] for ln in lines
                                                               if ln['lang'] == lang) for lang in LANGS},
        'description_one_line': desc_lines,
        'description_one_line_holds': all(n == 1 for n in desc_lines.values()),
        'smallest_pt': min([layout['size_pt'], FIELD_PT, EAN_PT, foot['size_pt']]),
        'sizes_read_from_the_file_pt': sorted(set(sizes_drawn)),
        'net': {'text': net_text, 'size_pt': round(foot['size_pt'], 3),
                'cap_mm': round(foot['cap_mm'], 3), 'sign_mm': foot['sign_mm'], 'width_mm': round(foot['total'], 2),
                'neighbour_ink_mm': {k: round(v, 4) for k, v in foot['neighbour_ink_mm'].items()},
                'read_from_the_file': signs, 'signs_found': len(signs),
                'sign_never_larger': one_sign and signs[0]['never_larger_than_its_neighbours'],
                'sign_at_least_3mm': one_sign and signs[0]['at_least_3_mm'],
                'sign_at_the_cap_height': one_sign and signs[0]['at_the_cap_height'],
                'measured': 'the sign\'s height read from page 1 of carton-artwork.pdf (its extent across the turned '
                            'band), against the figures\' ink (text_metrics.ink_extent_em) within 0.02 mm',
                'placement': NET_ONCE,
                'sign': 'the house\'s estimated sign (lid_master.sign_segments), drawn as a path with its ActualText'},
        'ean': {'panel': ean_panel, 'lang_beside': band['lang'], 'nominal_mm': list(EAN_MM),
                'drawn_mm': [EAN_MM[0], round(drawn_h, 3)], 'bar_height_cut_mm': round(EAN_MM[1] - drawn_h, 3),
                'orientation': 'ladder: the symbol\'s width along the panel\'s length, its bars across the panel',
                'number': None, 'status': 'truncated — owner to confirm',
                'conflict': 'label_layout keeps a symbol "never taller or shorter than its own proportions"; '
                            'D-D11-7 asks for the bars cut to the safe width — his to rule',
                'why_here': 'of the %d ways to put the three languages on the back and the long sides with the '
                            'EAN on either side (each set by the fit; panel_plan.options; [Day 13] on narrow panels '
                            'with the fields and the paragraphs placed too), the one panel_plan.rule chooses'
                            % len(layout['options'])},
        'panel_plan': {'chosen': {p: b['lang'] for p, b in layout['bands'].items()}, 'ean_panel': ean_panel,
                       'fields_at': layout['chosen']['fields_at'], 'paragraphs': layout['chosen']['paragraphs'],
                       'options': layout['options'],
                       'rule': 'the largest body size that fits, then the fewest lines run past a cut edge (cut off in '
                               'print), [Day 13] then the fewest lines leaving their panel (across a crease or onto '
                               'another face), then the fewest lines over, [Day 13] then the fewest changes from Day '
                               '12\'s layout (its paragraphs, its foot under the ℮ line); on a tie the house\'s order '
                               '(EN back, ES left, AR right, the EAN on the right side)'},
        'arabic_claims': {'text': text, 'source': source, 'owner_to_confirm': confirm, 'why': why,
                          'rule': 'D-D11-6 at build time, by palette_sticker.arabic_claims on Brand.claims (the '
                                  'sticker\'s own rule)'},
        'fields': {'batch_and_expiry': [w for w, _ in FIELDS], 'box_mm': list(FIELD_BOX_MM),
                   'said': 'write-in boxes: no batch or date is invented',
                   'panel': fields_panel, 'placed': layout['chosen']['fields_at']},
        'contrast': {'ink': pal['ink'], 'ground': pal['ground'], 'ratio': round(contrast, 2), 'min': CONTRAST_MIN,
                     'holds': contrast >= CONTRAST_MIN},
        'faces': {k: v['label'] for k, v in fc.items()},
        'copy': checked, 'span_names': names,
        'sources': {lang: {r['field']: r['source'] for r in blocks[lang]} for lang in LANGS},
        'for_review': review,
        'provisional': provisional,
        'translations': provenance,
        'fonts': fonts, 'fonts_embedded': all(f['embedded'] for name, f in fonts.items() if name != 'Helvetica'),
        'narrow_panels': narrow_record(layout),
        'foot_clearance': foot_clearance(out / 'carton-artwork.pdf', layout, product, pal['ink']),
        'marked': marked(blocks, ar_claims),
    }
    lm.write_json(out / 'carton-fit-report.json', report)
    return report
