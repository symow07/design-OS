"""Day 11 — Golden Hour closed as test one (D-D11-5): the bars embossed, the tray's teal (code), the sticker's corrected
lines (D-D11-6), one Latin face, and Day 10's files untouched.

The measuring functions are tested on synthetic inputs, each check beside a control that must fail (a planted fault);
the day's files are read where they are on this machine (skipped where they are not) and measured from the files
themselves — the relief from the file's EMBOSS plate, the sticker's words from its own ActualText."""
import json

import numpy as np
import pytest

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_open as po
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import round_files_faces as faces

DAY10 = lm.REPO / 'docs' / 'audit' / 'day-10'
pick_here = pytest.mark.skipif(not lm.PICK.exists(), reason='the owner\'s pick is not on this machine')
day10_here = pytest.mark.skipif(not (DAY10 / 'sticker' / 'fit-report.json').exists(), reason='Day 10 is not here')


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


# --- 1. the relief: 0.3 mm on the file's own plate -----------------------------------------------------------------------

def _ring(points):
    return [('L', points[i], points[(i + 1) % len(points)]) for i in range(len(points))]


def _plate_file(tmp_path, rings, name):
    """An engine page carrying ``rings`` on the EMBOSS plate (the lid master's own carrier), emitted as the master is."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    doc = Document(page_w=lm.LID_MM[0], page_h=lm.LID_MM[1], metadata={'typography_surface': lm.SURFACE},
                   root=Group(name='T', children=[lm.relief_carrier(rings, '#C69559')]))
    path = tmp_path / name
    emit_pdf_ai(doc, str(path))
    return path


BAR = [(10.0, 10.0), (40.0, 10.0), (40.0, 16.0), (10.0, 16.0)]
#: the control: the same bar with a sliver 0.2 mm wide and 3 mm long standing off its edge
BAR_WITH_SLIVER = [(10.0, 10.0), (40.0, 10.0), (40.0, 16.0), (25.1, 16.0), (25.1, 19.0), (24.9, 19.0), (24.9, 16.0),
                   (10.0, 16.0)]


MEASURED = ('within_the_isoline', 'reaches_the_isoline', 'off_the_glow', 'the_control_fails', 'the_reach_control_fails',
            'plate_0_3_mm')
NOT_MEASURED = ('capped_outer_edges', 'bar_ends')     # by construction: never recorded as held


# --- 3. the sticker's lines (D-D11-6) ------------------------------------------------------------------------------------

UNCONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خالٍ من القسوة', 'ar_source': ps.AR_UNCONFIRMED},
               {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': ps.AR_UNCONFIRMED}]
CONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خال من القسوة', 'ar_source': 'OWNER'},
             {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': 'OWNER'}]


def test_the_arabic_claims_print_the_house_record_only_when_confirmed():
    from apps.core import models as core
    assert ps.AR_UNCONFIRMED is core.AR_UNCONFIRMED                    # the house's mark, imported, never repeated
    text, _, confirm, _ = ps.arabic_claims(CONFIRMED)
    assert text == 'خال من القسوة · نباتي 100٪' and not confirm
    # the review of Day 11: a row with no ar_source (or an empty one) is unconfirmed — it never fails open
    no_source = [{k: v for k, v in r.items() if k != 'ar_source'} for r in CONFIRMED]
    empty_source = [dict(r, ar_source='') for r in CONFIRMED]
    for claims in (UNCONFIRMED, [], CONFIRMED[:1] + UNCONFIRMED[1:], no_source, empty_source, CONFIRMED[:1] + no_source[1:]):
        text, _, confirm, _ = ps.arabic_claims(claims)
        assert text == ps.AR_CLAIMS_FALLBACK and confirm


def test_a_claims_row_without_ar_source_failed_open_under_the_old_rule():
    """The control of the claims fix: the rule as it stood (unconfirmed only when ar_source says EXECUTOR_UNCONFIRMED)
    printed a row with no ar_source as confirmed; ``confirmed_arabic`` does not."""
    def old_unconfirmed(r):
        return 'ar' not in r or not r['ar'] or ('ar_source' in r and r['ar_source'] == ps.AR_UNCONFIRMED)
    row = {'en': 'Cruelty-free', 'ar': 'خال من القسوة'}
    assert not old_unconfirmed(row) and not ps.confirmed_arabic(row)
    assert ps.confirmed_arabic(CONFIRMED[0]) and not ps.confirmed_arabic(UNCONFIRMED[0])


def test_a_claims_line_never_opens_on_a_separator_and_day_10s_wrap_did():
    """The claims wrap claim by claim, the separator kept at its line's end; the control: Day 10's word-by-word wrap of
    the same line at the same column opens a line on "·"."""
    fc = ps.faces()
    text = ps.CORRECTED['es']['claims']
    row = {'field': 'claims', 'head': None, 'text': text, 'script': 'latin', 'lang': 'es',
           'units': ps.wrap_units(text, 'claims')}
    plain = dict(row)
    plain.pop('units')
    opened = []
    for column in np.arange(18.0, 60.0, 0.5):
        lines = [' '.join(t for _, t in line) for line in ps.wrap(row, column, 7.0, fc)]
        assert not any(line.startswith(ps.SEPARATOR) for line in lines)
        assert ' '.join(lines) == text
        opened += [column for line in ps.wrap(plain, column, 7.0, fc) if ' '.join(t for _, t in line).startswith(ps.SEPARATOR)]
    assert opened                                   # the control has power: word by word, some width opens on "·"
    assert ps.wrap_units(text, 'claims') == [['No', 'testado', 'en', 'animales', '·'], ['100', '%', 'vegano', '·'],
                                             ['Probado', 'dermatológicamente', '·'], ['Larga', 'duración']]


def test_the_corrected_copy_refuses_lawha():
    """باليت everywhere: an Arabic line that still says لوحة is refused (the control: Day 10's machine description)."""
    translations = {'calls': {name: {'translations': {lang: dict(fields) for lang in ('es', 'ar')}} for name, fields in (
        ('prose', {'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}),
        ('short lines', {'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}),
        ('headings', {'product_name': 'x', 'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}))}, 'model': 'm'}
    blocks = ps.corrected_copy(translations, UNCONFIRMED)
    assert {r['field']: r['text'] for r in blocks['ar']}['description'] == ps.CORRECTED['ar']['description']
    translations['calls']['prose']['translations']['ar']['warnings'] = 'لوحة ظلال'
    with pytest.raises(ValueError, match='لوحة'):
        ps.corrected_copy(translations, UNCONFIRMED)


# --- 4. one Latin face ---------------------------------------------------------------------------------------------------


# --- 2. the tray's teal: the code -----------------------------------------------------------------------------------------

def test_the_tray_prompt_states_the_colour_story_row_by_row_with_three_teal_pans_in_row_3():
    tray = po.tray_names()
    prompt = po.tray_story_prompt(tray)
    rows = [prompt.index('ROW %d' % i) for i in (1, 2, 3)]
    assert rows == sorted(rows)
    row3 = prompt[rows[2]:prompt.index('Row 3 must')]
    assert all(name in row3 for name in tray['names'][2]) and row3.count(' teal,') >= 3
    for r, names in enumerate(tray['names']):
        seg = prompt[rows[r]:]
        assert all(name in seg for name in names)
    from apps.pipeline.services import round_calls as ig
    assert not ig.competitor_in(prompt)


def _read(hexes):
    from apps.pipeline.targets.container import tray_picture as tp
    return {'state': tp.READ, 'pans': [[{'hex': h} for h in row] for row in hexes]}


def test_row_3s_teal_is_counted_from_the_picture_and_browns_are_not_teal():
    teals = ['#4F9A94', '#5FB3AE', '#2E6B6B', '#745555', '#65526A', '#43312E']
    assert po.teal_pans(_read([['#000000'] * 6, ['#000000'] * 6, teals]))['count'] == 3
    day10_row3 = ['#745555', '#65526A', '#43312E', '#402A36', '#252E3C', '#15222F']   # Day 10's tray, as read
    assert not po.teal_pans(_read([['#000000'] * 6, ['#000000'] * 6, day10_row3]))['holds']


def test_a_pan_too_close_to_the_case_is_lightened_by_the_least_step_that_reaches_delta_e_10():
    case = '#102638'
    rows = [{'name': 'Eternal', 'hex': '#252E3C', 'flags': []}, {'name': 'Petal Frost', 'hex': '#DAB4AC', 'flags': []}]
    moved = po.lift_from_case(rows, case)
    assert [m['name'] for m in moved] == ['Eternal'] and rows[1]['hex'] == '#DAB4AC'
    m = moved[0]
    de = float(faces.delta_e00(po._lab(m['to']), po._lab(case))[0])
    assert de >= po.CASE_DE_FLOOR and rows[0]['picture_hex'] == '#252E3C'
    # the control: one step less does not reach it
    lab = po._lab('#252E3C')[0]
    less = po._hex(po.lab_to_srgb(np.array([lab[0] + m['l_step'] - po.LIFT_STEP_L, lab[1], lab[2]])))
    assert float(faces.delta_e00(po._lab(less), po._lab(case))[0]) < po.CASE_DE_FLOOR


def test_lab_to_srgb_inverts_srgb_to_lab():
    rng = np.random.default_rng(11)
    rgb = rng.integers(0, 256, (200, 3)).astype(np.float64)
    assert np.abs(po.lab_to_srgb(faces.srgb_to_lab(rgb)) - rgb).max() < 0.01        # far under half a level


# --- Day 10 untouched ----------------------------------------------------------------------------------------------------


# --- the review of Day 11: the relief's proof, the eye's texts, the margin, Day 10's defaults --------------------------


AREA_SERVICES = ('golden_hour_fixes', 'lid_master', 'palette_sticker', 'palette_open', 'palette_box', 'palette_board')


def numeric_defaults(source):
    """Every default argument that is a number — a literal, or a module-level name bound to one (the services' ban;
    the lint gate reads literals only)."""
    import ast
    tree = ast.parse(source)
    numeric = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                value = value.operand
            if isinstance(value, ast.Constant) and type(value.value) in (int, float):
                numeric |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for d in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
                if (isinstance(d, ast.Name) and d.id in numeric) or (isinstance(d, ast.Constant) and type(d.value) in (int, float)):
                    found.append(ast.unparse(d))
    return found


