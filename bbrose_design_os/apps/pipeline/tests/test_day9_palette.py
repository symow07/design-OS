"""Day 9 — palette round 2: the guard re-rooted, the finish proof, the lettering, the Arabic display face, the plate
paths and proofs, the jury's two pictures and desirability, the pick page; on fixtures, no provider called. Each module
under test has its own section ("Day 9: <module>"); only the pick page's tests use the database."""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import math
import re
import shutil
import statistics
from pathlib import Path
from types import SimpleNamespace

import cv2
import fitz
import numpy as np
import pytest
from PIL import Image

from apps.ire import font_instances, font_roles
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import ClosePath, Color, CubicTo, Document, Finish, Group, LineTo, MoveTo, SolidFill, TextRun
from apps.ire.graph import Path as VPath           # the engine's vector path; ``Path`` is pathlib's throughout
from apps.pipeline.services import round_calls as ig
from apps.pipeline.services.concept_quality import DIMENSIONS


def _sha(path) -> str:
    """The sha256 of a file's bytes, the file named by a str or a Path (the arabic, jury and pick sections)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ======================================================================================================================
# Day 9: image_guard — the guard re-rooted for Day 9 (D-D9-1): Day 8's builds are rejected designs, and the one allowed
# logo is the approval's own source raster, by path and sha256.
# ======================================================================================================================

def test_day9_rejects_day8s_builds_and_allows_only_the_approved_logo_raster(tmp_path, monkeypatch, settings):
    """D-D9-1 / UNCHANGED: Day 8's builds are rejected designs — every picture under docs/audit/day-8 is refused before
    payment; the approved logo goes in only as the approval's own source raster, by path and sha256; Day 9's calls
    log to Day 9's own file and only Day 9's paid pictures are exempt."""
    settings.IMAGE_MODEL = 'gpt-image-2'
    assert ig.REPO / 'docs' / 'audit' / 'day-8' in ig.REJECTED_ROOTS
    assert not any('day-8' in str(r) for r in ig.ALLOWED_ROOTS)
    # [Day 10] the guard moved on: today's calls log to Day 10's file under 'day10/'; Day 9's log is closed and kept, and
    # audited under Day 9's own roots (test_day9_builds) — [Day 11] and on again: Day 11's file under 'day11/', Day 10's
    # log closed and audited under Day 10's own roots (test_day10_master)
    # [Day 12] and on again: Day 12's file under 'day12/', Day 11's log closed and audited under Day 11's own prefix
    # (test_day11_zilal)
    assert ig.CALL_LOG.parent.name == 'day-12' and ig.TODAY_OPERATION_PREFIX == 'day12/'
    logo, sha = ig.APPROVED_LOGO
    if not logo.exists():
        pytest.skip('the approved logo raster is not on this machine')
    deny = {'rejected': {sha: 'an archived copy of the mark in a rejected root'}, 'web': {}}
    checked = ig.check([{'role': 'the approved BBROSE logo', 'path': logo}], 'flat lid artwork', deny=deny)
    assert checked[0]['sha256'] == sha            # the approved file passes although its bytes sit in a rejected root
    day8_sketch = ig.REPO / 'docs' / 'audit' / 'day-8' / 'sketches' / 'B3' / 'lid.png'
    if day8_sketch.exists():
        with pytest.raises(ig.ImageCallRefused):
            ig.check([{'role': 'a Day 8 sketch', 'path': day8_sketch}], 'flat lid artwork')
    copy = tmp_path / 'bbrose-logo.png'
    copy.write_bytes(logo.read_bytes())
    with pytest.raises(ig.ImageCallRefused):                    # the same bytes elsewhere are not the approved file
        ig.check([{'role': 'a copy of the logo', 'path': copy}], 'flat lid artwork', deny=deny)


# ======================================================================================================================
# Day 9: finish_proof — the finish proof (D-D9-6) and the finish measures (D-D9-3) on engine-built fixtures: every plate
# here is drawn by the engine (a Document with its finishes, through ``emit_pdf_ai``) and read back from the .ai's own
# plate pages. DB-free; no provider is called.
# ======================================================================================================================

LID_W_MM, LID_H_MM = 190.0, 120.0
LID_MM2 = LID_W_MM * LID_H_MM
GOLD = Color.from_hex('#C9A24B')
SILVER = Color.from_hex('#A9ABAE')
FOIL = Finish(kind='foil', plate='FOIL_GOLD', appearance=GOLD)
METALLIC = Finish(kind='metallic_ink', plate='METALLIC_9244C', appearance=SILVER)
EMBOSS = Finish(kind='emboss', plate='EMBOSS')
DEBOSS = Finish(kind='deboss', plate='DEBOSS')
SPOT_UV = Finish(kind='spot_uv', plate='SPOT_UV')


DAY9_CONCEPTS = Path(__file__).resolve().parents[4] / 'docs' / 'audit' / 'day-9' / 'concepts'


def _box(name, x_mm, y_mm, w_mm, h_mm, hex_value, finishes=()):
    return VPath(name=name, fill=SolidFill(color=Color.from_hex(hex_value)), finishes=list(finishes),
                 segments=[MoveTo(x=x_mm, y=y_mm), LineTo(x=x_mm + w_mm, y=y_mm), LineTo(x=x_mm + w_mm, y=y_mm + h_mm),
                           LineTo(x=x_mm, y=y_mm + h_mm), ClosePath()])


def _bar(name, cx_mm, cy_mm, length_mm, width_mm, angle_deg, finishes):
    """A filled bar ``width_mm`` wide, its axis at ``angle_deg`` through (cx, cy)."""
    a = math.radians(angle_deg)
    ux, uy, px, py = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    half_l, half_w = length_mm / 2.0, width_mm / 2.0
    corners = [(cx_mm - ux * half_l - px * half_w, cy_mm - uy * half_l - py * half_w),
               (cx_mm + ux * half_l - px * half_w, cy_mm + uy * half_l - py * half_w),
               (cx_mm + ux * half_l + px * half_w, cy_mm + uy * half_l + py * half_w),
               (cx_mm - ux * half_l + px * half_w, cy_mm - uy * half_l + py * half_w)]
    return VPath(name=name, fill=SolidFill(color=GOLD), finishes=list(finishes),
                 segments=[MoveTo(x=corners[0][0], y=corners[0][1])]
                 + [LineTo(x=x, y=y) for x, y in corners[1:]] + [ClosePath()])


def _disc(name, cx_mm, cy_mm, r_mm, finishes):
    k = 0.5523 * r_mm
    return VPath(name=name, fill=SolidFill(color=GOLD), finishes=list(finishes), segments=[
        MoveTo(x=cx_mm + r_mm, y=cy_mm),
        CubicTo(x1=cx_mm + r_mm, y1=cy_mm + k, x2=cx_mm + k, y2=cy_mm + r_mm, x=cx_mm, y=cy_mm + r_mm),
        CubicTo(x1=cx_mm - k, y1=cy_mm + r_mm, x2=cx_mm - r_mm, y2=cy_mm + k, x=cx_mm - r_mm, y=cy_mm),
        CubicTo(x1=cx_mm - r_mm, y1=cy_mm - k, x2=cx_mm - k, y2=cy_mm - r_mm, x=cx_mm, y=cy_mm - r_mm),
        CubicTo(x1=cx_mm + k, y1=cy_mm - r_mm, x2=cx_mm + r_mm, y2=cy_mm - k, x=cx_mm + r_mm, y=cy_mm), ClosePath()])


#: a typography surface tag, so the engine sets live text through its type roles and plates a finished run (an
#: untagged document is drawn the legacy way, which plates no text)
SURFACE = {'typography_surface': 'apps/pipeline/services/finish_proof.py::tests'}


def _ai(tmp_path, name, nodes, *, carriers=()):
    """The nodes on a 190 x 120 lid through the engine; clear finishes ride on zero-opacity carriers (Day 8's way)."""
    children = [Group(name='ART', children=[_box('ground', 0, 0, LID_W_MM, LID_H_MM, '#3B1F3A')] + list(nodes))]
    if carriers:
        children.append(Group(name='FINISH CARRIERS', role='effects', opacity=0.0, children=list(carriers)))
    doc = Document(page_w=LID_W_MM, page_h=LID_H_MM, title=name, metadata=dict(SURFACE),
                   root=Group(name='Artwork', children=children))
    path = tmp_path / ('%s.ai' % name)
    emit_pdf_ai(doc, str(path))
    return path


def _flat(ai_path, out_png, *, cols_px, rows_px):
    """Page 1 of the .ai, rendered to exactly ``cols_px`` x ``rows_px`` (the flat lid)."""
    doc = fitz.open(str(ai_path))
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(cols_px / page.rect.width, rows_px / page.rect.height), alpha=False)
    pixels = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:rows_px, :cols_px, :3]
    doc.close()
    Image.fromarray(np.ascontiguousarray(pixels), 'RGB').save(out_png)
    return out_png


def _every_finish(tmp_path):
    nodes = [_box('frame', 4.5, 4.5, 181.0, 1.0, '#C9A24B', [FOIL]), _disc('medal', 45.0, 70.0, 14.0, [FOIL]),
             _box('band', 100.0, 95.0, 60.0, 8.0, '#A9ABAE', [METALLIC]), _box('name', 100.0, 20.0, 60.0, 12.0, '#F3E9DA')]
    carriers = [_disc('medal-emboss', 45.0, 70.0, 14.0, [EMBOSS]), _box('name-emboss', 100.0, 20.0, 60.0, 12.0,
                                                                         '#F3E9DA', [EMBOSS]),
                _box('groove', 100.0, 50.0, 0.6, 30.0, '#3B1F3A', [DEBOSS]),
                _box('coat', 130.0, 50.0, 30.0, 20.0, '#3B1F3A', [SPOT_UV])]
    return _ai(tmp_path, 'every-finish', nodes, carriers=carriers)


# --- the finish proof ------------------------------------------------------------------------------------------------


# --- the label -------------------------------------------------------------------------------------------------------


# --- coverage --------------------------------------------------------------------------------------------------------


# --- the foil limits -------------------------------------------------------------------------------------------------


def _unlabelled(src, dst, page_number):
    """The file with one page's label removed (text only: the plate's drawing stays)."""
    import fitz
    doc = fitz.open(str(src))
    page = doc[page_number - 1]
    for x0, y0, x1, y1, *_rest in page.get_text('words'):
        page.add_redact_annot(fitz.Rect(x0, y0, x1, y1))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    doc.save(str(dst))
    doc.close()
    return dst


# --- line density ----------------------------------------------------------------------------------------------------

def _stripes(rows_px, cols_px, *, px_per_mm, pitch_mm, width_mm, angle_deg):
    y, x = np.mgrid[0:rows_px, 0:cols_px].astype(np.float64) / px_per_mm
    a = math.radians(angle_deg)
    across = x * math.cos(a) + y * math.sin(a)                      # distance across the stripes
    return np.mod(across, pitch_mm) < width_mm


# ======================================================================================================================
# Day 9: lettering — D-D9-5, the name as lettering (apps/ire/lettering.py): a logotype built by our engine from a
# licensed face's own outlines. On the house's own granted faces; DB-free, no provider called, $0.
# ======================================================================================================================

NAME = 'Enchanted Rose'
DIDONE = 'PlayfairDisplay-Italic[wght]@700'
ROMAN = 'PlayfairDisplay[wght]@700'
SCRIPT = 'GreatVibes-Regular'
OLDSTYLE = 'CormorantGaramond[wght]@700'
CFF_FACE = 'fonts_cinzel-decorative_cinzeldecorative-bold_424a03286933c3a8'
NON_EXEMPT = {'typography_surface': 'apps/ire/lettering.py::specimen'}
SWASH = {'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.08], 'c2_em': [0.9, -0.3],
         'to_em': [1.75, -0.14]}


def _contours(path) -> list:
    """A Path's segments split back into contours (mm, y down) of ('L', p0, p1) / ('C', p0, c1, c2, p3)."""
    out, segs, last = [], [], None
    for s in path.segments:
        if s.op == 'M':
            segs, last = [], (s.x, s.y)
        elif s.op == 'L':
            segs.append(('L', last, (s.x, s.y)))
            last = (s.x, s.y)
        elif s.op == 'C':
            segs.append(('C', last, (s.x1, s.y1), (s.x2, s.y2), (s.x, s.y)))
            last = (s.x, s.y)
        elif s.op == 'Z':
            out.append(segs)
    return out


def _doc(children):
    from apps.ire.graph import Document, Group
    return Document(page_w=190.0, page_h=60.0, title='lettering test', metadata=dict(NON_EXEMPT),
                    root=Group(name='root', role='artwork', children=list(children)))


# --- the face: licensed and granted, or refused by name -------------------------------------------------------------


# --- the drawn copy extracts as its words -------------------------------------------------------------------------


def test_actual_text_is_omitted_when_unset_and_no_span_is_written_for_a_group_without_it(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Group, Rect, SolidFill
    plain = Group(name='plain', children=[Rect(name='r', x=1, y=1, w=5, h=5,
                                               fill=SolidFill(color=Color.from_hex('#222222')))])
    assert 'actual_text' not in plain.model_dump() and 'actual_text' not in plain.model_dump_json()
    assert Group(name='named', actual_text=NAME).model_dump()['actual_text'] == NAME
    out = tmp_path / 'plain.ai'
    emit_pdf_ai(_doc([plain]), str(out))
    import fitz
    with fitz.open(str(out)) as pdf:
        assert b'/ActualText' not in pdf[0].read_contents()


# --- the outlines -------------------------------------------------------------------------------------------------


# --- the setting: the face's own GSUB, optical kerning ---------------------------------------------------------------


# --- the operations ------------------------------------------------------------------------------------------------


# ======================================================================================================================
# Day 9: arabic_display — D-D9-5, one Arabic display face made emitter-capable (``apps.ire.arabic_display``).
# Database-free: no test here touches the test database. The chosen face is El Messiri Bold, derived as "El Messiri PF"
# (``ElMessiriPF-Bold``) under ``var/fonts/derived``. ``var/`` is git-ignored, so the module fixture re-derives the same
# bytes where the folder holds none.
# ======================================================================================================================

ROOT = Path(__file__).resolve().parents[4]                                  # the repo
RECORD = ROOT / 'docs' / 'audit' / 'day-9' / 'fonts' / 'arabic-display.json'


# --- the derived face passes the emitter-capable check ----------------------------------------------------------------


# --- registered: the line face resolves to the derived bytes, the granted source verifies ----------------------------


# --- the engine draws the descriptor in it --------------------------------------------------------------------------


# --- the emitter way against raqm, above the threshold the measurements set ------------------------------------------


# --- provenance -------------------------------------------------------------------------------------------------------


# --- the instruments ----------------------------------------------------------------------------------------------------


# ======================================================================================================================
# Day 9: rich_plate — §4, the plate paths and the plate proof (``rich_plate``), on fixtures at the lid's own grid (1536
# × 970 at ≈ 8.08 px/mm); the structure is drawn by our engine (Document → .ai → raster). No provider is called: every
# edit and mark match is a fake, and so is every OCR read but one test's, which runs production's own reader (local
# tesseract, $0). DB-free.
# ======================================================================================================================

GROUND_HEX, GOLD_HEX = '#3C2837', '#D8B878'
NAME_INK = (236, 205, 150)
LINE_INK = (28, 10, 22)


def _no_words(png, *, lang, psm):
    return []


def _mark_far(png):
    return {'score': 0.1, 'box_mm': [10.0, 10.0, 30.0, 20.0]}


# --- colour ------------------------------------------------------------------------------------------------------

#: Sharma, Wu and Dalal (2005), Table 1: all 34 pairs (L1, a1, b1), (L2, a2, b2), ΔE00 — the hue-wrap pairs (9–16),
#: the zero-chroma pairs (7, 8) and the published colour pairs (25–34) included
SHARMA_2005 = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0010, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


# --- 1. clean_small ----------------------------------------------------------------------------------------------


# --- 2. and 3. the image edit --------------------------------------------------------------------------------------


# --- 4. the proof --------------------------------------------------------------------------------------------------


# ======================================================================================================================
# Day 9: jury — the jury (jury.py): rubric v2p, the finish proof beside the flat build, J1's desirability for the
# palette's audience (a "no" is a top issue, never a cap), the sketch ranking v2 and the idea check v2; the v1 and v2
# texts, Day 8's requests and Day 8's records unchanged. No provider is ever called: a paid call goes to a fake client
# through the real spend reservation (an isolated ledger in tmp, $0) or to a faked ``paid_operation``. DB-free.
# ======================================================================================================================

DAY8 = Path(__file__).resolve().parents[4] / 'docs' / 'audit' / 'day-8'

#: measured on jury.py before any Day 9 line: the sha256 of each text as UTF-8, of each schema as json.dumps(sort_keys)
DAY8_SHA256 = {
    'RUBRIC_V1': 'c2bc1b28737d69ee8d8a4423a5a484fd9734e1e4431b33b8d54d8521ca2ca258',
    'RUBRIC_V2': '96eb5bbc2d6bd0c784008ad5022e21675888ad47ec2568603819bd34a20e287a',
    'ROLE_J1': '7f41d803b79c52bb58b661be5aaef7d37b00674f03b9721617276fd637911c7e',
    'ROLE_J2': '83c08a12f31baf51f8ce199e006d8f7735eac94643e4b937fff76a30645d14f4',
    'ANSWER_WORDS': '5989ba72a1389353d0847fa44d509356f3074b9bb4941038e6e6046ee363b003',
    'RANK_SCHEMA': 'f6a15ffea6ee027141de296b7557677336ecb5ce5d996dbe14b11c0cfc974262',
    'IDEA_SCHEMA': '5940fb3ebdcf438e3a0d602800283d409ca02df8c66057f6f62c6b55ae4d19d5',
    'verdict_J1': '00e13dafa6f71fae07ad70857235504e99ccef565be2edde85416a60bf32e29f',
    'verdict_J2': '4de2998dbe789ab52edcc63942d8f314259234f66ae0e2e1c3fb418040fe9c46',
}
#: the requests Day 8's jury.py sent on the fixtures of ``test_v1_and_v2_calls_...`` (each image's data replaced by a
#: placeholder: the texts, their order, the schemas and the cache breakpoints remain), measured by running the pre-edit
#: module with ``paid_operation`` faked
DAY8_REQUEST_SHA256 = {
    'ask/J1/v1': '2aa6399a627c5ba141f9058848712dae14f58c92d4cecf92eb5609d8919765e4',
    'ask/J1/v2': '5ff2738da38cbcf89fabd667cdd90b1d418383b010dc1112717db1981de30bc9',
    'ask/J2/v1': 'e0a488db8e9df6589eac0e4c3298ea7879e31bd92b78dea0f7e52668a8ef71a4',
    'ask/J2/v2': 'ba54834336fa40ee277896d9c52a154c36851d7139a51f1cbcc29de6441cb15c',
    'rank_sketches/v2': '9deaa9e0d610a2b73c459843bf5737edd19641c67bda5f91340b413d06ca30e4',
    'idea_check/v2': '38eb153f5d37d94258e880f1f59e5f86376accc61aaa398004ad47d59ba7ccf9',
}
PROOF_SENTENCE = ('Candidates come as the flat print artwork and its finish proof, which renders the planned finishes; '
                  'judge the design as it will be manufactured, never the rendering.')
AUDIENCE = 'women 18–30, dreamy, magical, bold make-up lovers in Amman, Beirut, Damascus, Ramallah and Tunis'
DESIRABILITY = ('would_buy_partly_for_the_lid', 'would_photograph_it', 'desirability_why')
#: keywords the provider's structured outputs reject or that would grow the grammar; none may reach the API
NO_LENGTH_KEYWORDS = {'maxItems', 'minItems', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'minLength',
                      'maxLength', 'uniqueItems', 'multipleOf'}


# --- fixtures and fakes ----------------------------------------------------------------------------------------------

def png(folder, name, colour, size):
    path = Path(folder) / name
    Image.new('RGB', size, colour).save(path)
    return path


sha = _sha                                  # the file's one sha256 helper, by the name the jury tests use


def image_bytes(block):
    return base64.b64decode(block['source']['data'])


def canonical(request):
    """The sha256 of a request with every image's data replaced by a placeholder."""
    def strip(node):
        if isinstance(node, dict):
            if node.get('type') == 'image':
                return dict(node, source=dict(node['source'], data='<image>'))
            return {k: strip(v) for k, v in node.items()}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return hashlib.sha256(json.dumps(strip(request), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def walk(schema):
    """Every dict node of a schema, depth first."""
    stack, nodes = [schema], []
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            nodes.append(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return nodes


def objects(schema):
    return [n for n in walk(schema) if n.get('type') == 'object']


def no_default_client():
    raise AssertionError('the default Anthropic client was built: the injected client must make the call')


class Answer:
    """A provider response as the SDK shapes it: text blocks, a stop reason and ``model_dump`` with the usage."""

    def __init__(self, payload, stop_reason='end_turn', text=None):
        self.stop_reason = stop_reason
        self.content = [SimpleNamespace(type='text', text=json.dumps(payload) if text is None else text)]

    def model_dump(self, mode='json'):
        return {'stop_reason': self.stop_reason, 'usage': {'input_tokens': 1200, 'output_tokens': 400,
                                                           'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}}


class FakeClient:
    """The injected provider client: ``messages.create`` records each request and returns the next queued answer. It never
    opens a socket (the conftest's outbound guard would refuse one)."""

    def __init__(self, *answers):
        self.requests, self.answers = [], list(answers)
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **request):
        self.requests.append(request)
        answer = self.answers.pop(0)
        return answer if isinstance(answer, Answer) else Answer(answer)


def verdict_answer(score, **extra):
    """A juror's answer as the provider returns it: the dimensions as rows, the pairwise as four vs_ fields."""
    answer = {'dimensions': [{'dimension': k, 'score': score, 'observation': 'seen', 'location': 'lid', 'repair': 'none'}
                             for k in DIMENSIONS],
              'hard_failures': [], 'banned_motif_seen': '', 'near_copy_of': '', 'observations': 'ok',
              'idea_read': 'an engraved night sky with foil stars', 'idea_matches_direction': True, 'would_remove': '',
              'ai_or_template_signs': '', 'reads_first': 'name', 'reads_second': 'ornament', 'reads_third': 'foil',
              'vs_launched_a': 'similar', 'vs_launched_b': 'similar', 'vs_rejected_a': 'clearly_better',
              'vs_rejected_b': 'clearly_better', 'top_issues': []}
    answer.update(extra)
    return answer


def payload(score, **extra):
    """A juror's payload as ``ask`` records it (normalised), as in Day 8's tests."""
    base = {'dimensions': {k: {'score': score, 'observation': 'seen', 'location': 'lid', 'repair': 'none'} for k in DIMENSIONS},
            'hard_failures': [], 'banned_motif_seen': '', 'near_copy_of': '', 'observations': 'ok',
            'idea_read': 'an engraved night sky', 'idea_matches_direction': True, 'would_remove': '',
            'ai_or_template_signs': '', 'reads_first': 'name', 'reads_second': 'mark', 'reads_third': 'device',
            'pairwise': {'launched_a': 'similar', 'launched_b': 'similar', 'rejected_a': 'clearly_better',
                         'rejected_b': 'clearly_better'},
            'top_issues': [], 'looks_easy_to_make': False, 'carries_collection': True,
            'foil_and_blind_lines_legible': True, 'printability_note': ''}
    base.update(extra)
    return base


def record(p):
    return {'payload': p, 'model': 'test-model', 'cost_usd': 0.0}


def rank_row(sketch, rank):
    return {'sketch': sketch, 'rank': rank, 'score': 8.5 - rank / 2, 'why': 'w', 'banned_motif_seen': '',
            'copy_present': True, 'ai_artefacts': '', 'would_buy_partly_for_the_lid': rank == 1,
            'would_photograph_it': True, 'desirability_why': 'd', 'must_rebuild': ['lettering', 'foil_or_metallic'],
            'richness_survives_rebuild': rank != 3, 'buildability_why': 'b'}


# --- v1 and v2 unchanged; v2p ----------------------------------------------------------------------------------------


# --- the finish proof (D-D9-6) ---------------------------------------------------------------------------------------


# --- desirability (D-D9-7) -------------------------------------------------------------------------------------------


# --- the sketch ranking v2 and the idea check v2 --------------------------------------------------------------------


# --- Day 8's records replay unchanged --------------------------------------------------------------------------------


# ======================================================================================================================
# Day 9: day9_pick — §6, the pick page: Day 9's round on top, Day 8 below and unchanged. The fixtures go through the
# real producers: every verdict is ``jury.combine``'s own on reviews in ``jury``'s field names, every ranking is written
# by ``jury.rank_sketches_v2`` itself on a fake answer (``jury.paid_operation`` replaced — no provider, no ledger, $0).
# Every test name carries ``day9pick`` (run with ``-k day9pick``); the page tests use the database, the rest do not.
# ======================================================================================================================

LID_PX = (1536, 970)
NAME_PX, ARABIC_PX = (1200, 240), (600, 120)          # at 600 dpi: 50.8 × 10.16 mm and 25.4 × 5.08 mm
DESIRE_WHY = 'She would keep the lid on her vanity, but the foil reads flat in a phone picture.'
DESIRE_ANSWER = {'would_buy_partly_for_the_lid': True, 'would_photograph_it': False, 'desirability_why': DESIRE_WHY}
DESIRE = {'would_buy_partly_for_the_lid': True, 'would_photograph_it': False, 'why': DESIRE_WHY}   # as the record keeps it
FINISH = {'foil_metallic_pct': 12.4, 'relief_pct': 6.0, 'lines_per_cm_densest': 14.2, 'foil_limits_hold': True}
PROOF = {'build': 'B3-r2', 'before_stricter_mean': 6.65, 'after_stricter_mean': 7.1, 'delta': 0.45, 'rubric': 'v2p',
         'jury_spread_note': "The jury's own spread on a repeat is 0.3."}


def _payload(score, juror, cid):
    """A juror's complete review as ``jury.ask`` keeps it (normalised), every dimension at ``score``; J1 answers the
    desirability questions in ``jury.DESIRABILITY_FIELDS``."""
    rows = {n: {'score': score, 'observation': f'{juror} sees {n} on {cid}', 'location': 'the whole lid',
                'repair': f'{juror} lifts {n}'} for n in DIMENSIONS}
    payload = {'dimensions': rows, 'hard_failures': [], 'banned_motif_seen': '', 'near_copy_of': '',
               'observations': f'{juror} on {cid}', 'idea_read': 'an engraved field under a painted ground',
               'idea_matches_direction': True, 'would_remove': '', 'ai_or_template_signs': '',
               'reads_first': 'the name', 'reads_second': 'the ornament', 'reads_third': 'the mark',
               'pairwise': {'launched_a': 'similar', 'launched_b': 'similar', 'rejected_a': 'clearly_better',
                            'rejected_b': 'clearly_better'},
               'top_issues': [{'observation': f'{juror} finding on {cid}', 'location': 'upper third',
                               'repair': f'{juror} repair on {cid}'}]}
    if juror == 'J1':
        payload.update(looks_easy_to_make=False, carries_collection=True, **DESIRE_ANSWER)
    else:
        payload.update(foil_and_blind_lines_legible=True, printability_note='holds on press')
    return payload


def _png(path, size, colour):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, colour).save(path)
    return path


def _row(number, rank, score):
    """One sketch's row in ``jury.RANK_SCHEMA_V2``'s own flat fields."""
    return {'sketch': number, 'rank': rank, 'score': score, 'why': f'sketch {number} ranked {rank}',
            'banned_motif_seen': '', 'copy_present': True, 'ai_artefacts': '',
            'would_buy_partly_for_the_lid': rank == 1, 'would_photograph_it': True, 'desirability_why': 'jewel-like',
            'must_rebuild': ['geometric_structure', 'foil_or_metallic'], 'richness_survives_rebuild': True,
            'buildability_why': 'the ground carries the richness'}


class _Answer:
    """A provider's response as ``jury._ask_j1`` reads it."""

    def __init__(self, text, stop_reason):
        self.content, self.stop_reason = [SimpleNamespace(type='text', text=text)], stop_reason

    def model_dump(self, mode='json'):
        return {'usage': {'input_tokens': 10, 'output_tokens': 10}}


A_SKETCHES = ['A-1.1', 'A-1.2', 'A-2.1']


# --- the record ------------------------------------------------------------------------------------------------------


# --- the page (database) ---------------------------------------------------------------------------------------------

def _day8(root):
    """Day 8's own page fixture (test_day8_concepts._pick_fixture, copied): one concept below the bar, pinned."""
    files = {}
    for rel, colour in (('concepts/X1/truthful.png', (43, 23, 41)), ('concepts/X1/name-1to1.png', (250, 243, 236)),
                        ('concepts/X1/arabic-1to1.png', (250, 243, 236)), ('concepts/X1/finish-sheet.png', (246, 246, 246)),
                        ('sketches/X1/lid.png', (43, 23, 41))):
        p = _png(root / rel, (40, 25), colour)
        files[rel] = _sha(p)
    pin = lambda rel, mime='image/png': {'path': rel, 'sha256': files[rel], 'mime': mime, 'words': rel}
    record = {'schema': 'day8_pick/1.0', 'gate': 'rubric v2 · mean ≥ 8', 'calibration': {'gate_rubric': 'v2'},
              'passing': [], 'below_the_bar': ['X1'], 'top_three_overall': ['X1'],
              'concepts': [{'id': 'X1', 'direction': 'A', 'name': 'Gravure', 'role': 'trend-led', 'idea': 'One line of rose-gold light.',
                            'story': 'story', 'option': {}, 'sketch': 'X1', 'status': None, 'passes': False,
                            'raw_means': {'J1': 7.1, 'J2': 7.4}, 'stricter_mean': 7.0, 'capped_mean': 6.8,
                            'scores': {'beauty': {'J1': 7, 'J2': 8, 'stands': 7}}, 'caps': [], 'hard_failures': [],
                            'top_issues': [{'observation': 'the hero line is thin at 2 m', 'location': 'centre', 'repair': 'widen it'}],
                            'reads': {'J1': ['name', 'line', 'mark'], 'J2': ['name', 'line', 'mark']}, 'idea_read': {'J1': 'a line', 'J2': 'a line'},
                            'checks': {'checks': [{'check': 'name cap height ≥ 7 mm', 'value': 11.0, 'holds': True}], 'issues': []},
                            'designer_eye': ['name: as sketched'], 'fonts': [{'role': 'Latin display', 'family': 'Instrument Serif', 'stem': 'InstrumentSerif-Regular', 'licence': 'SIL Open Font License, Version 1.1'}],
                            'takes': {'house_dna': 'gold rules'}, 'extends': {'lipstick': 'the hero line as its base ring'}, 'finishes': [{'finish': 'hot foil, rose gold', 'on': 'the hero line'}],
                            'proposals_flagged': [], 'repairs': {}, 'name_crop_width_mm': 84.0, 'arabic_crop_width_mm': 33.0,
                            'files': {'truthful': 'X1-truthful', 'name': 'X1-name', 'arabic': 'X1-arabic', 'finishes': 'X1-finishes'}}],
              'sketches': [{'id': 'X1', 'direction': 'A', 'choices': {}, 'rank': 1, 'score': 7.5, 'why': 'calm', 'went_on': True, 'copy': [], 'file': 'sketch-X1'}],
              'anchors': [{'brand': 'Hourglass', 'product': 'Curator', 'page': 'https://example.com/curator', 'role': 'fixed'}],
              'downloads': {'X1-truthful': pin('concepts/X1/truthful.png'), 'X1-name': pin('concepts/X1/name-1to1.png'),
                            'X1-arabic': pin('concepts/X1/arabic-1to1.png'), 'X1-finishes': pin('concepts/X1/finish-sheet.png'),
                            'sketch-X1': pin('sketches/X1/lid.png')}}
    (root / 'pick').mkdir(parents=True, exist_ok=True)
    (root / 'pick' / 'publication.json').write_text(json.dumps(record))
    return root


@pytest.fixture
def owner(client):
    from django.contrib.auth.models import User
    client.force_login(User.objects.create_superuser('owner9', 'o9@example.com', 'pw'))
    return client


