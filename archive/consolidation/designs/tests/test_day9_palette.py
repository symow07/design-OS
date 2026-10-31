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

from apps.ire import arabic_display as AD
from apps.ire import font_instances, font_roles
from apps.ire import lettering as L
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import ClosePath, Color, CubicTo, Document, Finish, Group, LineTo, MoveTo, SolidFill, TextRun
from apps.ire.graph import Path as VPath           # the engine's vector path; ``Path`` is pathlib's throughout
from apps.pipeline.services import day9_pick, jury
from apps.pipeline.services import finish_proof as fp
from apps.pipeline.services import image_guard as ig
from apps.pipeline.services import rich_plate as rp
from apps.pipeline.services import truthful_concept as tc
from apps.pipeline.services.concept_quality import DIMENSIONS
from apps.pipeline.services.day6_critic import critic_image_bytes


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

def test_the_finish_proof_is_deterministic_and_says_what_it_read(tmp_path):
    ai = _every_finish(tmp_path)
    flat = _flat(ai, tmp_path / 'flat.png', cols_px=380, rows_px=240)
    first = fp.render_proof(flat, ai, tmp_path / 'one.png')
    second = fp.render_proof(flat, ai, tmp_path / 'two.png')
    one, two = (tmp_path / 'one.png').read_bytes(), (tmp_path / 'two.png').read_bytes()
    assert one == two
    assert first['out']['sha256'] == second['out']['sha256'] == hashlib.sha256(one).hexdigest()
    assert {(p['plate'], p['kind']) for p in first['plates']} == {
        ('FOIL_GOLD', 'foil'), ('METALLIC_9244C', 'metallic_ink'), ('EMBOSS', 'emboss'), ('DEBOSS', 'deboss'),
        ('SPOT_UV', 'spot_uv')}
    assert first['seeds'] == fp.SEEDS and first['light']['azimuth_deg'] == fp.SOFTBOX.azimuth_deg
    assert first['light']['kind'] == 'one fixed softbox' and first['out']['size_px'] == [380, 240]
    assert all(p['rendered_as'] for p in first['plates'])
    assert first['metals'][0]['metal'] is not None
    with Image.open(tmp_path / 'one.png') as im:
        assert im.size == (380, 240) and im.mode == 'RGB' and not im.info.get('dpi')


def test_bare_board_changes_only_by_its_texture_and_the_finishes_change_it(tmp_path):
    ai = _every_finish(tmp_path)
    flat = _flat(ai, tmp_path / 'flat.png', cols_px=760, rows_px=480)
    fp.render_proof(flat, ai, tmp_path / 'proof.png')
    before = np.asarray(Image.open(flat), dtype=np.int16)
    after = np.asarray(Image.open(tmp_path / 'proof.png'), dtype=np.int16)
    px_per_mm = 760 / LID_W_MM
    bare = np.zeros(before.shape[:2], bool)
    bare[int(80 * px_per_mm):int(115 * px_per_mm), int(10 * px_per_mm):int(28 * px_per_mm)] = True   # no plate near
    assert np.abs(after - before)[bare].max() <= 8                  # the board's texture, nothing else
    medal = (slice(int(62 * px_per_mm), int(78 * px_per_mm)), slice(int(37 * px_per_mm), int(53 * px_per_mm)))
    assert np.abs(after - before)[medal].mean() > 8                 # the foil is rendered as metal


def test_a_blind_relief_the_flat_paints_is_rendered_as_page_1_prints_it_and_foil_keeps_the_flats_colour(tmp_path):
    # Day 8's way: a blind deboss groove (no ink: a zero-opacity carrier), an inked emboss (a cream bar), a foil disc
    carriers = [_box('groove', 60.0, 30.0, 1.2, 60.0, '#3B1F3A', [DEBOSS]),
                _box('bar-emboss', 110.0, 40.0, 50.0, 12.0, '#F3E9DA', [EMBOSS])]
    nodes = [_box('bar', 110.0, 40.0, 50.0, 12.0, '#F3E9DA'), _disc('disc', 150.0, 90.0, 10.0, [FOIL])]
    ai = _ai(tmp_path, 'blind', nodes, carriers=carriers)
    cols_px, rows_px = 760, 480
    px_per_mm = cols_px / LID_W_MM
    clean = _flat(ai, tmp_path / 'clean.png', cols_px=cols_px, rows_px=rows_px)
    # the preview's conventions, painted into the flat: the blind groove drawn tone on tone (page 1 prints nothing
    # there), smeared 2 px past the plate as a flat's resampling smears a line; the foil drawn a lighter gold than page
    # 1's appearance colour
    painted = np.asarray(Image.open(clean)).copy()
    groove = (slice(int(30.0 * px_per_mm), int(90.0 * px_per_mm)), slice(int(60.0 * px_per_mm), int(61.2 * px_per_mm)))
    smeared = (groove[0], slice(groove[1].start - 2, groove[1].stop + 2))
    painted[smeared] = (10, 4, 10)
    y_mm, x_mm = (np.mgrid[0:rows_px, 0:cols_px] + 0.5) / px_per_mm
    disc = (x_mm - 150.0) ** 2 + (y_mm - 90.0) ** 2 <= 9.5 ** 2
    painted[disc] = (230, 200, 120)
    Image.fromarray(painted).save(tmp_path / 'painted.png')
    record = fp.render_proof(tmp_path / 'painted.png', ai, tmp_path / 'painted-proof.png')
    fp.render_proof(clean, ai, tmp_path / 'clean-proof.png')
    against = record['flat_against_page_1']
    rows = {row['plate']: row for row in against['plates']}
    assert rows['DEBOSS']['differs_pct'] > fp.FLAT_DEPICTS_PCT and rows['DEBOSS']['page_1_taken'] is True
    assert rows['EMBOSS']['differs_pct'] == 0.0 and rows['EMBOSS']['page_1_taken'] is False   # the inked emboss
    assert rows['FOIL_GOLD']['differs_pct'] > fp.FLAT_DEPICTS_PCT and rows['FOIL_GOLD']['page_1_taken'] is False
    assert any('DEBOSS' in line and 'page 1' in line for line in against['said'])
    assert against['residual_differs_pct'] < against['lid_differs_pct']
    # the groove is rendered as the press makes it: the painted tone leaves no trace, the relief is still there
    with_paint = np.asarray(Image.open(tmp_path / 'painted-proof.png'), dtype=np.int16)
    without = np.asarray(Image.open(tmp_path / 'clean-proof.png'), dtype=np.int16)
    near = (slice(int(28.0 * px_per_mm), int(92.0 * px_per_mm)), slice(int(57.0 * px_per_mm), int(64.0 * px_per_mm)))
    assert np.abs(with_paint - without)[near].max() <= 2
    ground = np.asarray(Image.open(clean), dtype=np.int16)
    assert np.abs(with_paint - ground)[groove].mean() > 2              # the groove is shaded, not left flat
    assert np.abs(with_paint - np.array([10, 4, 10]))[smeared].mean() > 30
    # the foil keeps the flat's colour: its metal is read from the flat (the median under the plate), never swapped
    assert record['metals'] == [{'plate': 'FOIL_GOLD', 'metal': '#E6C878'}]


def test_a_framed_flat_is_refused_never_stretched(tmp_path):
    ai = _every_finish(tmp_path)
    framed = tmp_path / 'framed.png'
    Image.new('RGB', (384, 256), (59, 31, 58)).save(framed)          # 1536 x 1024 in proportion
    with pytest.raises(ValueError, match='proportion'):
        fp.render_proof(framed, ai, tmp_path / 'proof.png')
    assert not (tmp_path / 'proof.png').exists()


def test_nothing_is_written_under_day_8(tmp_path, monkeypatch):
    pinned = tmp_path / 'docs' / 'audit' / 'day-8'
    pinned.mkdir(parents=True)
    monkeypatch.setattr(fp, 'DAY8_AUDIT', pinned)
    ai = _every_finish(tmp_path)
    flat = _flat(ai, tmp_path / 'flat.png', cols_px=380, rows_px=240)
    with pytest.raises(PermissionError, match='hash-pinned'):
        fp.render_proof(flat, ai, pinned / 'concepts' / 'X' / 'finish-proof.png')
    with pytest.raises(PermissionError, match='hash-pinned'):
        fp.prove_build(flat, ai, pinned / 'concepts' / 'X')
    assert list(pinned.rglob('*')) == []


# --- the label -------------------------------------------------------------------------------------------------------

def test_the_label_is_never_counted_as_foil_and_a_foil_under_it_is_kept_whole(tmp_path):
    # a foil rule runs right through the label's own box (x 4-63 mm, y 3.7-6.7 mm); nothing else is foil
    ai = _ai(tmp_path, 'under-the-label', [_box('rule', 2.0, 4.5, 186.0, 1.0, '#C9A24B', [FOIL])])
    record = fp.coverage(ai)
    (row,) = record['plates']
    assert (row['plate'], row['kind'], row['page']) == ('FOIL_GOLD', 'foil', 2)
    assert row['area_mm2'] == pytest.approx(186.0, rel=0.005)       # the rule whole, and no label
    x0, y0, x1, y1 = row['label_box_mm']
    assert x0 == pytest.approx(4.0, abs=0.05) and 3.0 < y0 < 4.5 and 6.0 < y1 < 7.5 and x1 > 40.0
    (mask_row,) = fp.plate_masks(ai, px_per_mm=20.0)
    mask = mask_row['mask']
    label_rows = slice(int(y0 * 20), int(4.4 * 20))                  # the label's box above the rule
    assert not mask[label_rows, int(x0 * 20):int(x1 * 20)].any()
    assert mask[int(5.0 * 20), int(10 * 20):int(180 * 20)].all()   # the rule under the label, unbroken
    limits = fp.foil_limits(ai)
    assert limits['holds'] and limits['foil_plates'][0]['foil_area_mm2'] == pytest.approx(186.0, rel=0.005)


def test_a_plate_page_is_named_and_kinded_by_its_label_alone(tmp_path):
    ai = _every_finish(tmp_path)
    read = fp._read_plates(ai)
    try:
        assert [(p.plate, p.kind, p.page) for p in read.plates] == [
            ('FOIL_GOLD', 'foil', 2), ('METALLIC_9244C', 'metallic_ink', 3), ('EMBOSS', 'emboss', 4),
            ('DEBOSS', 'deboss', 5), ('SPOT_UV', 'spot_uv', 6)]
        for plate in read.plates:                                     # the label's words are gone from the page
            assert 'FINISH PLATE' not in read.doc[plate.page - 1].get_text()
    finally:
        read.doc.close()
    assert 'FINISH PLATE' in fitz.open(str(ai))[1].get_text()       # and the file on disk is untouched


def test_a_plates_own_lettering_is_kept_and_lettering_under_the_label_is_refused(tmp_path):
    word = TextRun(name='word', text='ROSE', x=60.0, y=60.0, size_pt=48.0, color=GOLD, finishes=[FOIL])
    ai = _ai(tmp_path, 'lettered', [word])
    read = fp._read_plates(ai)
    try:
        assert 'ROSE' in read.doc[1].get_text() and 'FINISH PLATE' not in read.doc[1].get_text()
    finally:
        read.doc.close()
    under = TextRun(name='under', text='FOIL WORDS UNDER THE LABEL', x=4.0, y=6.0, size_pt=6.0, color=GOLD,
                    finishes=[FOIL])
    with pytest.raises(RuntimeError, match='lettering'):
        fp.coverage(_ai(tmp_path, 'under', [under]))


# --- coverage --------------------------------------------------------------------------------------------------------

def test_coverage_reads_known_areas_within_half_a_per_cent_and_unions_the_relief(tmp_path):
    nodes = [_box('foil-a', 20.0, 20.0, 40.0, 30.0, '#C9A24B', [FOIL]), _disc('foil-b', 140.0, 40.0, 10.0, [FOIL]),
             _box('ink', 20.0, 80.0, 20.0, 10.0, '#A9ABAE', [METALLIC])]
    carriers = [_box('raised', 80.0, 60.0, 50.0, 40.0, '#3B1F3A', [EMBOSS]),
                _box('sunk', 120.0, 60.0, 30.0, 40.0, '#3B1F3A', [DEBOSS])]
    record = fp.coverage(_ai(tmp_path, 'known', nodes, carriers=carriers))
    by = {row['plate']: row for row in record['plates']}
    foil_mm2 = 40.0 * 30.0 + math.pi * 10.0 ** 2
    assert by['FOIL_GOLD']['area_mm2'] == pytest.approx(foil_mm2, rel=0.005)
    assert by['FOIL_GOLD']['area_pct'] == pytest.approx(foil_mm2 / LID_MM2 * 100.0, rel=0.005)
    assert by['METALLIC_9244C']['area_mm2'] == pytest.approx(200.0, rel=0.005)
    assert by['EMBOSS']['area_mm2'] == pytest.approx(2000.0, rel=0.005)
    assert by['DEBOSS']['area_mm2'] == pytest.approx(1200.0, rel=0.005)
    assert record['foil_and_metallic_pct'] == pytest.approx((foil_mm2 + 200.0) / LID_MM2 * 100.0, rel=0.005)
    # the relief is a union: the deboss overlaps the emboss over 10 x 40 mm, counted once
    assert record['relief_pct'] == pytest.approx((2000.0 + 1200.0 - 400.0) / LID_MM2 * 100.0, rel=0.005)
    assert record['meets_d9_3'] is False and record['met_by'] == []


def test_coverage_meets_d9_3_by_metal_or_by_relief(tmp_path):
    metal = fp.coverage(_ai(tmp_path, 'metal', [_box('foil', 10.0, 10.0, 60.0, 40.0, '#C9A24B', [FOIL])]))
    assert metal['foil_and_metallic_pct'] == pytest.approx(2400.0 / LID_MM2 * 100.0, rel=0.005)
    assert metal['meets_d9_3'] is True and metal['met_by'] == ['metal']
    relief = fp.coverage(_ai(tmp_path, 'relief', [], carriers=[_box('raised', 10.0, 10.0, 100.0, 36.0, '#3B1F3A',
                                                                    [EMBOSS])]))
    assert relief['relief_pct'] == pytest.approx(3600.0 / LID_MM2 * 100.0, rel=0.005)
    assert relief['meets_d9_3'] is True and relief['met_by'] == ['relief']


# --- the foil limits -------------------------------------------------------------------------------------------------

def test_foil_limits_find_a_005_mm_line_and_a_012_mm_gap(tmp_path):
    nodes = [_bar('thin', 60.0, 30.0, 20.0, 0.05, 0.0, [FOIL]),
             _box('left', 90.0, 55.0, 20.0, 10.0, '#C9A24B', [FOIL]),
             _box('right', 110.12, 55.0, 15.0, 10.0, '#C9A24B', [FOIL])]
    record = fp.foil_limits(_ai(tmp_path, 'too-fine', nodes))
    assert record['holds'] is False
    (plate,) = record['foil_plates']
    assert plate['thin']['parts'] == 1 and plate['thin']['area_mm2'] == pytest.approx(0.05 * 20.0, rel=0.1)
    tx0, ty0, tx1, ty1 = plate['thin']['boxes_mm'][0]['box_mm']
    assert tx0 == pytest.approx(50.0, abs=0.1) and tx1 == pytest.approx(70.0, abs=0.1)
    assert ty0 == pytest.approx(29.975, abs=0.05) and ty1 == pytest.approx(30.025, abs=0.05)
    assert plate['gaps']['parts'] == 1 and plate['gaps']['area_mm2'] == pytest.approx(0.12 * 10.0, rel=0.1)
    gx0, gy0, gx1, gy1 = plate['gaps']['boxes_mm'][0]['box_mm']
    assert gx0 == pytest.approx(110.0, abs=0.05) and gx1 == pytest.approx(110.12, abs=0.05)
    assert gy0 == pytest.approx(55.0, abs=0.1) and gy1 == pytest.approx(65.0, abs=0.1)


def test_foil_limits_pass_015_mm_lines_with_03_mm_gaps(tmp_path):
    upright = [_bar('bar-%d' % i, 40.0 + i * 0.45, 40.0, 15.0, 0.15, 90.0, [FOIL]) for i in range(30)]
    turned = [_bar('turned-%d' % i, 120.0 + i * 0.45 * math.cos(math.radians(120.0)),
                   80.0 + i * 0.45 * math.sin(math.radians(120.0)), 15.0, 0.15, 30.0, [FOIL]) for i in range(30)]
    record = fp.foil_limits(_ai(tmp_path, 'fine-enough', upright + turned))
    assert record['holds'] is True
    (plate,) = record['foil_plates']
    assert plate['thin']['parts'] == 0 and plate['gaps']['parts'] == 0
    # what the rule left out is the disk's own rounding of the bars' corners: counted, small, and said
    assert plate['thin']['ignored']['pieces'] > 0 and plate['thin']['ignored']['longest_mm'] < 0.2


def test_a_part_cut_by_the_tiles_is_one_part_and_parts_side_by_side_stay_apart(tmp_path):
    # the limits are read in 2048 px tiles (26 mm at 2000 dpi): a 0.05 mm line from 10 to 60 mm crosses two seams
    long_line = [_bar('long', 35.0, 30.0, 50.0, 0.05, 0.0, [FOIL])]
    plate = fp.foil_limits(_ai(tmp_path, 'across-seams', long_line))['foil_plates'][0]
    assert plate['thin']['parts'] == 1
    x0, _y0, x1, _y1 = plate['thin']['boxes_mm'][0]['box_mm']
    assert x0 == pytest.approx(10.0, abs=0.05) and x1 == pytest.approx(60.0, abs=0.05)
    # eleven diagonal bars 0.88 mm wide at a 1 mm pitch: ten 0.12 mm slits whose boxes all overlap, ten parts
    bars = [_bar('bar-%d' % i, 120.0 + i * math.cos(math.radians(135.0)), 60.0 + i * math.sin(math.radians(135.0)),
                 12.0, 0.88, 45.0, [FOIL]) for i in range(11)]
    plate = fp.foil_limits(_ai(tmp_path, 'slits', bars))['foil_plates'][0]
    assert plate['gaps']['parts'] == 10 and plate['thin']['parts'] == 0


def test_the_anti_aliasing_tolerance_is_explicit_and_cuts_both_ways(tmp_path):
    assert fp.AA_TOLERANCE_PX == 1.0
    # exactly at the limits, at every angle and sub-pixel phase: a 0.1 mm line and a 0.2 mm gap hold
    lines = [_bar('line-%d' % i, 12.0 + (i % 8) * 22.0 + 0.0037 * i, 20.0 + (i // 8) * 30.0 + 0.0053 * i, 16.0, 0.1,
                  angle, [FOIL]) for i, angle in enumerate(range(0, 91, 6))]
    record = fp.foil_limits(_ai(tmp_path, 'at-the-line-limit', lines))
    assert record['holds'] is True
    assert record['tolerance']['aa_tolerance_px'] == fp.AA_TOLERANCE_PX
    assert record['tolerance']['line_disk_mm'] == pytest.approx(0.1 - fp.AA_TOLERANCE_PX * 25.4 / 2000.0, abs=1e-3)
    assert record['tolerance']['gap_disk_mm'] == pytest.approx(0.2 - fp.AA_TOLERANCE_PX * 25.4 / 2000.0, abs=1e-3)
    gaps = []
    for i, angle in enumerate((0, 17, 45, 72)):
        a = math.radians(angle)
        px, py = -math.sin(a), math.cos(a)
        cx, cy, off = 30.0 + i * 42.0, 60.0, 3.0 + 0.1
        gaps += [_bar('a-%d' % i, cx - px * off, cy - py * off, 14.0, 6.0, angle, [FOIL]),
                 _bar('b-%d' % i, cx + px * off, cy + py * off, 14.0, 6.0, angle, [FOIL])]
    assert fp.foil_limits(_ai(tmp_path, 'at-the-gap-limit', gaps))['holds'] is True
    # below each limit by more than twice the tolerance: a 0.07 mm line and a 0.17 mm gap fail, at every angle
    for angle in (0, 17, 45):
        a = math.radians(angle)
        px, py = -math.sin(a), math.cos(a)
        nodes = [_bar('line', 40.0, 30.0, 20.0, 0.07, angle, [FOIL]),
                 _bar('a', 120.0 - px * 3.085, 70.0 - py * 3.085, 14.0, 6.0, angle, [FOIL]),
                 _bar('b', 120.0 + px * 3.085, 70.0 + py * 3.085, 14.0, 6.0, angle, [FOIL])]
        plate = fp.foil_limits(_ai(tmp_path, 'below-%d' % angle, nodes))['foil_plates'][0]
        assert plate['thin']['parts'] == 1 and plate['gaps']['parts'] == 1, (angle, plate)


def test_a_plain_foil_rectangle_holds_and_metallic_ink_is_reported_apart(tmp_path):
    nodes = [_box('foil', 20.0, 20.0, 80.0, 50.0, '#C9A24B', [FOIL]),
             _bar('hairline', 130.0, 60.0, 30.0, 0.04, 0.0, [METALLIC])]
    record = fp.foil_limits(_ai(tmp_path, 'plain', nodes))
    assert record['holds'] is True
    assert [p['plate'] for p in record['foil_plates']] == ['FOIL_GOLD']
    (ink,) = record['metallic_ink_plates']
    assert ink['plate'] == 'METALLIC_9244C' and ink['limit'].startswith('none')
    assert ink['area_mm2'] == pytest.approx(30.0 * 0.04, rel=0.05)
    # no foil plate read is not measured — never a pass on nothing — unless the caller says the build draws no foil
    nothing = fp.foil_limits(_ai(tmp_path, 'no-foil', []))
    assert nothing['holds'] is None and nothing['said'] == 'not measured: no foil plate read'
    assert fp.foil_limits(_ai(tmp_path, 'no-foil-said', []), foil_drawn=False)['holds'] is True
    assert fp.foil_limits(_ai(tmp_path, 'no-foil-drawn', []), foil_drawn=True)['said'].endswith('though the build draws foil')


def test_a_diagonal_hairline_or_gap_is_judged_on_its_length_not_its_box(tmp_path):
    """A part's run was its box's side, so a 45 degree hairline or gap up to 1.41 times the run was ignored (the
    verifier's fixtures: a 0.06 mm line 0.215 mm long, a 0.12 mm gap 0.45 mm long)."""
    for angle in (0.0, 45.0):
        hair = fp.foil_limits(_ai(tmp_path, 'hair-%d' % angle, [_bar('hair', 60.0, 30.0, 0.215, 0.06, angle, [FOIL])]))
        assert hair['holds'] is False and hair['foil_plates'][0]['thin']['parts'] == 1, angle
        a = math.radians(angle)
        px, py = -math.sin(a) * 1.12, math.cos(a) * 1.12               # two 1 mm bars 0.12 mm apart across their width
        gap = fp.foil_limits(_ai(tmp_path, 'gap-%d' % angle, [_bar('a', 100.0, 60.0, 0.45, 1.0, angle, [FOIL]),
                                                             _bar('b', 100.0 + px, 60.0 + py, 0.45, 1.0, angle, [FOIL])]))
        assert gap['holds'] is False and gap['foil_plates'][0]['gaps']['parts'] == 1, angle
        assert 'over the limits: FOIL_GOLD' in gap['said']


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


def test_an_unlabelled_plate_is_refused_never_read_as_no_finish(tmp_path):
    """A plate page whose label is gone was skipped unseen as 'an artboard', its finish read as 0 % and its foil as
    holding. Now only page 2 may be unlabelled, and only as colour art (the inside)."""
    one = _ai(tmp_path, 'one-plate', [_box('foil', 20.0, 20.0, 80.0, 50.0, '#C9A24B', [FOIL])])
    with pytest.raises(ValueError, match='drawn as a plate'):
        fp.coverage(_unlabelled(one, tmp_path / 'one-unlabelled.ai', 2))
    two = _ai(tmp_path, 'two-plates', [_box('foil', 20.0, 20.0, 80.0, 50.0, '#C9A24B', [FOIL]),
                                       _box('raised', 120.0, 20.0, 40.0, 40.0, '#3B1F3A', [EMBOSS])])
    with pytest.raises(ValueError, match='only page 2'):
        fp.foil_limits(_unlabelled(two, tmp_path / 'two-unlabelled.ai', 3))


def test_the_inside_artboard_in_colour_is_skipped_and_said(tmp_path):
    inside = Group(name='INSIDE', children=[_box('pattern', 10.0, 10.0, 60.0, 40.0, '#B04A6A')])
    children = [Group(name='ART', children=[_box('ground', 0, 0, LID_W_MM, LID_H_MM, '#3B1F3A'),
                                            _box('foil', 20.0, 20.0, 80.0, 50.0, '#C9A24B', [FOIL])])]
    doc = Document(page_w=LID_W_MM, page_h=LID_H_MM, title='inside', metadata=dict(SURFACE),
                   root=Group(name='Artwork', children=children), inside=inside)
    path = tmp_path / 'inside.ai'
    emit_pdf_ai(doc, str(path))
    record = fp.coverage(path)
    assert [p['plate'] for p in record['plates']] == ['FOIL_GOLD'] and record['skipped_pages'][0]['page'] == 2
    assert 'colour art' in record['skipped_pages'][0]['why']


def test_a_flat_that_is_not_the_files_page_one_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not this file's flat"):
        fp.render_proof(DAY9_CONCEPTS / 'C-2.2' / 'truthful.png', DAY9_CONCEPTS / 'B-1.3' / 'truthful.ai', tmp_path / 'proof.png')


# --- line density ----------------------------------------------------------------------------------------------------

def _stripes(rows_px, cols_px, *, px_per_mm, pitch_mm, width_mm, angle_deg):
    y, x = np.mgrid[0:rows_px, 0:cols_px].astype(np.float64) / px_per_mm
    a = math.radians(angle_deg)
    across = x * math.cos(a) + y * math.sin(a)                      # distance across the stripes
    return np.mod(across, pitch_mm) < width_mm


def test_line_density_reads_a_known_pitch_upright_and_diagonal():
    px_per_mm = 40.0
    upright = _stripes(800, 1200, px_per_mm=px_per_mm, pitch_mm=0.6, width_mm=0.2, angle_deg=0.0)
    got = fp.line_density(upright, px_per_mm=px_per_mm)
    assert got['max_lines_per_cm'] == pytest.approx(10.0 / 0.6, rel=0.05) and got['angle_deg'] == 0
    diagonal = _stripes(800, 1200, px_per_mm=px_per_mm, pitch_mm=0.6, width_mm=0.2, angle_deg=45.0)
    got = fp.line_density(diagonal, px_per_mm=px_per_mm)
    assert got['max_lines_per_cm'] == pytest.approx(10.0 / 0.6, rel=0.05)
    assert got['angle_deg'] in (45, 135)
    assert got['by_angle']['0'] == pytest.approx(10.0 / 0.6 * math.cos(math.radians(45.0)), rel=0.05)


def test_line_density_finds_where_it_is_densest_and_maps_it():
    px_per_mm = 40.0
    mask = np.zeros((1200, 1600), bool)                              # 30 x 40 mm
    mask[:, 800:] = _stripes(1200, 800, px_per_mm=px_per_mm, pitch_mm=0.8, width_mm=0.3, angle_deg=0.0)
    mask[:, :800] = _stripes(1200, 800, px_per_mm=px_per_mm, pitch_mm=2.0, width_mm=0.5, angle_deg=0.0)
    got = fp.line_density(mask, px_per_mm=px_per_mm)
    assert got['max_lines_per_cm'] == pytest.approx(12.5, rel=0.05)
    x0, y0, x1, y1 = got['window_mm']
    assert x0 >= 20.0 and x1 - x0 == pytest.approx(10.0) and y1 - y0 == pytest.approx(10.0)
    assert got['meets_d9_3'] is True and got['floor_lines_per_cm'] == 12.0
    coarse = got['map']['lines_per_cm']
    assert len(coarse) == 3 and len(coarse[0]) == 4
    assert coarse[0][0] == pytest.approx(5.0, rel=0.1) and coarse[0][3] == pytest.approx(12.5, rel=0.05)
    with pytest.raises(ValueError):
        fp.line_density(mask, px_per_mm=None)


def test_line_density_of_a_plate_read_from_the_engine(tmp_path):
    rings = [_bar('rule-%d' % i, 95.0, 20.0 + i * 0.8, 60.0, 0.3, 0.0, [FOIL]) for i in range(40)]
    (row,) = fp.plate_masks(_ai(tmp_path, 'rules', rings), px_per_mm=40.0)
    got = fp.line_density(row['mask'], px_per_mm=40.0)
    assert got['max_lines_per_cm'] == pytest.approx(12.5, rel=0.05) and got['angle_deg'] == 90


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


def _build(stem, ops, *, cap_mm=11.0, x_mm=10.0, top_mm=8.0, features=L.DEFAULT_FEATURES, finishes=(),
           kerning='optical'):
    return L.logotype(NAME, stem, ops, cap_mm=cap_mm, x_mm=x_mm, top_mm=top_mm, colour='#3A1A2B',
                      finishes=list(finishes), features=features, kerning=kerning)


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

def test_a_face_not_licensed_is_refused_by_name():
    with pytest.raises(L.LetteringRefused) as refused:
        L.resolve_face('NotAHouseFace-Regular')
    assert refused.value.code == L.FACE_NOT_LICENSED and 'NotAHouseFace-Regular' in str(refused.value)
    # a face the D-D7-1 exclusion list holds back (no licence evidence) is never in the licensed catalogue
    excluded = json.loads((L.ROOT / 'docs/audit/day-7/library/fonts-excluded.json').read_text())['files']
    stem = Path(excluded[0]['path']).stem
    with pytest.raises(L.LetteringRefused) as refused:
        _build(stem, [])
    assert refused.value.code == L.FACE_NOT_LICENSED and stem in str(refused.value)


def test_a_licensed_face_not_granted_is_refused_by_name(monkeypatch):
    from apps.ire import font_roles
    real = font_roles.verify_candidate

    def under_review(role, stem):
        record = dict(real(role, stem))
        record['verification'] = 'LICENCE_REVIEW_REQUIRED'
        return record
    monkeypatch.setattr(font_roles, 'verify_candidate', under_review)
    with pytest.raises(L.LetteringRefused) as refused:
        _build(SCRIPT, [])
    assert refused.value.code == L.FACE_NOT_GRANTED
    assert 'GreatVibes-Regular' in str(refused.value) and 'LICENCE_REVIEW_REQUIRED' in str(refused.value)


def test_a_granted_face_resolves_with_its_file_licence_and_grant_and_a_variable_face_names_its_weight():
    face = L.resolve_face(DIDONE)
    assert face['grant']['verification'] == 'VERIFIED_FOR_PRODUCTION'
    assert face['grant']['production_use_status'] == 'GRANTED'
    assert face['licence'].startswith('SIL Open Font License')
    assert face['sha256'] == hashlib.sha256(Path(face['granted_path']).read_bytes()).hexdigest()
    assert face['drawn_sha256'] == hashlib.sha256(Path(face['path']).read_bytes()).hexdigest()
    assert face['instance']['axes'] == {'wght': 700.0} and face['weight'] == 700.0
    with pytest.raises(L.LetteringRefused) as refused:
        L.resolve_face('PlayfairDisplay-Italic[wght]')
    assert refused.value.code == L.FACE_WEIGHT_UNNAMED


def test_the_record_names_the_face_its_file_licence_grant_and_the_glyphs_used():
    _group, record = _build(DIDONE, [SWASH])
    face = record['face']
    assert (face['family'], face['stem']) == ('Playfair Display', 'PlayfairDisplay-Italic[wght]')
    assert hashlib.sha256(Path(face['path']).read_bytes()).hexdigest() == face['drawn_sha256']
    assert face['grant']['production_use_status'] == 'GRANTED' and face['licence']
    assert ''.join(g['chars'] for g in record['glyphs']) == NAME
    assert record['width_mm'] == pytest.approx(record['box_mm'][2] - record['box_mm'][0])
    assert record['box_mm'][0] == pytest.approx(10.0)
    assert record['actual_text'] == NAME and [q['fill_rule'] for q in record['paths']] == ['nonzero']


# --- the drawn copy extracts as its words -------------------------------------------------------------------------

def test_the_logotype_extracts_as_its_words_and_the_artefact_still_reconciles(tmp_path):
    import fitz

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, TextRun
    foil = Finish(kind='foil', plate='FOIL_ROSE_GOLD', appearance=Color.from_hex('#C9A27E'))
    group, _record = _build(DIDONE, [SWASH], finishes=[foil])
    assert group.name == L.GROUP_NAME and group.actual_text == NAME
    assert not any(node.type == 'text' for node, _parent in _doc([group]).walk())       # outlines, never live text
    line = TextRun(name='descriptor', text='Eyeshadow Palette', x=10.0, y=45.0, size_pt=9.0,
                   color=Color.from_hex('#3A1A2B'), font='caption')
    out = tmp_path / 'logotype.ai'
    usage = {}
    emit_pdf_ai(_doc([group, line]), str(out), usage_out=usage)
    first = L.extracted_text(out, 0)
    assert first.count(NAME) == 1 and 'Eyeshadow Palette' in first
    assert usage['reconciliation']['agree'], usage['reconciliation']
    with fitz.open(str(out)) as pdf:
        assert pdf.page_count == 2                                   # the foil on its own plate page
        stream = pdf[0].read_contents()
        plate = pdf[1].get_text('text', flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_COLLECT_VECTORS)
    spoken = ('/Span << /ActualText <FEFF%s> >> BDC' % NAME.encode('utf-16-be').hex()).encode()
    assert stream.count(spoken) == 1 and stream.count(b'EMC') >= 1
    assert NAME not in plate and 'FINISH PLATE FOIL_ROSE_GOLD - FOIL - IN REGISTER WITH PAGE 1' in plate


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

@pytest.mark.parametrize('stem', [ROMAN, SCRIPT, CFF_FACE])
def test_a_glyphs_converted_outline_matches_the_fonts_own_bounds(stem):
    face = L.resolve_face(stem)
    font = L._face_font(face)
    scale = 14.0 / font['head'].unitsPerEm                               # an em of 14 mm
    cmap = font.getBestCmap()
    for ch in 'HRoeg':
        glyph = cmap[ord(ch)]
        own = L.glyph_bounds_fu(face, glyph)                             # fontTools BoundsPen: the curves' extremes
        contours = L.placed_contours(L.glyph_outline(face, glyph), scale_mm_per_unit=scale, x_mm=0.0,
                                     baseline_mm=0.0)
        x0, y0, x1, y1 = L.tight_bbox(contours)
        assert abs(x0 - own[0] * scale) <= 0.01 and abs(x1 - own[2] * scale) <= 0.01, (stem, ch)
        assert abs(-y1 - own[1] * scale) <= 0.01 and abs(-y0 - own[3] * scale) <= 0.01, (stem, ch)
    if 'glyf' in font:
        stored = font['glyf'][cmap[ord('H')]]                            # the font's own stored box (straight H)
        contours = L.placed_contours(L.glyph_outline(face, cmap[ord('H')]), scale_mm_per_unit=scale, x_mm=0.0,
                                     baseline_mm=0.0)
        x0, y0, x1, y1 = L.tight_bbox(contours)
        assert abs(x0 - stored.xMin * scale) <= 0.01 and abs(x1 - stored.xMax * scale) <= 0.01
        assert abs(-y1 - stored.yMin * scale) <= 0.01 and abs(-y0 - stored.yMax * scale) <= 0.01


def test_truetype_quadratics_are_raised_to_cubics_exactly():
    from apps.ire.vq2_glyph_pen import CubicSink
    face = L.resolve_face(ROMAN)
    glyphs = L._face_font(face).getGlyphSet()

    class Watching(CubicSink):
        def __init__(self, glyph_set):
            super().__init__(glyph_set)
            self.quadratics = []

        def _qCurveToOne(self, p1, p2):
            self.quadratics.append((self._getCurrentPoint(), p1, p2))
            super()._qCurveToOne(p1, p2)

    pen = Watching(glyphs)
    glyphs['S'].draw(pen)
    raised = pen.result()
    assert raised == L.glyph_outline(face, 'S')                          # the very conversion the logotype draws
    cubics, start = [], None
    for contour in raised:
        for op, pts in contour:
            if op == 'M':
                start = pts
            elif op == 'C':
                cubics.append((start, *pts))
                start = pts[2]
            elif op == 'L':
                start = pts
    assert pen.quadratics and len(cubics) == len(pen.quadratics)
    for (q0, q1, q2), (c0, c1, c2, c3) in zip(pen.quadratics, cubics):
        assert c0 == pytest.approx(q0) and c3 == pytest.approx(q2)
        for t in (0.2, 0.5, 0.8):
            quad = ((1 - t) ** 2 * q0[0] + 2 * (1 - t) * t * q1[0] + t * t * q2[0],
                    (1 - t) ** 2 * q0[1] + 2 * (1 - t) * t * q1[1] + t * t * q2[1])
            assert math.dist(quad, L.cubic_point(c0, c1, c2, c3, t)) < 1e-9


@pytest.mark.parametrize('stem,ops,features', [
    (DIDONE, [], L.DEFAULT_FEATURES),
    (SCRIPT, [{'op': 'alternate', 'at': 'E', 'feature': 'ss01'}], ('liga', 'fina')),
    (OLDSTYLE, [{'op': 'alternate', 'at': 'R', 'feature': 'ss01'}], L.DEFAULT_FEATURES),
])
def test_the_measured_cap_height_is_the_one_asked(stem, ops, features):
    group, record = _build(stem, ops, cap_mm=11.0, x_mm=20.0, top_mm=30.0, features=features)
    assert abs(record['cap_mm_measured'] - 11.0) <= 0.05
    assert record['cap_measured_on']['char'] == 'E'
    # measured again on the emitted path itself: the E is the first glyph, its contours the path's first
    face = L.resolve_face(stem)
    count = len(L.glyph_outline(face, record['cap_measured_on']['glyph']))
    drawn = _contours(group.children[0])[:count]
    assert abs(record['baseline_mm'] - L.tight_bbox(drawn)[1] - 11.0) <= 0.05
    assert abs(L.tight_bbox(drawn)[1] - 30.0) <= 1e-6                   # the cap line where it was asked


# --- the setting: the face's own GSUB, optical kerning ---------------------------------------------------------------

def test_the_faces_own_alternates_and_final_form_are_applied_and_recorded():
    ops = [{'op': 'alternate', 'at': 'E', 'feature': 'ss01'}, {'op': 'alternate', 'at': 'R', 'feature': 'ss01'},
           {'op': 'alternate', 'at': 'n', 'feature': 'swsh'}]
    _group, record = _build(SCRIPT, ops, features=('liga', 'fina'))
    names = [g['glyph'] for g in record['glyphs']]
    assert names[0] == 'E.ss01' and 'R.ss01' in names and names[-1] == 'e.fina'
    assert names[8] == 'd'                                              # 'fina' only where the face has a form
    status = {(o['at'], o['feature']): o['applied'] for o in record['ops'] if o['op'] == 'alternate'}
    assert status == {('E', 'ss01'): True, ('R', 'ss01'): True, ('n', 'swsh'): False}   # Great Vibes has no swsh
    assert [s['feature'] for s in record['glyphs'][0]['substitutions']] == ['ss01']


@pytest.mark.parametrize('stem', [ROMAN, OLDSTYLE])
def test_optical_kerning_lowers_the_spread_of_the_pair_gaps_against_the_plain_advances(stem):
    word = 'rosewater'
    plain = L.set_word(word, stem, cap_mm=10.0, kerning='none')
    optical = L.set_word(word, stem, cap_mm=10.0, kerning='optical')
    before = [p['gap_mm'] for p in L.pair_gaps(plain)]
    after = [p['gap_mm'] for p in L.pair_gaps(optical)]
    assert len(before) == len(after) == len(word) - 1
    assert statistics.pstdev(after) < 0.5 * statistics.pstdev(before)
    clamp = optical['optical']['clamp_mm']
    for row in optical['optical']['pairs']:
        assert abs(row['adjust_mm']) <= clamp + 1e-9
        assert row['closest_plain_mm'] + row['adjust_mm'] >= L.FOIL_GAP_MIN_MM - 1e-9 or row['adjust_mm'] >= 0.0


def test_a_connecting_script_keeps_its_small_letters_as_the_face_joins_them():
    setting = L.set_word(NAME, SCRIPT, cap_mm=12.0, kerning='optical')
    assert setting['optical']['connecting_script'] is True
    lower = [r for r in setting['optical']['pairs'] if r['class'] == 'lower-lower']
    assert lower and all('kept' in r for r in lower)
    assert all(g['optical_mm'] == 0.0 for g in setting['glyphs'][2:9])


# --- the operations ------------------------------------------------------------------------------------------------

def test_a_swash_is_engine_geometry_computed_never_read_from_a_picture(monkeypatch):
    import PIL.Image

    def no_picture(*_args, **_kwargs):
        raise AssertionError('a picture was read while lettering')
    monkeypatch.setattr(PIL.Image, 'open', no_picture)
    try:
        import cv2
        monkeypatch.setattr(cv2, 'imread', no_picture)
    except ImportError:
        pass
    from shapely.geometry import Polygon
    group, record = _build(DIDONE, [SWASH])
    again, _r = _build(DIDONE, [SWASH])
    assert group.children[0].segments == again.children[0].segments          # the same numbers, the same points
    measured = record['ops'][0]['measured']
    rebuilt = L.swash_geometry(*measured['centreline'], start_mm=measured['start_width_mm'],
                               tip_mm=measured['tip_width_mm'], taper=measured['taper'], belly_mm=measured['belly_mm'])
    drawn = L.region(_contours(group.children[0])[-len(rebuilt['outline']):])
    computed = L.region(rebuilt['outline'])
    assert drawn.symmetric_difference(computed).area < 1e-6 * computed.area      # its points, from its numbers alone
    assert measured['min_width_mm'] >= L.FOIL_LINE_MIN_MM                       # its tip a foil line at the finest
    moved, _r = _build(DIDONE, [dict(SWASH, to_em=[1.5, -0.2])])
    assert moved.children[0].segments != group.children[0].segments
    assert isinstance(computed, Polygon)


def test_overlapping_pieces_unite_under_nonzero_and_counters_stay_open(tmp_path):
    from PIL import Image

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    ops = [{'op': 'alternate', 'at': 'R', 'feature': 'ss01'},
           {'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.012}]
    group, record = _build(OLDSTYLE, ops, cap_mm=12.0, x_mm=5.0, top_mm=6.0)
    assert group.children[0].fill_rule == 'nonzero'
    join = [o for o in ops if o['op'] == 'join'][0]
    assert [o for o in record['ops'] if o['op'] == 'join'][0]['measured']['overlap_mm'] == pytest.approx(
        join['overlap_em'] * record['em_mm'])
    face = L.resolve_face(OLDSTYLE)
    scale = record['em_mm'] / L._face_font(face)['head'].unitsPerEm
    placed = {}
    for g in record['glyphs']:
        if g['chars'] in ('R', 'o'):
            placed[g['chars']] = L.region(L.placed_contours(L.glyph_outline(face, g['glyph']), scale_mm_per_unit=scale,
                                                            x_mm=g['x_mm'], baseline_mm=record['baseline_mm']))
    overlap = placed['R'].intersection(placed['o'])
    assert overlap.area > 0.0
    counter = L._polygons(placed['o'])[0].interiors[0]
    from shapely.geometry import Polygon
    eye = Polygon(counter).representative_point()
    inside = overlap.representative_point()
    out = tmp_path / 'ro.ai'
    emit_pdf_ai(_doc([group]), str(out))
    png = tmp_path / 'ro.png'
    assert pdf_to_png(out, png, dpi=600)
    with Image.open(png) as im:
        grey = im.convert('L')
        px = 600 / 25.4
        assert grey.getpixel((int(inside.x * px), int(inside.y * px))) < 100        # the overlap is ink
        assert grey.getpixel((int(eye.x * px), int(eye.y * px))) > 200              # the o's eye is paper


def test_a_cut_in_is_a_boolean_difference_on_flattened_outlines_written_back_as_lines():
    ops = [{'op': 'cut_in', 'at': 'E', 'shape': 'inline', 'inset_em': 0.024, 'width_em': 0.014}]
    group, record = _build(DIDONE, ops)
    measured = record['ops'][0]['measured']
    assert measured['flattened_at_mm'] <= 0.005 and measured['written_as'] == 'LineTo'
    assert measured['area_cut_mm2'] > 0.0
    assert measured['area_before_mm2'] - measured['area_cut_mm2'] == pytest.approx(measured['area_after_mm2'],
                                                                                    abs=1e-6)
    assert measured['foil_gap_ok'] and measured['foil_rim_ok']           # a 0.2 mm gap, a 0.1 mm rim at 11 mm
    first = _contours(group.children[0])[0]                               # the E: lines only, after the cut
    assert first and all(seg[0] == 'L' for seg in first)


def test_a_bridge_is_as_thick_as_the_bar_it_leaves_and_touches_no_other_letter():
    _group, record = _build(DIDONE, [{'op': 'join', 'kind': 'bridge', 'after': 't', 'height_em': 0.5}])
    measured = record['ops'][0]['measured']
    top, bottom = measured['measured_run_mm']
    assert measured['thickness_mm'] == pytest.approx(min(bottom - top, measured['inscribed_mm']))
    assert measured['thickness_mm'] <= L.BRIDGE_MAX_EM * record['em_mm']
    assert measured['touches'] == [] and record['ops'][0]['pair'] == 'te'


def test_a_bridge_leaving_a_flared_bar_is_as_thick_as_the_bars_body_never_pinched_at_its_end():
    # Cormorant's t: its bar wedges from about 0.69 mm by the stem to 0.82 mm at its end; a circle taken at the end
    # itself is bounded by the end (0.38 mm), and once drew the bridge as a wire
    _group, record = _build(OLDSTYLE, [{'op': 'join', 'kind': 'bridge', 'after': 't', 'height_em': 0.36}],
                            cap_mm=10.0)
    join = record['ops'][0]
    measured, em_mm = join['measured'], record['em_mm']
    assert join['pair'] == 'te' and measured['touches'] == []
    face = L.resolve_face(OLDSTYLE)
    scale = em_mm / L._face_font(face)['head'].unitsPerEm
    t = [g for g in record['glyphs'] if g['chars'] == 't'][0]
    bar = L.region(L.placed_contours(L.glyph_outline(face, t['glyph']), scale_mm_per_unit=scale, x_mm=t['x_mm'],
                                     baseline_mm=record['baseline_mm']))
    x_end, y = measured['leaves_mm']
    runs = []
    for k in range(1, 13):                                            # the bar's last 0.06 em, read on its own outline
        run = L._vertical_run(bar, x_end - k * 0.005 * em_mm, y, 0.1 * em_mm)
        if run is not None:
            runs.append(run[1] - run[0])
    assert len(runs) >= 10
    assert 0.9 * min(runs) <= measured['thickness_mm'] <= max(runs) + 1e-9
    assert measured['thickness_mm'] > 3.0 * L.BRIDGE_BURY_EM * em_mm          # never the end-bounded wire


def test_a_static_face_draws_as_granted_and_keeps_the_weight_named_beside_its_own():
    named = L.resolve_face('AbrilFatface-Regular@900')                # lettering_faces names Abril at 900
    plain = L.resolve_face('AbrilFatface-Regular')
    assert named['path'] == plain['path'] and named['drawn_sha256'] == plain['drawn_sha256']   # the same file drawn
    assert named['weight_named'] == 900.0 and named['weight'] == 900.0
    assert plain['weight_named'] is None and plain['weight'] == plain['weight_class']
    assert named['weight_class'] == plain['weight_class'] == float(L._face_font(plain)['OS/2'].usWeightClass)
    variable = L.resolve_face(DIDONE)
    assert variable['weight_named'] == variable['weight'] == variable['weight_class'] == 700.0


def test_the_d_d8_5_match_names_the_face_or_is_refused_by_name():
    from apps.pipeline.services.concept_design_map import LETTERING_SET, LETTERING_TRACED
    assert L.face_from_match({'state': LETTERING_SET, 'face': 'PlayfairDisplay[wght]', 'outline': 0.71},
                             weight=700) == 'PlayfairDisplay[wght]@700'
    assert L.face_from_match({'state': LETTERING_SET, 'face': SCRIPT}) == SCRIPT
    with pytest.raises(L.LetteringRefused) as refused:
        L.face_from_match({'state': LETTERING_TRACED, 'why': 'no face the house holds comes close'})
    assert refused.value.code == L.MATCH_NOT_SET


def test_an_unknown_operation_and_right_to_left_text_are_refused_by_name():
    with pytest.raises(L.LetteringRefused) as refused:
        _build(DIDONE, [{'op': 'emboss'}])
    assert refused.value.code == L.OP_UNKNOWN
    with pytest.raises(L.LetteringRefused) as refused:
        L.set_word('باليت', 'NotoNaskhArabic-Bold', cap_mm=5.0)
    assert refused.value.code in (L.TEXT_RIGHT_TO_LEFT, L.FACE_NO_LATIN)


def test_a_ligature_the_face_lacks_shares_a_stem():
    ops = [{'op': 'join', 'kind': 'stem', 'after': 5}]                  # ENCHA[N]TED: the N and the T
    group, record = L.logotype('ENCHANTED ROSE', 'Cinzel[wght]@700', ops, cap_mm=7.5, x_mm=10.0, top_mm=8.0,
                               colour='#000000', finishes=[])
    join = record['ops'][0]
    assert join['pair'] == 'NT'
    left, right = join['measured']['left_stem'], join['measured']['right_stem']
    assert left['centre_mm'] == pytest.approx(right['centre_mm'], abs=1e-6)        # the T's stem on the N's right one
    assert len(left['heights']) >= L.STEM_MIN_HEIGHTS and len(right['heights']) >= L.STEM_MIN_HEIGHTS
    face = L.resolve_face('Cinzel[wght]@700')
    scale = record['em_mm'] / L._face_font(face)['head'].unitsPerEm
    placed = {g['chars']: L.region(L.placed_contours(L.glyph_outline(face, g['glyph']), scale_mm_per_unit=scale,
                                                     x_mm=g['x_mm'], baseline_mm=record['baseline_mm']))
              for g in record['glyphs'][5:7]}
    assert placed['N'].intersection(placed['T']).area > 0.0               # one stem, their contours united
    assert group.actual_text == 'ENCHANTED ROSE'


def test_a_letter_cut_in_under_its_neighbour_keeps_a_white_line_between_them():
    gap_em = 0.02
    ops = [{'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.03},
           {'op': 'cut_in', 'at': 'R', 'shape': 'knockout', 'by': 'o', 'gap_em': gap_em}]
    group, record = _build('AbrilFatface-Regular', ops, cap_mm=9.0)
    cut = [o for o in record['ops'] if o['op'] == 'cut_in'][0]['measured']
    assert cut['by'] == 'o' and cut['area_cut_mm2'] > 0.0
    letters = _contours(group.children[0])
    face = L.resolve_face('AbrilFatface-Regular')
    scale = record['em_mm'] / L._face_font(face)['head'].unitsPerEm
    o_glyph = [g for g in record['glyphs'] if g['chars'] == 'o'][0]
    o_region = L.region(L.placed_contours(L.glyph_outline(face, o_glyph['glyph']), scale_mm_per_unit=scale,
                                          x_mm=o_glyph['x_mm'], baseline_mm=record['baseline_mm']))
    drawn = L.region(letters)
    # the drawn ink near the o is the o itself and, a white line away, the R: nothing of the R within the gap
    halo = o_region.buffer(gap_em * record['em_mm'] * 0.9).difference(o_region)
    assert drawn.intersection(halo).area < 1e-3


def test_a_cut_that_takes_no_ink_is_said_never_claimed():
    """A cut_in that removes nothing is recorded applied False with why, its foil flags reading nothing (every cut was
    once recorded applied True, its foil flags worked out from its numbers, cut or not)."""
    _group, record = _build('CormorantGaramond-Italic[wght]@600', [{'op': 'cut_in', 'at': 'E', 'shape': 'inline',
                                                                     'inset_em': 0.2, 'width_em': 0.02}], cap_mm=9.0)
    cut = record['ops'][0]
    assert cut['measured']['area_cut_mm2'] == 0.0 and cut['applied'] is False and cut['why'] == 'the cut meets no ink of this glyph'
    assert cut['measured']['foil_gap_ok'] is None
    _group, record = _build('CormorantGaramond-Italic[wght]@600', [{'op': 'cut_in', 'at': 'E', 'shape': 'inline',
                                                                     'inset_em': 0.03, 'width_em': 0.02}], cap_mm=9.0)
    assert record['ops'][0]['applied'] is True and record['ops'][0]['measured']['area_cut_mm2'] > 0.0


@pytest.mark.parametrize('ops, code', [
    ([{'op': 'cut_in', 'at': ' ', 'shape': 'inline', 'inset_em': 0.03, 'width_em': 0.02}], 'LETTERING_OPERATION_TARGET_NOT_IN_TEXT'),
    ([{'op': 'swash', 'at': ' ', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.06], 'c2_em': [1.0, -0.22], 'to_em': [2.2, -0.1]}],
     'LETTERING_OPERATION_TARGET_NOT_IN_TEXT'),
    ([{'op': 'alternate', 'at': ' ', 'feature': 'ss01'}], 'LETTERING_OPERATION_TARGET_NOT_IN_TEXT'),
    ([{'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.0}], 'LETTERING_OPERATION_PARAMETER_REFUSED'),
    ([{'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.06], 'c2_em': [1.0, -0.22], 'to_em': [2.2, -0.1],
       'belly_em': -0.05}], 'LETTERING_OPERATION_PARAMETER_REFUSED'),
    ([{'op': 'alternate', 'at': 'R', 'feature': 'ss01'}, {'op': 'alternate', 'at': 'R', 'feature': 'ss02'}],
     'LETTERING_OPERATION_PARAMETER_REFUSED'),
])
def test_an_operation_on_a_space_or_with_numbers_that_cannot_do_it_is_refused_by_name(ops, code):
    with pytest.raises(L.LetteringRefused) as refused:
        _build('LibreBaskerville[wght]@400', ops, cap_mm=9.0)
    assert refused.value.code == code


def test_the_foil_trap_closes_what_is_under_its_gap_and_the_record_says_so():
    """B-2.2's knockout white line (0.192 mm) and C-2.2's swash (0.175 mm from its o) are closed by the press trap: the
    records said them applied; read after the trap they are not, with why, and the shapes they kept apart are one."""
    from apps.pipeline.services import day9_recipes as recipes, rich_concept as rc
    out = {}
    for sid, idea in (('B-2.2', 'B-2'), ('C-2.2', 'C-2')):
        choices = rc.sketch_record(sid)['option']['choices']
        out[sid] = rc.name_lines(rc.spec(idea), recipes.recipe(idea, choices, sid))
    (b2,) = out['B-2.2']
    cut = [o for o in b2['record']['ops'] if o['op'] == 'cut_in'][0]
    assert cut['applied'] is False and cut['why'].startswith('closed by the foil trap: its white is 0.192 mm')
    assert b2['foil_trap']['pieces'] == [13, 12] and b2['foil_trap']['closed'] == ['cut_in at R (0.192 mm)']
    swash = [o for o in out['C-2.2'][1]['record']['ops'] if o['op'] == 'swash'][0]
    assert swash['applied'] is False and out['C-2.2'][1]['foil_trap']['pieces'] == [4, 3]
    assert out['C-2.2'][0]['foil_trap']['closed'] == []
    from apps.dashboard.day8_views import _ops_said
    assert _ops_said([b2['record']['ops']]).endswith('R cut in under o, a hairline between them (not applied: closed by the '
                                                      'foil trap: its white is 0.192 mm, under the 0.2 mm foil gap)')


def test_a_stroke_in_its_own_paint_is_its_own_path_trapped_onto_the_letter(tmp_path):
    import fitz

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish
    foil = Finish(kind='foil', plate='FOIL_GOLD', appearance=Color.from_hex('#C8A45A'))
    gold = dict(SWASH, colour='#C8A45A', finishes=[foil])
    group, record = _build(OLDSTYLE, [{'op': 'alternate', 'at': 'R', 'feature': 'ss01'}, gold])
    names = [c.name for c in group.children]
    assert names == ['logotype-outlines', 'logotype-swash-R']
    letters, swash = group.children
    assert letters.finishes == [] and [f.plate for f in swash.finishes] == ['FOIL_GOLD']
    measured = record['ops'][-1]['measured']
    assert measured['paint'] == 'its own' and measured['trap_mm'] == L.SEPARATE_PAINT_TRAP_MM
    overlap = L.region(_contours(letters)).intersection(L.region(_contours(swash)))
    assert overlap.area > 0.0                                           # the trap: the foil runs onto the letter...
    assert overlap.area < 0.5 * L.region(_contours(swash)).area         # ...a little, never over it
    out = tmp_path / 'foil-swash.ai'
    emit_pdf_ai(_doc([group]), str(out))
    with fitz.open(str(out)) as pdf:
        assert pdf.page_count == 2
        assert 'FINISH PLATE FOIL_GOLD - FOIL' in pdf[1].get_text()
    assert L.extracted_text(out, 0).count(NAME) == 1


def test_the_specimen_letters_three_faces_each_joined_swashed_and_optically_kerned(tmp_path):
    from PIL import Image
    out = L.specimen(tmp_path)
    assert out['drawn_copy'].count(NAME) == 3                             # each logotype speaks as its words
    assert 'default_extraction' in out and out['default_extraction_how']   # what a default reader sees, on file
    rows = out['rows']
    assert len({r['face']['family'] for r in rows}) == 3
    joins = set()
    for row in rows:
        ops = {(o['op'], o.get('kind')) for o in row['ops'] if o['applied']}
        assert any(op == 'join' for op, _kind in ops) and ('swash', None) in ops
        joins |= {kind for op, kind in ops if op == 'join'}
        assert row['kerning']['mode'] == 'optical'
        assert abs(row['cap_mm_measured'] - row['cap_mm_asked']) <= 0.05
        assert row['face']['grant']['production_use_status'] == 'GRANTED'
    assert joins == set(L.JOINS)                                          # every join the module offers, shown once
    with Image.open(out['files']['png']['path']) as im:
        assert im.size == (L.SPECIMEN_LID_PX, round(L.SPECIMEN_LID_PX * 120.0 / 190.0))
    assert out['cost_usd'] == 0.0


# ======================================================================================================================
# Day 9: arabic_display — D-D9-5, one Arabic display face made emitter-capable (``apps.ire.arabic_display``).
# Database-free: no test here touches the test database. The chosen face is El Messiri Bold, derived as "El Messiri PF"
# (``ElMessiriPF-Bold``) under ``var/fonts/derived``. ``var/`` is git-ignored, so the module fixture re-derives the same
# bytes where the folder holds none.
# ======================================================================================================================

ROOT = Path(__file__).resolve().parents[4]                                  # the repo
RECORD = ROOT / 'docs' / 'audit' / 'day-9' / 'fonts' / 'arabic-display.json'


@pytest.fixture(scope='module')
def derived():
    """The chosen derived face's provenance (its path absolute), made — deterministically — where var/ holds none."""
    rec = AD.ensure_chosen()
    return dict(rec, path=str(font_instances._abs(rec['path'])))


# --- the derived face passes the emitter-capable check ----------------------------------------------------------------

def test_the_derived_face_passes_the_type_books_emitter_capable_check(derived):
    from apps.ire import type_book as TB
    face = TB.face_from_file(derived['path'], licence_path=ROOT / derived['licence_text']['path'], stem=derived['stem'])
    TB._annotate([face])
    assert face['emitter_capable'] is True                     # type_book.EMITTER_CAPABLE_MEANS, the book's own check
    assert face['arabic_forms_missing'] == 0 and face['arabic_marks_missing'] == 0 and face['reportlab']['ok']
    assert face['licence']['licence'] == 'SIL Open Font License, Version 1.1'
    granted = font_roles.catalogue()[derived['source_stem']]
    assert granted['arabic'] is False and granted['arabic_forms_missing'] == 36   # the face as granted is not capable


def test_every_form_the_emitter_writes_is_in_the_derived_cmap(derived):
    from fontTools.ttLib import TTFont

    from apps.dielines.exporters.text_intl import shape_ar
    cmap = TTFont(derived['path'], lazy=True).getBestCmap()
    shaped = shape_ar(AD.DESCRIPTOR, keep_harakat=True)
    assert 'ﻼ' in shaped                     # ظلال needs the lam-alef ligature: outside the 119 forms the check counts
    assert all(ord(ch) in cmap for ch in shaped)
    forms = AD.emitted_forms()
    assert len(forms) == 128 and set(forms) <= set(cmap)          # the 119 joining forms, U+FEF5–FEFC and U+FDF2
    assert {0xFDF2} | set(range(0xFEF5, 0xFEFD)) <= set(cmap)


# --- registered: the line face resolves to the derived bytes, the granted source verifies ----------------------------

def test_resolve_line_face_draws_the_derived_bytes_and_verifies_the_granted_source(derived):
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    granted = font_roles.catalogue()[derived['source_stem']]
    r = font_roles.resolve_line_face(derived['stem'], derived['wght'])
    assert not r.get('refused'), r
    assert r['record']['verification'] == VERIFIED_FOR_PRODUCTION
    assert r['record']['sha256'] == granted['sha256'] == derived['source_sha256'] == r['sha256']   # the grant names these
    assert Path(r['path']).resolve() == Path(derived['path']).resolve()                         # the derived bytes draw
    assert r['granted_path'] == granted['path'] and r['postscript'] == 'ElMessiriPF-Bold'
    assert r['instance']['sha256'] == derived['sha256'] and r['instance']['derived_from_sha256'] == granted['sha256']
    assert font_roles.instances_registered()['ElMessiriPF-Bold']['derived_from'] == derived['source_stem']
    assert font_roles.line_face_scripts(font_roles.line_face_key(derived['stem'], derived['wght'])) == (True, True)
    # a field on its source, never a catalogue entry (the catalogue's pinned counts hold)
    assert derived['stem'] not in font_roles.catalogue()
    assert [d['stem'] for d in font_instances.derived_of(derived['source_stem'], granted['sha256'])] == [derived['stem']]
    other = font_roles.resolve_line_face(derived['stem'], 400.0)          # made at one weight: another is refused
    assert other['refused'] and other['tried'][-1]['verification'] == font_roles.DERIVED_WEIGHT_VERDICT


def test_a_derived_face_absent_here_or_with_moved_bytes_is_refused(tmp_path, derived):
    assert font_instances.derived_face(derived['stem'], out_dir=tmp_path) is None        # a fresh clone holds none
    assert font_roles.resolve_line_face('NoSuchFacePF-Bold', 700.0)['refused'] is True
    # a provenance whose file's bytes differ from its record is not a derived face
    copy = tmp_path / 'ElMessiriPF-Bold.ttf'
    data = bytearray(Path(derived['path']).read_bytes())
    data[-1] ^= 0xFF
    copy.write_bytes(bytes(data))
    meta = {k: v for k, v in derived.items()}
    meta['path'] = str(copy)
    (tmp_path / 'ElMessiriPF-Bold.json').write_text(json.dumps(meta, ensure_ascii=False))
    assert font_instances.derived_index(tmp_path) and font_instances.derived_face(derived['stem'], out_dir=tmp_path) is None


def test_the_granted_source_of_a_derived_face_still_resolves_as_itself(derived):
    """The GRANTED face a face was derived from stays its own face. Its catalogue entry lists what was derived from it
    under ``derived``; the resolvers read that field as "this entry is a derived face", so wherever the derived face was
    made the source was refused (a line: DERIVED_FACE_NOT_MADE_AT_THAT_WEIGHT; a role: VARIABLE_INSTANCE_UNPINNED) and a
    lead naming it fell to the chain's next face (Day 9's Arabic verifier, measured; its refix was never run)."""
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    font_roles.reset_cache()           # the catalogue read after the fixture made the face (a fresh clone builds it before)
    granted = font_roles.catalogue()[derived['source_stem']]
    assert [d['stem'] for d in granted['derived']] == [derived['stem']]          # the field on the source is kept
    line = font_roles.resolve_line_face(derived['source_stem'], 700.0)
    assert not line.get('refused'), line
    assert line['record']['verification'] == VERIFIED_FOR_PRODUCTION and line['instance'] is None
    assert line['postscript'] == granted['postscript'] and Path(line['path']).resolve() == Path(granted['path']).resolve()
    lead = font_roles.resolve_role_with(derived['source_stem'], 'display')
    assert lead.get('stem') == derived['source_stem'] and lead['postscript'] == granted['postscript'], lead


def test_a_further_line_whose_joins_were_not_measured_is_never_read_as_faithful():
    """A further line whose joins could not be measured leaves the aggregate unmeasured — never 0 — and the face is not
    faithful on it (Day 9's Arabic verifier: ``or 0.0`` read an unmeasured line as a perfect one)."""
    rec = json.loads(RECORD.read_text(encoding='utf-8'))
    row = json.loads(json.dumps(next(r for r in rec['candidates'] if r['key'] == rec['choice']['key'])))
    assert AD.faithful(row)['faithful'] is True                                  # as recorded: every line measured
    assert AD._worst([0.005, None]) is None and AD._worst([0.005, 0.002]) == 0.005 and AD._worst([2, 3], sum) == 5
    row['further_lines']['worst_dy_em'] = AD._worst([x['worst_dy_em'] for x in row['further_lines']['lines']] + [None])
    assert row['further_lines']['worst_dy_em'] is None and AD.faithful(row)['faithful'] is False


def test_measure_leaves_the_further_lines_unmeasured_when_one_of_their_joins_was_not_measured(tmp_path, monkeypatch):
    """measure() itself, one further line's joins unmeasured: the three aggregates are None and the face is not faithful
    (the test above builds the aggregate by hand, so a revert of measure's own lines would pass it)."""
    real = AD.joins

    def one_unmeasured(source_path, drawn_path, text=AD.DESCRIPTOR):
        return {'measured': False} if text == AD.EXTRA_LINES[2] else real(source_path, drawn_path, text)
    monkeypatch.setattr(AD, 'joins', one_unmeasured)
    row = AD.measure(next(c for c in AD.CANDIDATES if c['key'] == 'el-messiri-700'), work_dir=tmp_path)
    lines = row['further_lines']
    assert lines['worst_dy_em'] is None and lines['worst_drift_units'] is None and lines['units_glyphs_differ'] is None
    assert AD.faithful(row)['faithful'] is False


def test_faithful_refuses_a_wrong_letter_that_reads_a_high_iou():
    """The verifier's tampers (ح drawn as خ, ع as غ, a medial ي as ب) read IoU 0.97-0.995 and passed; a candidate must
    also draw every ink component once, every further line whole, every letter from its own glyphs. The control is read
    as it is."""
    rec = json.loads(RECORD.read_text(encoding='utf-8'))
    row = json.loads(json.dumps(next(r for r in rec['candidates'] if r['key'] == rec['choice']['key'])))
    assert AD.faithful(row)['faithful'] is True
    extra = json.loads(json.dumps(row))
    extra['further_lines']['lines'][1]['components']['extra'] = 1                # ح drawn as خ: one dot too many
    assert AD.faithful(extra)['faithful'] is False
    other = json.loads(json.dumps(row))
    other['joins']['units_glyphs_differ'] = 1                                    # a letter from another glyph
    assert AD.faithful(other)['faithful'] is False
    merged = json.loads(json.dumps(row))
    merged['emitter_way']['components']['merged'] = 2
    assert AD.faithful(merged)['faithful'] is False
    control = next(r for r in rec['candidates'] + [rec['control']] if r['control'])
    assert not any(k.startswith(('further', 'glyphs', 'no_ink_component_extra')) for k in AD.faithful(control)['tests'])


def test_the_chosen_faces_dot_pairs_are_measured_against_the_foil_gap_and_said(derived):
    """'its gaps clear the foil limit' was fixed text: at the lid's alif (3.1 mm) the dot pairs of ت and ي stand 0.16 mm
    apart — foil would join them — and the reason now says so from the measure."""
    pl = AD.print_limits(derived['path'], alif_em=AD._alif_em(derived['path']))
    assert pl['gaps_between_shapes'] == 3 and 0.14 <= pl['gaps_between_shapes_mm'][0] <= 0.18
    rec = json.loads(RECORD.read_text(encoding='utf-8'))
    by_key = {r['key']: r for r in rec['candidates'] + [rec['control']]}
    chosen = dict(by_key[rec['choice']['key']], print_limits=pl)
    said = ' '.join(AD._why(dict(rec['choice'], derived=True), dict(by_key, **{rec['choice']['key']: chosen})))
    assert 'clear the foil limit' not in said and '3 place(s) between two of its shapes stand under the 0.2 mm foil gap' in said


def test_a_harfbuzz_that_is_not_raqms_own_build_measures_nothing(monkeypatch):
    from PIL import features
    monkeypatch.setattr(AD, '_HB', {})
    monkeypatch.setattr(features, 'version', lambda name: '0.0.0' if name == 'harfbuzz' else None)
    with pytest.raises(AD.HarfBuzzUnavailable):
        AD.harfbuzz()


def test_a_held_derived_face_whose_licence_text_is_gone_has_it_written_again(tmp_path):
    src = AD.source_of(next(c for c in AD.CANDIDATES if c['key'] == 'el-messiri-700'))
    first = AD.derive(src, out_dir=tmp_path)
    ofl = tmp_path / Path(first['licence_text']['path']).name
    ofl.unlink()
    again = AD.derive(src, out_dir=tmp_path)
    assert ofl.exists() and again['licence_text']['sha256'] == first['licence_text']['sha256'] == AD._sha256(ofl)


# --- the engine draws the descriptor in it --------------------------------------------------------------------------

def test_emit_pdf_ai_draws_the_descriptor_in_the_derived_face(derived, tmp_path):
    import unicodedata

    import fitz

    from apps.dielines.exporters.text_intl import _libs
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    run = TextRun(name='descriptor_ar', text=AD.DESCRIPTOR, x=95.0, y=26.0, size_pt=36.0, align='center',
                  font=font_roles.line_face_key(derived['stem'], derived['wght']), color=Color.from_hex('#000000'))
    doc = Document(page_w=190.0, page_h=40.0, metadata={'typography_surface': AD.SURFACE},
                   root=Group(name='root', role='artwork', children=[run]))
    assert not font_roles.is_exempt(doc)                    # an exempt document would draw every Arabic run in Naskh
    usage = {}
    out = tmp_path / 'descriptor.ai'
    emit_pdf_ai(doc, str(out), usage_out=usage)
    with fitz.open(str(out)) as pdf:
        fonts = {str(f[3]).split('+', 1)[-1] for f in pdf[0].get_fonts(full=True)}
        text = pdf[0].get_text('text').strip()
    assert 'ElMessiriPF-Bold' in fonts and not any('Naskh' in f for f in fonts)      # embedded, and nothing fell back
    # MuPDF hands the drawn presentation forms back in logical order: exactly the forms the reshaper writes, spelling
    # the descriptor under compatibility decomposition (U+FEFC is لا)
    assert text == _libs(True)[0](AD.DESCRIPTOR)
    assert unicodedata.normalize('NFKC', text) == AD.DESCRIPTOR
    row = next(r for r in usage['faces'] if r['postscript'] == 'ElMessiriPF-Bold')
    assert row['outside_layer'] is False and row['sha256'] == derived['sha256'] and row['chars'] == len(AD.DESCRIPTOR) - 1
    assert row['instance_of']['stem'] == derived['source_stem'] and row['instance_of']['sha256'] == derived['source_sha256']
    assert usage['reconciliation']['agree'] is True and usage['reconciliation']['embedded'] == ['ElMessiriPF-Bold']
    assert usage['refused']['chunks'] == []


def test_the_engines_page_matches_the_raqm_reference(derived, tmp_path):
    proof = AD.emitter_proof(derived['stem'], derived['wght'], work_dir=tmp_path, source_path=ROOT / derived['drawn_from'])
    got = proof['iou_vs_reference']
    assert got['iou'] >= AD.IOU_FAITHFUL                         # 0.969 measured (MuPDF against FreeType raqm)
    assert got['components']['missing'] == got['components']['extra'] == got['components']['split'] == 0
    assert proof['order'] == 'logical' and proof['forms_drawn'] and proof['descriptor_recovered']


# --- the emitter way against raqm, above the threshold the measurements set ------------------------------------------

def test_the_emitter_way_matches_raqm_above_the_measured_threshold(derived):
    source = ROOT / derived['drawn_from']
    ref = AD.supersampled(AD.render_reference, source, AD.DESCRIPTOR, em_px=AD.MEASURE_EM_PX)
    emit = AD.supersampled(AD.render_basic, derived['path'], AD._shaped(), em_px=AD.MEASURE_EM_PX)
    got = AD.compare(ref, emit)
    assert got['iou'] >= AD.IOU_FAITHFUL                         # 0.9951 measured
    assert got['components']['missing'] == got['components']['split'] == got['components']['extra'] == 0
    j = AD.joins(source, derived['path'])
    assert j['measured'] and j['joins'] == 7 and j['worst_dy_units'] == 0 and j['worst_dx_units'] == 0
    assert j['units_glyphs_differ'] == 0 and j['missing_in_cmap'] == []


def test_the_threshold_sits_between_the_faithful_and_the_drifting_faces_measured():
    rec = json.loads(RECORD.read_text())
    readings = rec['thresholds']['readings']
    assert rec['thresholds']['iou_faithful'] == AD.IOU_FAITHFUL
    faithful = [r['iou'] for k, r in readings.items() if k.startswith(('el-messiri', 'reem-kufi', 'noto-naskh'))]
    drifting = [r['iou'] for k, r in readings.items() if k.startswith(('mirza', 'aref-ruqaa'))]
    assert len(faithful) == 5 and len(drifting) == 4
    assert min(faithful) > AD.IOU_FAITHFUL > max(drifting)
    assert readings['aref-ruqaa-700']['worst_join_dy_em'] > AD.JOIN_DY_EM_MAX >= readings['el-messiri-700']['further_lines_worst_dy_em']
    assert readings['reem-kufi-500']['context_share'] > AD.CONTEXT_SHARE_MAX >= readings['el-messiri-700']['context_share']


def test_the_rule_chooses_the_recorded_face_from_the_recorded_measures(derived):
    rec = json.loads(RECORD.read_text())
    choice = AD.choose(rec['candidates'] + [rec['control']])
    assert choice['key'] == rec['choice']['key'] == AD.CHOSEN['key'] and choice['derived'] is True
    assert rec['derived_sha256'] == derived['sha256'] and rec['derived']['stem'] == AD.CHOSEN['stem']
    assert rec['why'] and rec['emitter_proof']['derived_embedded'] is True
    assert {r['key'] for r in rec['candidates']} == {c['key'] for c in AD.CANDIDATES}
    specimen = ROOT / rec['specimen']['path']
    assert specimen.exists() and _sha(specimen) == rec['specimen']['sha256']


# --- provenance -------------------------------------------------------------------------------------------------------

def test_the_provenance_names_the_ofl_licence_its_text_and_the_source_digest(derived):
    from fontTools.ttLib import TTFont
    assert derived['schema'] == font_instances.DERIVED_SCHEMA
    assert derived['licence'] == 'SIL Open Font License, Version 1.1' and derived['reserved_font_names'] == []
    assert derived['source_sha256'] == _sha(ROOT / derived['source_path'])
    assert derived['sha256'] == _sha(derived['path'])
    licence = ROOT / derived['licence_text']['path']
    text = licence.read_text(encoding='utf-8')
    assert _sha(licence) == derived['licence_text']['sha256']
    assert text.startswith(derived['copyright']) and 'SIL OPEN FONT LICENSE Version 1.1' in text
    assert derived['licence_evidence']['evidence_sha256'] == _sha(ROOT / derived['licence_evidence']['evidence_path'])
    assert derived['cmap_added_count'] == 37 and derived['composites'] == 1 and derived['cmap_kept']['differ'] == []
    assert derived['tool']['harfbuzz'] == derived['tool']['raqm_harfbuzz'] and derived['made_at']
    ft = TTFont(derived['path'], lazy=True)
    names = ft['name']
    assert names.getDebugName(1) == 'El Messiri PF' and names.getDebugName(6) == 'ElMessiriPF-Bold'
    assert derived['family'] == 'El Messiri PF' and 'DSIG' not in ft


def test_the_derivation_is_deterministic(tmp_path, derived):
    candidate = next(c for c in AD.CANDIDATES if c['key'] == AD.CHOSEN['key'])
    again = AD.derive(AD.source_of(candidate), out_dir=tmp_path)
    assert again['sha256'] == derived['sha256'] and again['stem'] == AD.CHOSEN['stem']


# --- the instruments ----------------------------------------------------------------------------------------------------

def test_the_shaper_is_the_harfbuzz_pillows_raqm_links(derived):
    hb = AD.harfbuzz()
    assert hb['same_build'] is True and hb['version'] == hb['raqm_harfbuzz']
    # ظلال in El Messiri, visual order: the lone lam, the lam-alef ligature (rlig), the initial zah — no mark, no move
    glyphs = AD.shape(ROOT / derived['drawn_from'], 'ظلال')
    assert [g['name'] for g in glyphs] == ['uni0644', 'uniFEFC', 'uniFEC7']
    assert all(g['y'] == 0 and g['x'] == g['pen'] for g in glyphs)


def test_a_ligature_the_face_shapes_as_two_glyphs_is_measured_from_its_first():
    # Noto Naskh shapes لا as two glyphs (its alef, then its lam) and its own U+FEFC is their sum: the join measure reads
    # a letter from its leftmost advancing glyph, so the control drifts nowhere (it read 300 units, a false drift, when
    # a letter was read from its widest glyph)
    path = font_roles.catalogue()['NotoNaskhArabic-Bold']['path']
    assert [g['name'] for g in AD.shape(path, 'ظلال')][1:3] == ['uni0627.fina.rlig.2', 'uni0644.medi.rlig']
    j = AD.joins(path, path)
    assert j['measured'] and j['worst_drift_units'] == j['worst_dx_units'] == j['worst_dy_units'] == 0
    assert j['units_glyphs_differ'] == 7                     # other glyphs than its shaping's, in the same places
    assert json.loads(RECORD.read_text())['control']['joins']['worst_drift_units'] == 0


def test_a_dotted_letter_alone_is_its_body_and_its_dots_where_the_face_builds_it_so():
    # Reem Kufi draws beh as a dotless body and a dot GPOS places: the derived form is a composite of exactly those
    entry = font_roles.catalogue()['ReemKufi[wght]']
    inst = font_instances.static_at('ReemKufi[wght]', entry['sha256'], 700.0)
    if inst is None:
        pytest.skip('the Reem Kufi 700 instance is not made here')
    got = AD.drawn_form(inst['path'], 'ب', 'init')
    assert not got['single'] and [p['name'] for p in got['glyphs']] == ['dotbelow-ar', 'behDotless-ar.init']
    assert got['glyphs'][0]['y'] < 0 and got['advance'] > 0


def test_compare_aligns_ink_boxes_and_counts_a_lost_dot_and_a_broken_stroke():
    a = np.zeros((60, 120), np.uint8)
    a[20:40, 10:90] = 255
    a[45:50, 50:55] = 255                                   # a dot
    b = np.zeros((60, 120), np.uint8)
    b[20:40, 10:90] = 255
    b[45:50, 10:15] = 255                                   # the dot drawn elsewhere: lost here, extra there
    got = AD.compare(a, b)
    assert got['shift_px'] == [0, 0] and got['iou'] == round(1600 / 1650, 4)
    assert got['components']['missing'] == 1 and got['components']['extra'] == 1
    shifted = np.roll(a, 2, axis=1)                          # the same ink moved: aligned away, IoU 1
    assert AD.compare(a, shifted)['iou'] == 1.0
    broken = a.copy()
    broken[20:40, 48:50] = 0                                 # the stroke cut: one reference component drawn as two
    assert AD.compare(a, broken)['components']['split'] == 1


# ======================================================================================================================
# Day 9: rich_plate — §4, the plate paths and the plate proof (``rich_plate``), on fixtures at the lid's own grid (1536
# × 970 at ≈ 8.08 px/mm); the structure is drawn by our engine (Document → .ai → raster). No provider is called: every
# edit and mark match is a fake, and so is every OCR read but one test's, which runs production's own reader (local
# tesseract, $0). DB-free.
# ======================================================================================================================

ROWS, COLS = rp.LID_PX[1], rp.LID_PX[0]
GROUND_HEX, GOLD_HEX = '#3C2837', '#D8B878'
NAME_INK = (236, 205, 150)
LINE_INK = (28, 10, 22)


def _velvet(seed=7, fine=6.0, coarse=2.5, base=(112.0, 46.0, 92.0)):
    """A plum velvet ground: a fine grain, a soft mottle and a gentle light falloff, deterministic."""
    rng = np.random.default_rng(seed)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (ROWS, COLS)).astype(np.float32), (0, 0), 1.1)
    mottle = cv2.GaussianBlur(rng.normal(0, 1, (ROWS, COLS)).astype(np.float32), (0, 0), 7.0)
    grain /= grain.std()
    mottle /= mottle.std()
    yy, xx = np.mgrid[0:ROWS, 0:COLS].astype(np.float32)
    light = 1.0 + 0.18 * (xx / COLS) - 0.10 * (yy / ROWS)
    rgb = (np.array(base, np.float32) * light[..., None] + fine * grain[..., None] * np.array([1.0, 0.7, 0.9])
           + coarse * mottle[..., None] * np.array([1.0, 0.6, 0.85]))
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


@pytest.fixture(scope='module')
def velvet():
    return _velvet()


@pytest.fixture(scope='module')
def rosette(tmp_path_factory):
    """An engine-turned rosette drawn by our engine: 40 rings at 0.7 mm pitch (14 lines/cm), 0.12 mm gold lines (the
    print limits of D-D9-3), through the emitter and the rasteriser at the lid's scale; its footprint is where it
    differs from the ground drawn alone, and its coverage is how much (anti-aliased) gold each pixel holds."""
    from apps.ire.graph import ClosePath, Color, Document, Group, LineTo, MoveTo, Path as VPath, Rect, SolidFill, Stroke
    out = tmp_path_factory.mktemp('rosette')

    def doc(rings):
        ground = Group(name='GROUND', role='background', children=[
            Rect(name='ground', x=0, y=0, w=tc.W, h=tc.H, fill=SolidFill(color=Color.from_hex(GROUND_HEX)))])
        paths = []
        for k in range(40 if rings else 0):
            r = 4.0 + 0.7 * k
            pts = [(142.0 + (r + 0.35 * math.sin(12 * t)) * math.cos(t), 62.0 + (r + 0.35 * math.sin(12 * t)) * math.sin(t))
                   for t in np.linspace(0, 2 * math.pi, 361)[:-1]]
            segs = [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + [ClosePath()]
            paths.append(VPath(name='ring-%d' % k, segments=segs, stroke=Stroke(color=Color.from_hex(GOLD_HEX), width_mm=0.12)))
        children = [ground] + ([Group(name='ORNAMENT', role='decoration', children=paths)] if paths else [])
        return Document(page_w=tc.W, page_h=tc.H, title='rosette', root=Group(name='root', role='artwork', children=children))

    drawn = np.asarray(Image.open(tc.render(doc(True), out / 'rosette.png', frame=False)['path']).convert('RGB'))
    ground = np.asarray(Image.open(tc.render(doc(False), out / 'ground.png', frame=False)['path']).convert('RGB'))
    diff = np.abs(drawn.astype(int) - ground.astype(int)).max(axis=2)
    assert drawn.shape == (ROWS, COLS, 3)
    return {'rgb': drawn, 'mask': diff > 10, 'coverage': diff / diff.max()}


def _no_words(png, *, lang, psm):
    return []


def _mark_far(png):
    return {'score': 0.1, 'box_mm': [10.0, 10.0, 30.0, 20.0]}


def _prove(plate, rosette, *, removed, pasted, ocr=_no_words, mark=_mark_far):
    return rp.prove_rich_plate(plate, removed_masks=removed, pasted_regions=pasted, structure_rgb=rosette['rgb'],
                               structure_mask=rosette['mask'], px_per_mm=rp.PX_PER_MM, ocr=ocr, mark_matcher=mark)


def _with_line(plate, p0=(160, 640), p1=(640, 820)):
    """A thin dark line (3 px, anti-aliased) drawn on the plate, and its mask."""
    out, m = plate.copy(), np.zeros((ROWS, COLS), np.uint8)
    cv2.line(m, p0, p1, 255, 3, cv2.LINE_AA)
    cv2.line(out, p0, p1, LINE_INK, 3, cv2.LINE_AA)
    return out, m > 0


def _name_block():
    block = np.zeros((ROWS, COLS), bool)
    block[100:220, 150:600] = True
    return block


def _painted(plate, coverage, *, dx_px=0, dy_px=0, alpha=0.6, ink=(216, 184, 120)):
    """``plate`` with a copy of the structure painted on it, moved by (dx, dy) px — what an image model that kept or
    re-drew our ornament would leave."""
    moved = cv2.warpAffine(coverage.astype(np.float32), np.float32([[1, 0, dx_px], [0, 1, dy_px]]), (COLS, ROWS))
    a = (alpha * moved)[..., None]
    return np.clip(np.round(plate * (1 - a) + np.array(ink, np.float32) * a), 0, 255).astype(np.uint8)


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


def test_ciede2000_matches_sharma_wu_dalal_2005_to_four_decimals():
    got = rp.ciede2000(np.array([p[0] for p in SHARMA_2005]), np.array([p[1] for p in SHARMA_2005]))
    assert [round(float(v), 4) for v in got] == [p[2] for p in SHARMA_2005]
    # one pair at a time (scalars), and both orders
    for lab1, lab2, expected in SHARMA_2005:
        assert round(float(rp.ciede2000(lab1, lab2)), 4) == expected
        assert round(float(rp.ciede2000(lab2, lab1)), 4) == expected


def test_ciede2000_agrees_with_the_repos_own_witness_and_lab_is_d65_srgb():
    from apps.pipeline.services import fidelity_checks as fc
    rng = np.random.default_rng(0)
    a = np.column_stack([rng.uniform(0, 100, 500), rng.uniform(-90, 90, 500), rng.uniform(-90, 90, 500)])
    b = np.column_stack([rng.uniform(0, 100, 500), rng.uniform(-90, 90, 500), rng.uniform(-90, 90, 500)])
    witness = np.array([fc.delta_e_2000(x, y) for x, y in zip(a, b)])
    assert np.abs(rp.ciede2000(a, b) - witness).max() < 1e-9
    # sRGB red under D65 (the published CIELAB of #FF0000), white and black
    assert np.allclose(rp.srgb_to_lab((255, 0, 0)), (53.2408, 80.0925, 67.2032), atol=1e-3)
    assert np.allclose(rp.srgb_to_lab((255, 255, 255)), (100.0, 0.0, 0.0), atol=1e-3)
    assert np.allclose(rp.srgb_to_lab((0, 0, 0)), (0.0, 0.0, 0.0), atol=1e-9)
    for rgb in ((39, 22, 36), (252, 241, 226), (10, 200, 90)):
        assert np.allclose(rp.srgb_to_lab(rgb), fc.lab(rgb), atol=1e-9)


# --- 1. clean_small ----------------------------------------------------------------------------------------------

def test_poisson_cleaning_removes_a_dark_line_the_residue_check_fails_before_and_holds_after(velvet, rosette):
    dirty, element = _with_line(velvet)
    avoid = _name_block()
    dirty[avoid] = NAME_INK
    cleaned, record = rp.clean_small(dirty, element, avoid_mask=avoid)
    region = record['region_mask']
    before = _prove(dirty, rosette, removed=[region], pasted=[region])
    after = _prove(cleaned, rosette, removed=[region], pasted=[region])
    # before: a MEASURED failure, and of the residue check alone
    assert before['holds'] is False and before['not_measured'] == []
    assert before['residue']['holds'] is False
    assert before['residue']['regions'][0]['ratio'] > 3 * rp.RESIDUE_RATIO_MAX
    assert [k for k in ('words', 'mark', 'structure', 'seams') if before[k]['holds'] is not True] == []
    # after: the residue check holds, and so does the whole proof (the positive control)
    assert after['residue']['holds'] is True
    assert after['residue']['regions'][0]['ratio'] <= rp.RESIDUE_RATIO_MAX
    assert after['holds'] is True and after['not_measured'] == []
    # only the grown region changed; the dark line is gone from it
    assert record['changed_outside_region_px'] == 0 and np.array_equal(cleaned[~region], dirty[~region])
    assert (element & ~region).sum() == 0
    assert int(rp.srgb_to_lab(cleaned)[element][:, 0].min()) > int(rp.srgb_to_lab(velvet)[..., 0].min()) - 3
    # the source region (with the clone's margin) was clear of every element and inside the plate
    dx, dy = record['offset_px']
    ys, xs = np.nonzero(rp._guide(region))
    assert ys.min() + dy >= 0 and xs.min() + dx >= 0 and ys.max() + dy < ROWS and xs.max() + dx < COLS
    assert not avoid[ys + dy, xs + dx].any() and not element[ys + dy, xs + dx].any()
    assert record['offset_mm'] == [round(dx / rp.PX_PER_MM, 3), round(dy / rp.PX_PER_MM, 3)]
    assert record['method'].startswith('Poisson blending (cv2.seamlessClone')
    assert record['region']['area_px'] == int(region.sum()) and record['grown_mm'] == rp.SMALL_GROW_MM
    json.dumps(rp.jsonable(record))                      # the record is a file's, its mask summarised


def test_the_seam_after_poisson_reads_under_3_and_a_naive_paste_of_a_shifted_colour_over_3(velvet, rosette):
    dirty, element = _with_line(velvet)
    cleaned, record = rp.clean_small(dirty, element, avoid_mask=np.zeros_like(element))
    region = record['region_mask']
    dx, dy = record['offset_px']
    ys, xs = np.nonzero(region)
    naive = dirty.copy()                                 # the same source pixels, a shifted colour, pasted straight in
    naive[ys, xs] = np.clip(dirty[ys + dy, xs + dx].astype(int) + (10, 4, -6), 0, 255).astype(np.uint8)
    poisson = _prove(cleaned, rosette, removed=[region], pasted=[region])['seams']
    pasted = _prove(naive, rosette, removed=[region], pasted=[region])['seams']
    assert poisson['holds'] is True and poisson['max_delta_e'] < rp.SEAM_DELTA_E_MAX
    assert pasted['holds'] is False and pasted['max_delta_e'] > rp.SEAM_DELTA_E_MAX and pasted['not_measured'] == []
    row = poisson['regions'][0]
    assert row['measured'] == row['arcs'] and row['unmeasured'] == 0 and row['at_plate_edge'] == 0
    # the arcs are 2 mm long: the region's boundary length over 2 mm, to within one arc a contour
    contours, _h = cv2.findContours(region.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    length_mm = sum(cv2.arcLength(c, True) for c in contours) / rp.PX_PER_MM
    assert abs(row['arcs'] - length_mm / rp.SEAM_SEGMENT_MM) <= len(contours) + 1


def test_the_source_is_taken_where_the_texture_matches(rosette):
    """Two grounds side by side: an element on the plum half is filled from the plum half, never across the line."""
    plum, ivory = _velvet(seed=3), _velvet(seed=4, base=(232.0, 222.0, 204.0))
    plate = plum.copy()
    plate[:, 900:] = ivory[:, 900:]
    dirty, element = _with_line(plate, p0=(700, 300), p1=(860, 420))
    cleaned, record = rp.clean_small(dirty, element, avoid_mask=np.zeros_like(element))
    dx, dy = record['offset_px']
    ys, xs = np.nonzero(rp._guide(record['region_mask']))
    assert (xs + dx).max() < 900 and (ys + dy).min() >= 0   # every source pixel on the plum side, inside the plate
    assert record['texture']['distance'] < 1.0
    assert np.array_equal(cleaned[~record['region_mask']], dirty[~record['region_mask']])
    assert record['candidates']['clear'] < record['candidates']['offsets_in_plate']


def test_an_element_at_the_lids_edge_is_removed_and_its_edge_arc_is_no_seam(velvet, rosette):
    dirty, element = _with_line(velvet, p0=(0, 400), p1=(300, 470))
    cleaned, record = rp.clean_small(dirty, element, avoid_mask=np.zeros_like(element))
    region = record['region_mask']
    proof = _prove(cleaned, rosette, removed=[region], pasted=[region])
    assert proof['holds'] is True
    assert proof['seams']['regions'][0]['at_plate_edge'] >= 1 and proof['seams']['regions'][0]['unmeasured'] == 0
    lstar = rp.srgb_to_lab(cleaned)[..., 0]
    assert lstar[element].min() > rp.srgb_to_lab(np.array([[LINE_INK]], np.uint8))[0, 0, 0] + 10


def test_clean_small_refuses_with_no_clear_source_and_on_an_empty_mask(velvet):
    dirty, element = _with_line(velvet)
    everything_else = ~rp._grow(element, 3.0, rp.PX_PER_MM)
    with pytest.raises(rp.NoCleanSource):
        rp.clean_small(dirty, element, avoid_mask=everything_else)
    with pytest.raises(ValueError, match='empty'):
        rp.clean_small(dirty, np.zeros_like(element), avoid_mask=np.zeros_like(element))


def test_a_mask_reused_across_clones_gives_the_same_paste(velvet):
    """OpenCV 5.0.0's seamlessClone writes into its mask: every call here clones from a fresh copy, so the same region
    object pasted twice gives the same result and is itself untouched."""
    dirty, element = _with_line(velvet)
    region = rp._grow(element, rp.SMALL_GROW_MM, rp.PX_PER_MM)
    kept = region.copy()
    source = np.roll(velvet, 200, axis=1)
    first = rp._poisson_paste(source, dirty, region)
    second = rp._poisson_paste(source, dirty, region)
    assert np.array_equal(region, kept) and np.array_equal(first, second)
    assert not np.array_equal(first[region], dirty[region])


def test_lettering_is_cleaned_seam_ready_and_the_whole_proof_holds(velvet, rosette):
    """The headline case: a model-drawn name in the picture. Grown 1 mm, the letters close two counters and leave an
    inlet between two of them too narrow for a seam band; seam-ready, every arc is read and the proof holds."""
    dirty, m = velvet.copy(), np.zeros((ROWS, COLS), np.uint8)
    cv2.putText(m, 'Enchanted', (150, 900), cv2.FONT_HERSHEY_TRIPLEX, 4.0, 255, 9, cv2.LINE_AA)
    element, avoid = m > 0, _name_block()
    dirty[element] = NAME_INK
    dirty[avoid] = NAME_INK
    cleaned, record = rp.clean_small(dirty, element, avoid_mask=avoid)
    region = record['region_mask']
    assert record['seam_ready_px'] > 0 and not (region & avoid).any()
    before = _prove(dirty, rosette, removed=[region], pasted=[region])
    after = _prove(cleaned, rosette, removed=[region], pasted=[region])
    assert before['residue']['holds'] is False and before['not_measured'] == []
    assert after['holds'] is True and after['not_measured'] == []
    assert after['seams']['regions'][0]['unmeasured'] == 0 and after['seams']['max_delta_e'] < rp.SEAM_DELTA_E_MAX
    # the bare grown letters would not be read whole: the seam-ready region is what makes the proof possible
    bare = rp.fill_small_holes(rp._grow(element, rp.SMALL_GROW_MM, rp.PX_PER_MM))
    assert rp.seam_delta_e(cleaned, bare, px_per_mm=rp.PX_PER_MM)['unmeasured'] >= 1


def test_seam_ready_closes_narrow_inlets_and_keeps_wide_gaps_and_the_plates_edge():
    m = np.zeros((ROWS, COLS), bool)
    m[300:400, 300:500] = True
    m[300:400, 508:700] = True                           # 8 px ≈ 1 mm apart: an inlet, closed
    m[300:400, 760:900] = True                           # 60 px ≈ 7.4 mm apart: a gap, kept
    m[0:60, 0:200] = True                                # on the plate's edge: not eroded there
    ready = rp.seam_ready(m)
    assert ready[302:398, 500:508].all() and not ready[300:400, 710:750].any()   # the mouth's corners stay round
    assert ready[0, 0:200].all() and ready[0:60, 0].all() and (ready | ~m).all()


def test_small_islands_inside_a_region_are_filled_and_large_or_open_ones_kept():
    m = np.zeros((ROWS, COLS), bool)
    m[100:200, 100:400] = True
    m[140:146, 150:156] = False                          # 36 px ≈ 0.55 mm²: filled
    m[120:180, 250:350] = False                          # 6000 px ≈ 92 mm²: kept
    m[0:50, 0:50] = True
    m[0:10, 10:20] = False                               # small, but open to the plate's edge: kept
    filled = rp.fill_small_holes(m)
    assert filled[140:146, 150:156].all() and not filled[120:180, 250:350].any() and not filled[0:10, 10:20].any()
    assert (filled & ~m).sum() == 36


# --- 2. and 3. the image edit --------------------------------------------------------------------------------------

def _swash():
    """A large gold swash: a thick arc, 3 mm wide."""
    m = np.zeros((ROWS, COLS), np.uint8)
    cv2.ellipse(m, (520, 560), (300, 160), 0, 200, 340, 255, 24, cv2.LINE_AA)
    return m > 0


def test_the_fake_edit_changes_pixels_only_inside_the_removal_mask(velvet, tmp_path):
    element = _swash()
    dirty = velvet.copy()
    dirty[element] = (214, 178, 96)
    removal = rp._grow(element, 1.0, rp.PX_PER_MM)
    calls = []

    def hostile(image_png, mask_png, prompt, style_ref):
        calls.append((image_png, mask_png, prompt, style_ref))
        frame = np.asarray(Image.open(image_png).convert('RGB'))
        return (255 - frame).astype(np.uint8)            # the model changes every pixel of the frame

    cleaned, record = rp.clean_large(dirty, removal, edit_fn=hostile, prompt='paint the velvet', style_ref='ref.png',
                                     out_dir=tmp_path)
    assert len(calls) == 1 and calls[0][2:] == ('paint the velvet', 'ref.png')
    assert np.array_equal(cleaned[~removal], dirty[~removal]) and record['changed_outside_region_px'] == 0
    assert record['changed_px'] > 0.95 * removal.sum()
    # what the model was sent: the lid in the 1536 × 1024 frame, and an RGBA mask transparent exactly on the removal
    # mask grown 2 mm (the bands opaque)
    image = np.asarray(Image.open(calls[0][0]))
    mask = Image.open(calls[0][1])
    assert image.shape == (1024, 1536, 3) and np.array_equal(image[27:997], dirty)
    assert np.array_equal(image[:27], np.repeat(dirty[:1], 27, axis=0))
    assert mask.mode == 'RGBA' and mask.size == (1536, 1024)
    alpha = np.asarray(mask)[..., 3]
    assert set(np.unique(alpha)) == {0, 255} and (alpha[:27] == 255).all() and (alpha[997:] == 255).all()
    assert np.array_equal(alpha[27:997] == 0, rp._grow(removal, rp.EDIT_GROW_MM, rp.PX_PER_MM))
    assert record['call']['mask_sha256'] and record['call']['editable_px'] == int((alpha == 0).sum())
    json.dumps(rp.jsonable(record))


def test_the_models_colour_cast_is_blended_away_at_the_seam_and_a_naive_paste_keeps_it(velvet, rosette, tmp_path):
    element = _swash()
    dirty = velvet.copy()
    dirty[element] = (214, 178, 96)
    removal = rp._grow(element, 1.0, rp.PX_PER_MM)
    clean_frame = cv2.copyMakeBorder(velvet, 27, 27, 0, 0, cv2.BORDER_REPLICATE).astype(int)

    def cast(image_png, mask_png, prompt, style_ref):
        frame = np.asarray(Image.open(image_png).convert('RGB')).astype(int)
        editable = np.asarray(Image.open(mask_png))[..., 3] == 0
        repainted = np.where(editable[..., None], clean_frame, frame) + (14, -6, 9)   # the swash gone, a colour cast
        return np.clip(repainted, 0, 255).astype(np.uint8)

    cleaned, record = rp.clean_large(dirty, removal, edit_fn=cast, prompt='p', style_ref=None, out_dir=tmp_path)
    naive = dirty.copy()
    naive[removal] = cast(record['call']['image_png'], record['call']['mask_png'], 'p', None)[27:997][removal]
    blended = _prove(cleaned, rosette, removed=[removal], pasted=[removal])
    straight = _prove(naive, rosette, removed=[removal], pasted=[removal])
    assert blended['holds'] is True
    assert blended['seams']['max_delta_e'] < rp.SEAM_DELTA_E_MAX < straight['seams']['max_delta_e']
    assert straight['seams']['holds'] is False and straight['residue']['holds'] is True


def test_paint_free_areas_keeps_the_models_pixels_only_inside_the_free_areas(tmp_path):
    layout = np.full((ROWS, COLS, 3), (200, 170, 110), np.uint8)
    free = np.zeros((ROWS, COLS), bool)
    for cy in range(60, 900, 160):
        for cx in range(60, 1480, 160):
            free[cy:cy + 130, cx:cx + 130] = True          # enamel cells inside the engine's gold lattice
    layout[free] = (90, 30, 70)
    sent = []

    def paint(image_png, mask_png, prompt, style_ref):
        sent.append(np.asarray(Image.open(mask_png))[..., 3])
        return (255 - np.asarray(Image.open(image_png).convert('RGB'))).astype(np.uint8)

    plate, record = rp.paint_free_areas(layout, free, edit_fn=paint, prompt='enamel', style_ref='sketch.png',
                                        out_dir=tmp_path)
    assert np.array_equal(plate[~free], layout[~free]) and np.array_equal(plate[free], 255 - layout[free])
    assert record['changed_outside_free_px'] == 0 and record['changed_px'] == int(free.sum())
    assert np.array_equal(sent[0][27:997] == 0, free) and (sent[0][:27] == 255).all()
    assert record['free_share'] == round(float(free.mean()), 4)


def test_an_edit_of_another_size_or_a_plate_off_the_lid_grid_is_refused_never_resized(velvet, tmp_path):
    removal = rp._grow(_swash(), 1.0, rp.PX_PER_MM)

    def lid_only(image_png, mask_png, prompt, style_ref):
        return np.asarray(Image.open(image_png).convert('RGB'))[27:997]   # 970 rows back for a 1024-row frame

    with pytest.raises(ValueError, match='never resized'):
        rp.clean_large(velvet, removal, edit_fn=lid_only, prompt='p', style_ref=None, out_dir=tmp_path)
    framed = cv2.copyMakeBorder(velvet, 27, 27, 0, 0, cv2.BORDER_REPLICATE)
    with pytest.raises(ValueError, match='working scale'):
        rp.clean_large(framed, np.zeros(framed.shape[:2], bool), edit_fn=lid_only, prompt='p', style_ref=None,
                       out_dir=tmp_path)
    with pytest.raises(ValueError, match='empty'):
        rp.clean_large(velvet, np.zeros((ROWS, COLS), bool), edit_fn=lid_only, prompt='p', style_ref=None,
                       out_dir=tmp_path)
    with pytest.raises(ValueError, match='empty'):
        rp.paint_free_areas(velvet, np.zeros((ROWS, COLS), bool), edit_fn=lid_only, prompt='p', style_ref=None,
                            out_dir=tmp_path)


# --- 4. the proof --------------------------------------------------------------------------------------------------

def test_a_copy_of_the_structure_painted_elsewhere_is_caught(velvet, rosette):
    elsewhere = _painted(velvet, rosette['coverage'], dx_px=-round(80 * rp.PX_PER_MM), dy_px=round(10 * rp.PX_PER_MM))
    proof = _prove(elsewhere, rosette, removed=[rosette['mask']], pasted=[rosette['mask']])['structure']
    assert proof['holds'] is False and proof['not_measured'] == []
    assert proof['shifted_best_ncc'] >= rp.SHIFTED_NCC_MAX
    assert proof['shifted_best_at_mm'] == pytest.approx([-80.0, 10.0], abs=0.3)
    assert proof['in_place_ncc'] < rp.IN_PLACE_NCC_MAX   # nothing in place: the shifted search is what caught it


def test_a_copy_in_place_or_two_pixels_off_is_caught_and_the_clean_plate_holds(velvet, rosette):
    clean = _prove(velvet, rosette, removed=[rosette['mask']], pasted=[rosette['mask']])['structure']
    assert clean['holds'] is True and clean['shifted_best_ncc'] < rp.SHIFTED_NCC_MAX
    assert clean['in_place_ncc'] < rp.IN_PLACE_NCC_MAX and clean['tiles'] > 1
    in_place = _prove(_painted(velvet, rosette['coverage'], alpha=0.35), rosette, removed=[rosette['mask']],
                      pasted=[rosette['mask']])['structure']
    assert in_place['holds'] is False and in_place['in_place_ncc'] >= rp.IN_PLACE_NCC_MAX
    # misregistered by 2 px, the copy hardly correlates in place: only the zero shift is left out of the search
    off = _prove(_painted(velvet, rosette['coverage'], dx_px=2), rosette, removed=[rosette['mask']],
                 pasted=[rosette['mask']])['structure']
    assert off['holds'] is False and off['shifted_best_ncc'] >= rp.SHIFTED_NCC_MAX
    assert off['shifted_best_at_mm'] == pytest.approx([2 / rp.PX_PER_MM, 0.0], abs=0.15)


def test_a_doubled_word_or_mark_fails_and_names_what_it_found(velvet, rosette):
    def words(png, *, lang, psm):
        if lang == 'ara':
            return [('العيون', 77.0, (200, 10, 260, 30))]
        if psm == 11:
            return [('Enchanted', 91.0, (10, 10, 90, 30)), ('noise', 12.0, (0, 0, 5, 5))]
        return []

    def near_mark(png):
        return {'score': 0.81, 'box_mm': [40.0, 20.0, 60.0, 30.0]}

    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    proof = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=words, mark=near_mark)
    assert proof['holds'] is False and proof['not_measured'] == []
    assert proof['words']['holds'] is False and proof['words']['latin_found'] == ['Enchanted']
    assert proof['words']['arabic_found'] == ['العيون']
    assert proof['mark']['holds'] is False and proof['mark']['best_score'] == 0.81


def test_a_reader_that_failed_or_a_mark_not_looked_for_is_not_measured_never_a_pass(velvet, rosette):
    from apps.pipeline.services.concept_sketches import OCRFailed

    def failing(png, *, lang, psm):
        raise OCRFailed('')                               # a failure without a message is still named

    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    for mark, says in (({'score': None, 'not_measured': 'flat in grey at every scale'}, 'flat in grey'),
                       ({'score': -1.0, 'box_mm': [0.0, 0.0, 0.0, 0.0]}, 'below 0'),
                       ({}, 'no score')):
        proof = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=failing, mark=lambda png, m=mark: m)
        assert proof['holds'] is False
        assert proof['words']['holds'] is False and proof['words']['latin_found'] is None
        assert any('OCRFailed' in why for why in proof['words']['not_measured'])
        assert len(proof['words']['not_measured']) == len(rp.OCR_READS) and proof['words']['arabic_found'] is None
        assert proof['mark']['holds'] is False and says in proof['mark']['not_measured'][0]
        assert any(why.startswith('words: ') for why in proof['not_measured'])
        assert any(why.startswith('mark: ') for why in proof['not_measured'])


def test_each_read_is_matched_in_its_own_script_and_a_failed_read_is_named(velvet, rosette):
    """Day 8's plate proof matched the Latin copy in the English reads and the Arabic descriptor in the Arabic read.
    Matched as one list, the Arabic read's digit noise read as a doubled info line (real tesseract: '18' at 57.9 on
    Day 8's A5 plate, '27' at 68.8 on this velvet); here each read is matched in its own script only."""
    from apps.pipeline.services.concept_sketches import OCRFailed
    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    calls = []

    def digits_from(only_lang):
        def read(png, *, lang, psm):
            calls.append((lang, psm))
            return [('18', 90.0, (5, 5, 20, 20)), ('باليت', 88.0, (30, 5, 60, 20))] if lang == only_lang else []
        return read

    from_arabic = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=digits_from('ara'))['words']
    assert calls == [('eng', 11), ('eng', 6), ('ara', 11)]
    assert from_arabic['holds'] is False and from_arabic['not_measured'] == []
    assert from_arabic['latin_found'] == [] and from_arabic['arabic_found'] == ['باليت']   # Arabic copy, not '18'
    from_english = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=digits_from('eng'))['words']
    assert from_english['latin_found'] == ['18', '18'] and from_english['arabic_found'] == []
    assert from_english['holds'] is False and from_english['not_measured'] == []

    def arabic_fails(png, *, lang, psm):
        if lang == 'ara':
            raise OCRFailed('ara did not load')
        return []

    proof = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=arabic_fails)
    words = proof['words']
    assert proof['holds'] is False and words['holds'] is False
    assert words['latin_found'] == [] and words['arabic_found'] is None        # the English reads stand; Arabic unread
    assert len(words['not_measured']) == 1 and 'ara, psm 11' in words['not_measured'][0]
    assert [r['words_read'] for r in words['reads']] == [0, 0, None]
    assert proof['not_measured'] == ['words: ' + words['not_measured'][0]]


def test_production_ocr_holds_on_the_clean_velvet_and_finds_a_name_painted_on_it(velvet, rosette):
    """Through production's own reader, ``concept_sketches.ocr_words`` (local tesseract, $0): on this velvet the Arabic
    read returns texture noise as '27' at 68.8 (measured) — matched as Latin copy, the clean ground failed. Matched in
    its own script, the clean ground holds, every read having read the texture; a name painted on it is found."""
    from apps.pipeline.services.concept_sketches import ocr_words
    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    clean = _prove(velvet, rosette, removed=[region], pasted=[region], ocr=ocr_words)
    assert clean['words']['holds'] is True and clean['words']['not_measured'] == []
    assert clean['words']['latin_found'] == [] and clean['words']['arabic_found'] == []
    assert all(r['words_read'] > 0 for r in clean['words']['reads']) and clean['holds'] is True
    painted = velvet.copy()
    cv2.putText(painted, 'Enchanted Rose', (200, 600), cv2.FONT_HERSHEY_TRIPLEX, 3.0, NAME_INK, 6, cv2.LINE_AA)
    words = _prove(painted, rosette, removed=[region], pasted=[region], ocr=ocr_words)['words']
    assert words['holds'] is False and words['not_measured'] == []
    assert 'Enchanted' in words['latin_found'] and 'Rose' in words['latin_found']


def test_empty_masks_or_regions_give_holds_false_never_a_pass(velvet, rosette):
    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    nothing = np.zeros((ROWS, COLS), bool)
    cases = {
        'removed list empty': (dict(removed=[], pasted=[region]), 'residue', 'list of removed masks is empty'),
        'removed not given': (dict(removed=None, pasted=[region]), 'residue', 'no removed masks were given'),
        'removed mask empty': (dict(removed=[region, nothing], pasted=[region]), 'residue', 'removed mask 1 is empty'),
        'pasted list empty': (dict(removed=[region], pasted=[]), 'seams', 'list of pasted regions is empty'),
        'pasted region empty': (dict(removed=[region], pasted=[nothing]), 'seams', 'pasted region 0 is empty'),
        'pasted region whole': (dict(removed=[region], pasted=[~nothing]), 'seams', 'covers the whole plate'),
    }
    for name, (given, part, says) in cases.items():
        proof = _prove(velvet, rosette, **given)
        assert proof['holds'] is False, name
        assert proof[part]['holds'] is False, name
        assert any(says in why for why in proof[part]['not_measured']), (name, proof[part]['not_measured'])
    flat_structure = rp.prove_rich_plate(velvet, removed_masks=[region], pasted_regions=[region],
                                         structure_rgb=rosette['rgb'], structure_mask=nothing, px_per_mm=rp.PX_PER_MM,
                                         ocr=_no_words, mark_matcher=_mark_far)
    assert flat_structure['holds'] is False and flat_structure['structure']['holds'] is False
    assert 'structure mask is empty' in flat_structure['structure']['not_measured'][0]
    no_detail = rp.prove_rich_plate(velvet, removed_masks=[region], pasted_regions=[region],
                                    structure_rgb=np.full_like(velvet, 60), structure_mask=rosette['mask'],
                                    px_per_mm=rp.PX_PER_MM, ocr=_no_words, mark_matcher=_mark_far)
    assert no_detail['holds'] is False and 'no band-pass detail' in no_detail['structure']['not_measured'][0]


def test_a_flat_or_banded_plate_is_measured_and_a_residue_on_flat_ground_fails(rosette):
    flat = np.full((ROWS, COLS, 3), (60, 40, 55), np.uint8)
    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    proof = _prove(flat, rosette, removed=[region], pasted=[region])
    assert proof['holds'] is True                          # flat everywhere: every part measured, nothing found
    assert proof['residue']['regions'][0]['ratio'] == 0.0 and proof['structure']['in_place_flat'] is True
    # a gradient banded by 8-bit steps (one level every ~50 px) is no ornament
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    banded = np.dstack([40 + (xx * 30 // COLS), 30 + (yy * 12 // ROWS), 50 + (xx * 20 // COLS)]).astype(np.uint8)
    structure = _prove(banded, rosette, removed=[region], pasted=[region])['structure']
    assert structure['holds'] is True and structure['shifted_best_ncc'] < rp.SHIFTED_NCC_MAX
    # a line left on a flat ground is a measured residue, never "not measured": its band-pass tail reaches a ring
    # 1.5 mm out (a ratio far over the max) ...
    lined, element = _with_line(flat)
    near = rp._grow(element, 1.0, rp.PX_PER_MM)
    residue = _prove(lined, rosette, removed=[near], pasted=[near])['residue']
    assert residue['holds'] is False and residue['not_measured'] == []
    assert residue['regions'][0]['ratio'] > 10 * rp.RESIDUE_RATIO_MAX
    # ... and with the ring beyond its reach (3.5 mm out), detail inside and none round it: no ratio to state
    far = rp._grow(element, 3.0, rp.PX_PER_MM)
    residue = _prove(lined, rosette, removed=[far], pasted=[far])['residue']
    assert residue['holds'] is False and residue['not_measured'] == []
    assert residue['regions'][0]['residue_on_flat_ground'] is True and residue['regions'][0]['ratio'] is None


def test_the_seam_measure_alone_reads_the_pictures_own_floor(velvet):
    region = rp._grow(_swash(), 1.0, rp.PX_PER_MM)
    floor = rp.seam_delta_e(velvet, region, px_per_mm=rp.PX_PER_MM)
    assert floor['measured'] == floor['arcs'] and floor['max_delta_e'] < rp.SEAM_DELTA_E_MAX
    with pytest.raises(ValueError, match='no seam'):
        rp.seam_delta_e(velvet, np.zeros((ROWS, COLS), bool), px_per_mm=rp.PX_PER_MM)


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


def anchor_set(folder):
    paths = [png(folder, f'anchor-{i}.png', (20 * i, 30, 40), (400, 250)) for i in range(4)]
    return jury.anchor_blocks(paths[:2], paths[2:])


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

def test_v1_v2_and_every_day8_text_and_schema_are_byte_identical():
    """The v1 and v2 rubric texts, both roles, the answer words and Day 8's three schemas hash as they did before any
    Day 9 line; the system prompts and the roles Day 8's calls build are those same texts."""
    def text_sha(text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def schema_sha(schema):
        return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()

    measured = {'RUBRIC_V1': text_sha(jury.RUBRIC_V1), 'RUBRIC_V2': text_sha(jury.RUBRIC_V2),
                'ROLE_J1': text_sha(jury.ROLE_J1), 'ROLE_J2': text_sha(jury.ROLE_J2),
                'ANSWER_WORDS': text_sha(jury.ANSWER_WORDS), 'RANK_SCHEMA': schema_sha(jury.RANK_SCHEMA),
                'IDEA_SCHEMA': schema_sha(jury.IDEA_SCHEMA), 'verdict_J1': schema_sha(jury.verdict_schema('J1')),
                'verdict_J2': schema_sha(jury.verdict_schema('J2'))}
    assert measured == DAY8_SHA256
    assert jury.RUBRICS['v1'] is jury.RUBRIC_V1 and jury.RUBRICS['v2'] is jury.RUBRIC_V2
    for version in ('v1', 'v2'):
        assert jury._system(version) == [{'type': 'text', 'text': jury.RUBRICS[version], 'cache_control': {'type': 'ephemeral'}}]
    assert jury._role('J1') == {'type': 'text', 'text': 'YOUR ROLE. ' + jury.ROLE_J1}
    assert jury._role('J2') == {'type': 'text', 'text': 'YOUR ROLE. ' + jury.ROLE_J2}


def test_v2p_is_v2_plus_exactly_the_proof_sentence_under_reading_the_bar():
    v2p = jury.RUBRICS['v2p']
    assert jury.FINISH_PROOF_SENTENCE == PROOF_SENTENCE
    assert v2p == jury.RUBRIC_V2 + ' ' + PROOF_SENTENCE and v2p is jury.RUBRIC_V2P
    assert v2p.count(PROOF_SENTENCE) == 1 and PROOF_SENTENCE not in jury.RUBRIC_V1 + jury.RUBRIC_V2
    bar = v2p.rindex('READING THE BAR')                         # v2's last section: no paragraph break after it
    assert jury.RUBRIC_V2.rindex('\n\n') < bar < v2p.index(PROOF_SENTENCE) and v2p.endswith(PROOF_SENTENCE)
    assert jury._system('v2p') == [{'type': 'text', 'text': v2p, 'cache_control': {'type': 'ephemeral'}}]
    assert jury.DAY9_RUBRICS == ('v2p',)


def test_v1_and_v2_calls_and_day8s_ranking_and_idea_check_send_exactly_what_day8_sent(tmp_path, monkeypatch):
    """Both jurors under v1 and v2 (no proof), Day 8's sketch ranking and Day 8's idea check build the very requests the
    pre-edit module built on these fixtures: the texts, their order, the schemas, the roles and the cache breakpoints."""
    captured = []

    def fake_paid(invoke, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(stop_reason='end_turn',
                               content=[SimpleNamespace(type='text', text=json.dumps({'ranking': [], 'best_two': [], 'note': ''}))],
                               model_dump=lambda mode='json': {'usage': {'input_tokens': 10, 'output_tokens': 10}})

    monkeypatch.setattr(jury, 'paid_operation', fake_paid)
    monkeypatch.setattr(jury, '_client', lambda: SimpleNamespace(messages=SimpleNamespace(create=None)))
    p = {name: png(tmp_path, f'{name}.png', colour, size) for name, colour, size in (
        ('cand', (200, 30, 90), (300, 190)), ('la', (10, 10, 10), (400, 250)), ('lb', (20, 20, 20), (400, 250)),
        ('ra', (30, 30, 30), (400, 250)), ('rb', (40, 40, 40), (400, 250)), ('s1', (50, 0, 0), (300, 190)),
        ('s2', (0, 50, 0), (300, 190)))}
    anchors = jury.anchor_blocks([p['la'], p['lb']], [p['ra'], p['rb']])
    common = dict(anchors=anchors, facts='THE FACTS', spec='THE SPEC', engine_issues=('ISSUE ONE',), direction_idea='THE IDEA',
                  effort='high', reservation_prefix='day9/', reservation_cap=1.0, model='test-model')
    measured = {}
    for juror in ('J1', 'J2'):
        for version in ('v1', 'v2'):
            captured.clear()
            jury.ask(juror, p['cand'], operation=f'day9/t/{juror}', destination=tmp_path / f'ask-{juror}-{version}.json',
                     rubric_version=version, **common)
            measured[f'ask/{juror}/{version}'] = canonical(captured[0])
    captured.clear()
    jury.rank_sketches([p['s1'], p['s2']], anchors=anchors, facts='THE FACTS', spec='THE SPEC', direction_idea='THE IDEA',
                       operation='day9/t/rank', destination=tmp_path / 'rank.json', rubric_version='v2', model='test-model',
                       checks=['OCR found 10 of 10.', 'OCR found 4 of 10.'])
    measured['rank_sketches/v2'] = canonical(captured[0])
    captured.clear()
    jury.idea_check('THE SPEC TEXT', anchors=anchors, facts='THE FACTS', operation='day9/t/idea',
                    destination=tmp_path / 'idea.json', rubric_version='v2', model='test-model')
    measured['idea_check/v2'] = canonical(captured[0])
    assert measured == DAY8_REQUEST_SHA256


# --- the finish proof (D-D9-6) ---------------------------------------------------------------------------------------

def test_a_proof_adds_its_label_and_picture_between_the_flat_build_and_the_flat_shelf_view(tmp_path):
    flat = png(tmp_path, 'flat.png', (120, 30, 70), (1536, 970))
    proof = png(tmp_path, 'proof.png', (200, 160, 90), (1536, 970))
    args = dict(what=jury.LID_WHAT, facts='F', spec='S', engine_issues=['E'], direction_idea='I')
    plain, plain_sent = jury._candidate_blocks(flat, **args)
    shown, sent = jury._candidate_blocks(flat, proof=proof, **args)
    # without a proof: Day 8's five blocks, word for word
    assert [b['type'] for b in plain] == ['text', 'image', 'text', 'image', 'text']
    assert plain[0]['text'] == (f'CANDIDATE — {jury.LID_WHAT}. First at full size, then shrunk to 330 px wide (about one '
                                'arc-minute a pixel at 2 m for a 190 mm face — the shelf view).')
    assert plain[2]['text'] == 'The same lid at 330 px wide (shelf view):'
    assert list(plain_sent) == ['candidate_sha256', 'full_px', 'shelf_px']
    # with a proof: two blocks more, its label and its picture, between the flat build and the FLAT build's shelf view
    assert [b['type'] for b in shown] == ['text', 'image', 'text', 'image', 'text', 'image', 'text']
    flat_full, proof_full, shelf = (image_bytes(b) for b in shown if b['type'] == 'image')
    assert flat_full == critic_image_bytes(flat)[0] and proof_full == critic_image_bytes(proof)[0]
    assert shelf == jury.resized_png(flat, width=jury.SHELF_WIDTH_PX)[0]
    with Image.open(io.BytesIO(shelf)) as im:
        assert im.size[0] == 330
    assert shown[0]['text'].startswith(f'CANDIDATE — {jury.LID_WHAT}. First the flat print artwork at full size, then its '
                                       'finish proof at full size, then the flat print artwork shrunk to 330 px wide')
    assert shown[2]['text'] == jury.PROOF_LABEL and shown[2]['text'].startswith('FINISH PROOF of the same lid: not the print artwork')
    assert 'judge the design, never the rendering' in shown[2]['text']
    assert shown[4]['text'] == jury.PROOF_SHELF_LABEL == 'The flat print artwork (not the finish proof) at 330 px wide (shelf view):'
    assert shown[1] == plain[1] and shown[5] == plain[3] and shown[6] == plain[4]      # every other block as it was
    assert sent == dict(plain_sent, proof_sha256=sha(proof), proof_px={'resampled': False, 'size_px': [1536, 970]})


def test_judge_shows_both_jurors_the_proof_in_one_call_each_and_keeps_its_sha256(tmp_path, settings, monkeypatch):
    """Through the real spend reservation (an isolated ledger, a fake client, $0): one call a juror, each with the flat
    build, its finish proof and the flat build's shelf view after the anchors; J1 under its Day 9 role and schema, J2 as
    on Day 8; both records and the verdict keep the proof's sha256; J1's "no" is the verdict's first top issue."""
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    monkeypatch.setattr(jury, '_client', no_default_client)
    flat = png(tmp_path, 'flat.png', (120, 30, 70), (1536, 970))
    proof = png(tmp_path, 'proof.png', (200, 160, 90), (1536, 970))
    anchors = anchor_set(tmp_path)
    client = FakeClient(verdict_answer(9.0, looks_easy_to_make=False, carries_collection=True,
                                       would_buy_partly_for_the_lid=False, would_photograph_it=True,
                                       desirability_why='too quiet for a bold make-up lover'),
                        verdict_answer(9.0, foil_and_blind_lines_legible=True, printability_note=''))
    out = jury.judge(flat, anchors=anchors, facts='F', spec='S', operation_prefix='day9/test/jury',
                     destination_dir=tmp_path / 'jury', rubric_version='v2p', proof=proof, client=client,
                     reservation_prefix='day9/test/', reservation_cap=10.0)
    assert [r['messages'][0]['content'][6] for r in client.requests] == [jury._role('J1', audience=True), jury._role('J2')]
    for request in client.requests:                                     # one call a juror, the proof inside it
        content = request['messages'][0]['content']
        assert content[:6] == anchors[0] and request['system'] == jury._system('v2p')
        assert [image_bytes(b) for b in content if b['type'] == 'image'][4:] == [
            critic_image_bytes(flat)[0], critic_image_bytes(proof)[0], jury.resized_png(flat, width=jury.SHELF_WIDTH_PX)[0]]
    j1, j2 = (r['messages'][0]['content'] for r in client.requests)
    assert AUDIENCE in j1[6]['text'] and AUDIENCE not in json.dumps(j2, ensure_ascii=False)
    assert j1[-1] == {'type': 'text', 'text': jury.DESIRABILITY_WORDS} and j2[-1]['text'].endswith(jury.ANSWER_WORDS)
    assert [r['output_config']['format']['schema'] for r in client.requests] == [
        jury.verdict_schema('J1', desirability=True), jury.verdict_schema('J2')]
    for juror in ('J1', 'J2'):
        rec = json.loads((tmp_path / 'jury' / f'{juror}.json').read_text())
        assert rec['sent']['proof_sha256'] == sha(proof) and rec['proof'] == str(proof) and rec['rubric_version'] == 'v2p'
        assert rec['reservation_id'] and Path(rec['response_artifact']).exists()     # reserved and settled, at $0
    verdict = json.loads((tmp_path / 'jury' / 'verdict.json').read_text())
    assert verdict['proof_sha256'] == sha(proof) and verdict['proof'] == str(proof) and verdict == json.loads(json.dumps(out))
    assert out['top_issues'][0]['observation'] == 'J1: she would not buy it partly for the lid — too quiet for a bold make-up lover'
    assert out['verdict']['passed'] is True and out['caps_applied'] == []          # a top issue, never a cap
    assert out['raw']['J1']['would_photograph_it'] is True and 'would_photograph_it' not in out['raw']['J2']


def test_a_proof_goes_only_with_v2p_and_v2p_only_with_a_proof_refused_before_payment(tmp_path, monkeypatch):
    def unpaid(*args, **kwargs):
        raise AssertionError('a refused call reached the payment')

    monkeypatch.setattr(jury, 'paid_operation', unpaid)
    monkeypatch.setattr(jury, '_client', lambda: SimpleNamespace(messages=SimpleNamespace(create=None)))
    flat = png(tmp_path, 'flat.png', (120, 30, 70), (300, 190))
    proof = png(tmp_path, 'proof.png', (200, 160, 90), (300, 190))
    args = dict(anchors=([], {}), facts='F', operation='day9/t/J1')
    with pytest.raises(ValueError, match='judged only under'):
        jury.ask('J1', flat, destination=tmp_path / 'a.json', rubric_version='v2', proof=proof, **args)
    with pytest.raises(ValueError, match='finish proof comes with each candidate'):
        jury.ask('J2', flat, destination=tmp_path / 'b.json', rubric_version='v2p', **args)
    same = tmp_path / 'same.png'
    shutil.copyfile(flat, same)
    with pytest.raises(ValueError, match='the flat build itself'):
        jury.ask('J1', flat, destination=tmp_path / 'c.json', rubric_version='v2p', proof=same, **args)
    jpeg = tmp_path / 'proof.jpg'
    Image.new('RGB', (64, 40), (200, 160, 90)).save(jpeg, format='JPEG')
    with pytest.raises(ValueError, match='must be a PNG'):
        jury.ask('J1', flat, destination=tmp_path / 'd.json', rubric_version='v2p', proof=jpeg, **args)
    # a record already there that was not asked about this proof is refused, never read back as this proof's verdict
    other = png(tmp_path, 'other-proof.png', (90, 160, 200), (300, 190))
    for name, sent in (('other.json', {'proof_sha256': sha(other)}), ('none.json', {'candidate_sha256': sha(flat)})):
        (tmp_path / name).write_text(json.dumps({'sent': sent, 'payload': None}))
        with pytest.raises(ValueError, match='was not asked about this finish proof'):
            jury.ask('J1', flat, destination=tmp_path / name, rubric_version='v2p', proof=proof, **args)
    (tmp_path / 'same.json').write_text(json.dumps({'sent': {'proof_sha256': sha(proof)}, 'payload': None}))
    assert jury.ask('J1', flat, destination=tmp_path / 'same.json', rubric_version='v2p', proof=proof, **args)['payload'] is None
    # the Day 9 ranking and idea check carry no proof, so never v2p; a ranking's measured lines match its sketches
    ranking = dict(anchors=([], {}), facts='F', spec='S', direction_idea='I', operation='day9/t/rank')
    with pytest.raises(ValueError, match='finish proof comes with each candidate'):
        jury.rank_sketches_v2([flat], destination=tmp_path / 'r.json', rubric_version='v2p', **ranking)
    with pytest.raises(ValueError, match='finish proof comes with each candidate'):
        jury.idea_check_v2('S', anchors=([], {}), facts='F', operation='day9/t/idea', destination=tmp_path / 'i.json',
                           rubric_version='v2p')
    with pytest.raises(ValueError, match='One measured line per sketch'):
        jury.rank_sketches_v2([flat, proof], destination=tmp_path / 'r.json', checks=['only one'], **ranking)
    with pytest.raises(ValueError, match='No sketches'):
        jury.rank_sketches_v2([], destination=tmp_path / 'r.json', **ranking)
    assert not [n for n in ('a.json', 'b.json', 'c.json', 'd.json', 'r.json', 'i.json') if (tmp_path / n).exists()]


# --- desirability (D-D9-7) -------------------------------------------------------------------------------------------

def test_a_no_to_either_question_is_a_top_issue_set_first_and_never_a_cap():
    many = [{'observation': f'issue {i}', 'location': 'lid', 'repair': 'fix'} for i in range(5)]
    base = jury.combine(record(payload(9.0, top_issues=many)), record(payload(9.0, top_issues=many)))
    out = jury.combine(record(payload(9.0, top_issues=many, would_buy_partly_for_the_lid=False, would_photograph_it=False,
                                      desirability_why='too polite for her')),
                       record(payload(9.0, top_issues=many)))
    # first, so the cut to ten (J1's five and J2's five) never drops them
    assert [i['observation'] for i in out['top_issues'][:2]] == ['J1: she would not buy it partly for the lid — too polite for her',
                                                                 'J1: she would not photograph it — too polite for her']
    assert out['top_issues'][2:] == base['top_issues'][:8] and len(out['top_issues']) == 10
    assert out['verdict']['issues'][0].startswith('J1: she would not buy it partly for the lid — too polite for her (the whole lid). ')
    # never a cap: the scores, the caps and the decision are the ones without the answers
    assert out['capped'] == base['capped'] and out['caps_applied'] == base['caps_applied'] == []
    assert out['verdict']['passed'] is True and out['verdict']['score'] == base['verdict']['score']
    # one "no", no why: one issue, its words alone
    one = jury.combine(record(payload(9.0, would_buy_partly_for_the_lid=True, would_photograph_it=False, desirability_why=' ')),
                       record(payload(9.0)))
    assert [i['observation'] for i in one['top_issues']] == ['J1: she would not photograph it']
    # two yeses, a Day 8 payload (no answers) and a J2 that answered anyway add nothing
    plain = jury.combine(record(payload(9.0)), record(payload(9.0)))
    for j1, j2 in ((payload(9.0, would_buy_partly_for_the_lid=True, would_photograph_it=True, desirability_why='yes'), payload(9.0)),
                   (payload(9.0), payload(9.0, would_buy_partly_for_the_lid=False, would_photograph_it=False))):
        out = jury.combine(record(j1), record(j2))
        assert {k: v for k, v in out.items() if k != 'raw'} == {k: v for k, v in plain.items() if k != 'raw'}


def test_j1s_desirability_is_three_flat_fields_and_the_schema_stays_small():
    """Under v2p J1's schema gains exactly three flat fields after Day 8's nineteen; nothing else changes. The grammar
    stays small: no object added (three, as in Day 8's accepted schema), three properties more, about 10 % more bytes —
    far under the first schema the provider refused on Day 8 ("the compiled grammar is too large": 4,586 bytes, 14
    objects, 73 properties)."""
    day8, day9 = jury.verdict_schema('J1'), jury.verdict_schema('J1', desirability=True)
    assert list(day9['properties'])[-3:] == list(DESIRABILITY) and day9['required'][-3:] == list(DESIRABILITY)
    assert [day9['properties'][k] for k in DESIRABILITY] == [{'type': 'boolean'}, {'type': 'boolean'}, {'type': 'string'}]
    stripped = copy.deepcopy(day9)
    for key in DESIRABILITY:
        del stripped['properties'][key]
        stripped['required'].remove(key)
    assert stripped == day8
    assert hashlib.sha256(json.dumps(day8, sort_keys=True).encode()).hexdigest() == DAY8_SHA256['verdict_J1']
    assert len(objects(day8)) == 3 and len(objects(day9)) == 3
    assert sum(len(o['properties']) for o in objects(day8)) == 27 and sum(len(o['properties']) for o in objects(day9)) == 30
    assert len(json.dumps(day8, separators=(',', ':'))) == 1904 and len(json.dumps(day9, separators=(',', ':'))) <= 2200
    with pytest.raises(ValueError, match='Only J1'):
        jury.verdict_schema('J2', desirability=True)
    # the audience, in the owner's words, in J1's Day 9 role only
    assert jury.AUDIENCE == AUDIENCE
    assert jury._role('J1', audience=True) == {'type': 'text', 'text': 'YOUR ROLE. ' + jury.ROLE_J1 + ' The palette is made '
                                               'for its audience, ' + AUDIENCE + ': you also answer for her.'}
    with pytest.raises(ValueError, match='Only J1'):
        jury._role('J2', audience=True)
    assert 'desirability_why — why, in at most 15 words' in jury.DESIRABILITY_WORDS


# --- the sketch ranking v2 and the idea check v2 --------------------------------------------------------------------

def test_the_ranking_v2_and_idea_check_v2_schemas_are_strict_flat_and_carry_no_length_keywords():
    day9 = {'RANK_SCHEMA_V2': jury.RANK_SCHEMA_V2, 'IDEA_SCHEMA_V2': jury.IDEA_SCHEMA_V2,
            'J1 verdict under v2p': jury.verdict_schema('J1', desirability=True)}
    for name, schema in day9.items():
        for node in objects(schema):
            assert node['additionalProperties'] is False and node['required'] == list(node['properties']), name
        assert not {k for node in walk(schema) for k in node} & NO_LENGTH_KEYWORDS, name
        blob = json.dumps(schema)                    # as Day 8's test_no_array_length_keywords_reach_the_api reads it
        assert 'maxItems' not in blob and 'minItems' not in blob and 'minimum' not in blob and 'maximum' not in blob, name
        assert len(json.dumps(schema, separators=(',', ':'))) <= 2200, name
    row, day8_row = (s['properties']['ranking']['items'] for s in (jury.RANK_SCHEMA_V2, jury.RANK_SCHEMA))
    assert list(row['properties'])[:7] == list(day8_row['properties'])
    assert {k: row['properties'][k] for k in day8_row['properties']} == day8_row['properties']
    assert list(row['properties'])[7:] == ['would_buy_partly_for_the_lid', 'would_photograph_it', 'desirability_why',
                                           'must_rebuild', 'richness_survives_rebuild', 'buildability_why']
    assert row['properties']['must_rebuild'] == {'type': 'array', 'items': {'type': 'string', 'enum': [
        'lettering', 'logo', 'foil_or_metallic', 'geometric_structure', 'painted_relief']}}
    assert len(objects(jury.RANK_SCHEMA_V2)) == 2 and len(objects(jury.IDEA_SCHEMA_V2)) == 1     # flat: no nested object
    assert jury.RANK_SCHEMA_V2['required'] == ['ranking', 'best_two', 'note']
    assert jury.IDEA_SCHEMA_V2['properties'] == {
        'reaches_nine_if_executed_perfectly': {'type': 'boolean'}, 'ceiling': {'type': 'number'},
        'would_buy_partly_for_the_lid': {'type': 'boolean'}, 'another_brand_could_own_it': {'type': 'boolean'},
        'why': {'type': 'string'}, 'what_would_lift_it': {'type': 'string'}}


def test_rank_sketches_v2_asks_desirability_and_buildability_through_an_injected_client(tmp_path, settings, monkeypatch):
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    monkeypatch.setattr(jury, '_client', no_default_client)
    sketches = [png(tmp_path, f's{i}.png', (40 * i, 20, 60), (1536, 970)) for i in range(1, 4)]
    anchors = anchor_set(tmp_path)
    client = FakeClient({'ranking': [rank_row(2, 1), rank_row(1, 2), rank_row(3, 3)], 'best_two': [2, 1, 3], 'note': 'n'})
    rec = jury.rank_sketches_v2(sketches, anchors=anchors, facts='F', spec='S', direction_idea='I',
                                operation='day9/test/rank-A', destination=tmp_path / 'rank.json',
                                checks=['OCR 1', 'OCR 2', 'OCR 3'], model='test-model', client=client,
                                reservation_prefix='day9/test/', reservation_cap=10.0)
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request['output_config']['format']['schema'] == jury.RANK_SCHEMA_V2
    assert request['output_config']['effort'] == 'medium' and request['max_tokens'] == jury.RANK_V2_MAX_OUTPUT_TOKENS
    assert request['system'] == jury._system('v2')
    content = request['messages'][0]['content']
    assert content[:6] == anchors[0] and content[6] == jury._role('J1', audience=True)
    texts = [b['text'] for b in content if b['type'] == 'text']
    assert texts[3].startswith('SKETCHES (Day 9). 3 ideas for the same direction, flat lid artwork, numbered 1–3 in order.')
    assert texts[3].endswith('A sketch whose richness lives in model-drawn lettering, painted gold or fake engraving ranks lower.')
    assert jury.BUILD_RULES in texts[3]
    assert texts.index('Sketch 1:') < texts.index('Measured by code on sketch 1: OCR 1') < texts.index('Sketch 2:')
    assert [image_bytes(b) for b in content if b['type'] == 'image'][4:] == [
        jury.resized_png(p, long_edge=jury.SKETCH_EDGE_PX)[0] for p in sketches]
    for words in ('Rank all 3 (1 = best)', 'why it ranks there (at most 40 words)', 'would_buy_partly_for_the_lid',
                  'would_photograph_it', 'desirability_why (at most 15 words)', 'must_rebuild (which of lettering, logo, '
                  'foil or metallic, geometric structure and painted relief', 'richness_survives_rebuild',
                  'buildability_why (at most 15 words)'):
        assert words in texts[-1]
    assert rec['kind'] == 'sketch_ranking_v2' and rec['audience'] == AUDIENCE and rec['rubric_version'] == 'v2'
    assert rec['payload']['best_two'] == [2, 1] and rec['ranked_every_sketch_once'] is True
    assert rec['payload']['ranking'][2]['richness_survives_rebuild'] is False
    assert rec['checks'] == ['OCR 1', 'OCR 2', 'OCR 3'] and [s['sha256'] for s in rec['sketches']] == [sha(p) for p in sketches]
    assert rec['reservation_id'] and rec['stop_reason'] == 'end_turn' and rec['parse_error'] == ''
    assert json.loads((tmp_path / 'rank.json').read_text()) == rec
    with pytest.raises(ValueError, match='immutable'):
        jury.rank_sketches_v2(sketches, anchors=anchors, facts='F', spec='S', direction_idea='I', operation='day9/test/rank-A',
                              destination=tmp_path / 'rank.json', client=client)
    assert len(client.requests) == 1


def test_idea_check_v2_asks_the_three_questions_through_an_injected_client(tmp_path, settings, monkeypatch):
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    monkeypatch.setattr(jury, '_client', no_default_client)
    answer = {'reaches_nine_if_executed_perfectly': False, 'ceiling': 8.5, 'would_buy_partly_for_the_lid': True,
              'another_brand_could_own_it': True, 'why': 'w', 'what_would_lift_it': 'l'}
    client = FakeClient(answer)
    rec = jury.idea_check_v2('THE SPEC', anchors=([], {}), facts='THE FACTS', operation='day9/test/idea-1',
                             destination=tmp_path / 'idea.json', model='test-model', client=client,
                             reservation_prefix='day9/test/', reservation_cap=10.0)
    request = client.requests[0]
    assert request['output_config']['format']['schema'] == jury.IDEA_SCHEMA_V2 and request['system'] == jury._system('v2')
    assert request['output_config']['effort'] == 'high' and request['max_tokens'] == jury.MAX_OUTPUT_TOKENS
    content = request['messages'][0]['content']
    assert content[0] == jury._role('J1', audience=True) and len(content) == 2
    text = content[1]['text']
    for words in ('(1) Executed perfectly by a senior designer, would the lid reach 9 on the scale? Give the ceiling you see.',
                  '(2) Would she, the audience named in your role, buy the palette partly for its lid?',
                  '(3) Could another brand own this idea', 'True means it is NOT ownable', jury.BUILD_RULES,
                  'THE PRODUCT:\nTHE FACTS', 'THE SPEC:\nTHE SPEC'):
        assert words in text
    assert text.index('(1)') < text.index('(2)') < text.index('(3)')
    assert rec['kind'] == 'idea_check_v2' and rec['payload'] == answer and rec['audience'] == AUDIENCE
    assert rec['stop_reason'] == 'end_turn' and rec['parse_error'] == '' and rec['reservation_id']
    assert json.loads((tmp_path / 'idea.json').read_text()) == rec


def test_a_cut_or_unreadable_answer_is_recorded_as_none_never_guessed(tmp_path, settings, monkeypatch):
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    monkeypatch.setattr(jury, '_client', no_default_client)
    cut = FakeClient(Answer({'reaches_nine_if_executed_perfectly': True}, stop_reason='max_tokens'))
    rec = jury.idea_check_v2('S', anchors=([], {}), facts='F', operation='day9/test/idea-cut', destination=tmp_path / 'cut.json',
                             model='test-model', client=cut, reservation_prefix='day9/test/', reservation_cap=10.0)
    assert rec['stop_reason'] == 'max_tokens' and rec['payload'] is None and rec['parse_error'] == ''
    garbled = FakeClient(Answer(None, text='{"ranking": ['))
    sketch = png(tmp_path, 's.png', (40, 20, 60), (300, 190))
    rec = jury.rank_sketches_v2([sketch], anchors=([], {}), facts='F', spec='S', direction_idea='I',
                                operation='day9/test/rank-cut', destination=tmp_path / 'garbled.json', model='test-model',
                                client=garbled, reservation_prefix='day9/test/', reservation_cap=10.0)
    assert rec['payload'] is None and rec['parse_error'] and rec['ranked_every_sketch_once'] is None


def test_ranked_every_sketch_once_is_measured_never_assumed():
    def answer(*numbers):
        return {'ranking': [{'sketch': n} for n in numbers]}

    assert jury._ranked_every_sketch_once(answer(2, 1, 3), 3) is True
    assert jury._ranked_every_sketch_once(answer(1, 1, 3), 3) is False          # one sketch twice, another never
    assert jury._ranked_every_sketch_once(answer(1, 2), 3) is False
    assert jury._ranked_every_sketch_once(answer(1, 2, True), 3) is False       # a boolean is no sketch number
    assert jury._ranked_every_sketch_once(None, 3) is None
    assert jury._ranked_every_sketch_once({'ranking': 'all'}, 3) is None


# --- Day 8's records replay unchanged --------------------------------------------------------------------------------

def test_day8s_recorded_verdicts_replay_unchanged_through_normalise_combine_and_judge(tmp_path, monkeypatch):
    """Every Day 8 verdict (64: the builds, the stale-spec verdicts and both calibrations) re-combines from its own juror
    records to exactly what was recorded, and every juror payload is a fixed point of ``_normalise``. ``judge``, re-run
    on copies of the juror records, reads them back (no call) and writes the recorded verdict again: the same keys in
    the same order and the same values, the record paths aside. Read only: nothing under docs/audit/day-8 is written."""
    def unpaid(*args, **kwargs):
        raise AssertionError('a replay reached the payment')

    monkeypatch.setattr(jury, 'paid_operation', unpaid)
    folders = sorted(v.parent for v in DAY8.rglob('verdict.json'))
    assert len(folders) == 64
    kept = ('raw', 'capped', 'caps_applied', 'top_issues', 'verdict')
    for i, folder in enumerate(folders):
        recorded = json.loads((folder / 'verdict.json').read_text())
        j1, j2 = (json.loads((folder / f'{juror}.json').read_text()) for juror in ('J1', 'J2'))
        for rec in (j1, j2):
            assert jury._normalise(copy.deepcopy(rec['payload'])) == rec['payload'], folder
        out = json.loads(json.dumps(jury.combine(copy.deepcopy(j1), copy.deepcopy(j2)), ensure_ascii=False))
        assert {k: out[k] for k in kept} == {k: recorded[k] for k in kept}, folder
        replay = tmp_path / str(i)
        replay.mkdir()
        for juror in ('J1', 'J2'):
            shutil.copyfile(folder / f'{juror}.json', replay / f'{juror}.json')
        jury.judge(Path(recorded['candidate']), anchors=([], {}), facts='', operation_prefix='day9/replay',
                   destination_dir=replay, rubric_version=recorded['rubric_version'], times=recorded['times'])
        written = json.loads((replay / 'verdict.json').read_text())
        assert list(written) == list(recorded), folder                 # no Day 9 key on a Day 8 verdict
        assert dict(written, records=None) == dict(recorded, records=None), folder


def test_day8s_recorded_rankings_and_idea_checks_replay_unchanged():
    """Day 8's three rankings and six idea checks (and the first-call probe) are fixed points of ``_normalise`` and keep
    Day 8's shapes; each ranking names its six sketches exactly once."""
    rankings = sorted(DAY8.glob('sketches/ranking-*.json'))
    ideas = sorted(DAY8.glob('jury/idea-check/*/*.json'))
    assert len(rankings) == 3 and len(ideas) == 6
    row_keys = sorted(jury.RANK_SCHEMA['properties']['ranking']['items']['required'])
    for path in rankings:
        rec = json.loads(path.read_text())
        assert rec['kind'] == 'sketch_ranking' and jury._normalise(copy.deepcopy(rec['payload'])) == rec['payload']
        assert sorted(rec['payload']) == sorted(jury.RANK_SCHEMA['required'])
        assert all(sorted(row) == row_keys for row in rec['payload']['ranking'])
        assert rec['payload']['best_two'] == rec['payload']['best_two'][:2]
        assert jury._ranked_every_sketch_once(rec['payload'], 6) is True
    for path in ideas:
        rec = json.loads(path.read_text())
        assert rec['kind'] == 'idea_check' and sorted(rec['payload']) == sorted(jury.IDEA_SCHEMA['required'])
        assert jury._normalise(copy.deepcopy(rec['payload'])) == rec['payload']
    probe = json.loads((DAY8 / 'jury' / 'probe' / 'ES3083-C4-J1-first-call.json').read_text())
    assert jury._normalise(copy.deepcopy(probe['payload'])) == probe['payload']


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
RANK_ROW = jury.RANK_SCHEMA_V2['properties']['ranking']['items']['properties']
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


def _verdict(cid, j1, j2):
    """``jury.combine`` on the two reviews (j2 None: a juror returned nothing, so the review is pending)."""
    second = {'payload': None if j2 is None else _payload(j2, 'J2', cid)}
    return dict(jury.combine({'payload': _payload(j1, 'J1', cid)}, second), rubric_version='v2p')


def _png(path, size, colour):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, colour).save(path)
    return path


def _build_folder(root, cid, *, direction, sketch, j1, j2, finish=FINISH, repair_of=None, skip=(), shade=0, issues=()):
    folder = root / 'concepts' / cid
    (folder / 'jury').mkdir(parents=True, exist_ok=True)
    build = {'schema': 'day9_build/1', 'concept': cid, 'idea': cid[:3], 'direction': direction,
             'idea_name': f'Idea {cid[:3]}', 'idea_line': f'The idea line of {cid}.', 'sketch': sketch, 'plate_path': 'a',
             'lettering': {'face': 'Instrument Serif', 'stem': 'InstrumentSerif-Regular',
                           'licence': 'SIL Open Font License, Version 1.1',
                           'ops': ['an En ligature', 'a swash R', 'optical kerning'], 'cap_mm': 14.0},
             'arabic': {'face': 'Noto Naskh Arabic', 'stem': 'NotoNaskhArabic-Bold',
                        'licence': 'SIL Open Font License, Version 1.1'},
             'checks_hold': not issues, 'issues': list(issues), 'cannot_meet': [], 'finish': dict(finish), 'repair_of': repair_of}
    files = {'build.json': json.dumps(build, ensure_ascii=False), 'jury/verdict.json': json.dumps(_verdict(cid, j1, j2)),
             'media-map.json': '{"schema": "day9_media_map/1"}', 'checks.json': '{"all_hold": true}',
             'designer-eye.json': '{"differences": []}', 'truthful.ai': '%PDF-1.7 ai ' + cid,
             'truthful.pdf': '%PDF-1.7 pdf ' + cid, 'truthful.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>'}
    for name, text in files.items():
        if name not in skip:
            (folder / name).write_text(text, encoding='utf-8')
    for name, size, colour in (('truthful.png', LID_PX, (43, 23, 41 + shade)), ('finish-proof.png', LID_PX, (90, 70, 40 + shade)),
                               ('name-1to1.png', NAME_PX, (250, 243, 236)), ('arabic-1to1.png', ARABIC_PX, (250, 243, 236)),
                               ('finish-sheet.png', (190, 120), (246, 246, 246))):
        if name not in skip:
            _png(folder / name, size, colour)
    return folder


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


def _ranking(root, monkeypatch, direction, sids, rows, best_two, *, stop_reason='end_turn'):
    """J1's ranking of a direction's sketches, written by ``jury.rank_sketches_v2`` itself on a fake answer ($0)."""
    text = json.dumps({'ranking': rows, 'best_two': best_two, 'note': 'fixture'})
    monkeypatch.setattr(jury, 'paid_operation', lambda invoke, **kwargs: _Answer(
        text if stop_reason == 'end_turn' else text[:40], stop_reason))
    path = root / 'sketches' / f'ranking-{direction}.json'
    path.unlink(missing_ok=True)                            # the producer refuses to overwrite; a test may write again
    return jury.rank_sketches_v2([root / 'sketches' / s / 'lid.png' for s in sids], anchors=([], {}), facts='facts',
                                 spec='spec', direction_idea='idea', operation=f'day9/sketches/rank-{direction}',
                                 destination=path, model='test-model',
                                 client=SimpleNamespace(messages=SimpleNamespace(create=None)))


A_SKETCHES = ['A-1.1', 'A-1.2', 'A-2.1']


def _round(root, monkeypatch):
    """Seven build folders over three directions: A ties on the stricter mean (A-2 wins on both jurors' mean), B's
    repair beats its first build on the stricter mean though both jurors' mean is lower, C-2's review is pending and
    C-3 lacks its finish proof; nine sketches, one of them never ranked."""
    for i, sid in enumerate((*A_SKETCHES, 'B-1.1', 'B-2.1', 'C-1.1', 'C-2.1', 'C-3.1', 'X-loose')):
        _png(root / 'sketches' / sid / 'lid.png', (48, 32), (10 * i, 20, 30))
    _ranking(root, monkeypatch, 'A', A_SKETCHES, [_row(3, 1, 7.9), _row(1, 2, 7.6), _row(2, 3, 7.0)], [3, 1])
    _ranking(root, monkeypatch, 'B', ['B-1.1', 'B-2.1'], [_row(1, 1, 7.4), _row(2, 2, 7.1)], [1, 2])
    _ranking(root, monkeypatch, 'C', ['C-1.1', 'C-2.1', 'C-3.1'], [_row(1, 1, 7.5), _row(2, 2, 7.2), _row(3, 3, 7.0)], [1, 2])
    _build_folder(root, 'A-1', direction='A', sketch='A-1.1', j1=7.0, j2=7.0, shade=1)
    _build_folder(root, 'A-2', direction='A', sketch='A-2.1', j1=7.5, j2=7.0, shade=2)
    _build_folder(root, 'B-1', direction='B', sketch='B-1.1', j1=6.5, j2=7.2, shade=3)
    _build_folder(root, 'B-1-r1', direction='B', sketch='B-1.1', j1=6.8, j2=6.6, repair_of='B-1', shade=4)
    _build_folder(root, 'C-1', direction='C', sketch='C-1.1', j1=7.2, j2=6.9, shade=5,
                  issues=['plate seam prints: 17 arc(s) of region 0 over ΔE00 3.0 on the colour across it'])
    _build_folder(root, 'C-2', direction='C', sketch='C-2.1', j1=7.0, j2=None, shade=6)
    _build_folder(root, 'C-3', direction='C', sketch='C-3.1', j1=7.0, j2=7.0, skip=('finish-proof.png',), shade=7)
    (root / 'jury').mkdir(parents=True, exist_ok=True)
    (root / 'jury' / 'proof-effect.json').write_text(json.dumps(PROOF))
    return root


@pytest.fixture
def day9(tmp_path, monkeypatch):
    root = _round(tmp_path / 'day-9', monkeypatch)
    monkeypatch.setattr(day9_pick, 'DAY9', root)
    monkeypatch.setattr(day9_pick, 'RECORD', root / 'pick' / 'publication.json')
    return root


# --- the record ------------------------------------------------------------------------------------------------------

def test_day9pick_the_reader_reads_the_producers_own_field_names():
    """The task named a nested desirability object and nested ranking objects; the producers write flat fields (a
    smaller compiled grammar). The reader takes jury's names, and fails here first if they move."""
    assert set(day9_pick.DESIRABILITY_KEYS) == set(jury.DESIRABILITY_FIELDS)
    assert set(day9_pick.RANKING_ROW_KEYS) <= set(RANK_ROW) and set(_row(1, 1, 7.0)) == set(RANK_ROW)
    assert set(_row(1, 1, 7.0)['must_rebuild']) <= set(jury.MUST_REBUILD)


def test_day9pick_the_sheet_is_the_best_build_of_each_direction_with_the_tie_rule(day9):
    record = day9_pick.publish()
    assert record['passing'] == [] and record['below_the_bar'] == ['A-2', 'C-1', 'B-1-r1'] == record['shown']
    assert record['ranking'] == ['A-2', 'A-1', 'C-1', 'B-1-r1', 'B-1']            # C-2 is pending: never ranked
    by_id = {b['id']: b for b in record['builds']}
    assert (by_id['A-1']['stricter_mean'], by_id['A-2']['stricter_mean']) == (7.0, 7.0)
    assert (by_id['A-1']['both_mean'], by_id['A-2']['both_mean']) == (7.0, 7.25)
    assert by_id['B-1-r1']['stricter_mean'] > by_id['B-1']['stricter_mean'] and by_id['B-1-r1']['both_mean'] < by_id['B-1']['both_mean']
    assert by_id['C-2']['judged'] is False and by_id['C-2']['status'] == 'review_pending' and by_id['C-2']['scores'] is None
    assert record['left_out'] == [{'id': 'C-3', 'missing': ['finish-proof.png']}] and 'C-3' not in by_id
    assert json.loads(day9_pick.RECORD.read_text())['below_the_bar'] == ['A-2', 'C-1', 'B-1-r1']
    # a tie on both means keeps the folder order; each direction gives one build
    rows = [{'id': i, 'direction': d, 'judged': True, 'stricter_mean': s, 'both_mean': b}
            for i, d, s, b in (('A-a', 'A', 7.0, 7.1), ('A-b', 'A', 7.0, 7.1), ('B-a', 'B', 7.0, 7.1), ('C-a', 'C', 6.0, 9.0))]
    assert day9_pick.best_of_each_direction(rows) == ['A-a', 'B-a', 'C-a']
    assert day9_pick.best_of_each_direction(list(reversed(rows))) == ['B-a', 'A-b', 'C-a']


def test_day9pick_a_passing_build_is_shown_and_no_sheet_is_made(day9):
    _build_folder(day9, 'B-2', direction='B', sketch='B-2.1', j1=8.5, j2=8.6, shade=9)
    record = day9_pick.publish()
    assert record['passing'] == ['B-2'] == record['shown'] and record['below_the_bar'] == []
    passing = next(b for b in record['builds'] if b['id'] == 'B-2')
    assert passing['passes'] is True and passing['status'] == 'accepted' and passing['capped_mean'] == 8.5


def test_day9pick_the_verdict_and_the_build_are_read_exactly(day9):
    record = day9_pick.publish()
    a2 = next(b for b in record['builds'] if b['id'] == 'A-2')
    assert a2['raw_means'] == {'J1': 7.5, 'J2': 7.0} and a2['status'] == 'rejected' and a2['passes'] is False
    assert a2['rubric'] == 'v2p' and 'rubric v2 ' not in record['gate']               # Day 9 judges under v2p (D-D9-6)
    assert a2['scores']['beauty'] == {'J1': 7.5, 'J2': 7.0, 'stands': 7.0} and set(a2['scores']) == set(DIMENSIONS)
    assert a2['desirability'] == DESIRE
    assert a2['juror_issues']['J1'][0]['observation'] == 'J1 finding on A-2' and a2['juror_issues']['J2'][0]['repair'] == 'J2 repair on A-2'
    # J1's "no" is a top issue the verdict's rules set (D-D9-7), kept beside the jurors' own
    assert [i['observation'] for i in a2['rule_issues']] == ['J1: she would not photograph it — ' + DESIRE_WHY]
    assert a2['lettering']['ops'] == ['an En ligature', 'a swash R', 'optical kerning'] and a2['arabic']['stem'] == 'NotoNaskhArabic-Bold'
    assert a2['finish'] == dict(FINISH, area_floor_holds=True, lines_floor_holds=True)
    assert a2['pictures']['truthful'] == {'size_px': [1536, 970], 'off_lid_proportion_pct': 0.011}
    assert a2['name_crop'] == {'size_px': [1200, 240], 'width_mm': 50.8, 'height_mm': 10.16} and record['crop_dpi'] == 600
    assert day9_pick.finish_numbers(dict(FINISH, foil_metallic_pct=4.0, relief_pct=9.0))['area_floor_holds'] is False
    assert day9_pick.finish_numbers(dict(FINISH, foil_metallic_pct=4.0, relief_pct=15.0))['area_floor_holds'] is True
    assert day9_pick.finish_numbers(dict(FINISH, foil_metallic_pct=None, relief_pct=9.0))['area_floor_holds'] is None
    assert day9_pick.finish_numbers(dict(FINISH, lines_per_cm_densest=11.9))['lines_floor_holds'] is False
    assert day9_pick.finish_numbers(dict(FINISH, lines_per_cm_densest=None))['lines_floor_holds'] is None
    assert record['proof_effect'] == dict(PROOF, file='proof-effect')
    # a key the producers must write is never filled in: a build's finish number, J1's desirability answer
    build = json.loads((day9 / 'concepts' / 'A-1' / 'build.json').read_text())
    del build['finish']['relief_pct']
    (day9 / 'concepts' / 'A-1' / 'build.json').write_text(json.dumps(build))
    with pytest.raises(KeyError):
        day9_pick.publish()
    _build_folder(day9, 'A-1', direction='A', sketch='A-1.1', j1=7.0, j2=7.0, shade=1)
    verdict = json.loads((day9 / 'concepts' / 'A-1' / 'jury' / 'verdict.json').read_text())
    del verdict['raw']['J1']['desirability_why']
    (day9 / 'concepts' / 'A-1' / 'jury' / 'verdict.json').write_text(json.dumps(verdict))
    with pytest.raises(KeyError):
        day9_pick.publish()


def test_day9pick_sketch_numbers_are_read_through_the_rankings_own_sketch_list(day9, monkeypatch):
    record = day9_pick.publish()
    sketches = {s['id']: s for s in record['sketches']}
    assert [s['id'] for s in record['sketches']] == ['A-2.1', 'A-1.1', 'A-1.2', 'B-1.1', 'B-2.1', 'C-1.1', 'C-2.1', 'C-3.1',
                                                     'X-loose']
    assert (sketches['A-2.1']['rank'], sketches['A-2.1']['went_on'], sketches['A-1.2']['went_on']) == (1, True, False)
    assert sketches['B-1.1']['built_as'] == ['B-1', 'B-1-r1'] and sketches['C-3.1']['built_as'] == []
    assert sketches['A-2.1']['desirability'] == {'would_buy_partly_for_the_lid': True, 'would_photograph_it': True, 'why': 'jewel-like'}
    assert sketches['A-2.1']['buildability'] == {'must_rebuild': ['geometric_structure', 'foil_or_metallic'],
                                                 'richness_survives_rebuild': True, 'why': 'the ground carries the richness'}
    assert sketches['A-2.1']['ranked_bytes_hold'] is True
    assert sketches['X-loose']['ranked'] is False and sketches['X-loose']['rank'] is None
    assert record['rankings']['A'] == {'file': 'ranking-A', 'state': day9_pick.RANKED, 'best_two': ['A-2.1', 'A-1.1'], 'why': None}
    _png(day9 / 'sketches' / 'A-1.2' / 'lid.png', (48, 32), (1, 2, 3))              # not the bytes J1 ranked
    assert {s['id']: s for s in day9_pick.publish()['sketches']}['A-1.2']['ranked_bytes_hold'] is False


def test_day9pick_a_ranking_without_an_answer_is_said_and_ranks_none_of_its_sketches(day9, monkeypatch):
    rows = [_row(3, 1, 7.9), _row(1, 2, 7.6), _row(2, 3, 7.0)]
    _ranking(day9, monkeypatch, 'A', A_SKETCHES, rows, [3, 1], stop_reason='max_tokens')    # the answer was cut
    record = day9_pick.publish()
    assert record['rankings']['A'] == {'file': 'ranking-A', 'state': day9_pick.NO_ANSWER, 'best_two': [],
                                       'why': "J1's ranking returned no answer (stop reason max_tokens)"}
    a_rows = [s for s in record['sketches'] if s['id'] in A_SKETCHES]
    assert all(s['ranked'] is False and s['went_on'] is False for s in a_rows) and len(a_rows) == 3
    _ranking(day9, monkeypatch, 'A', A_SKETCHES, rows[:2], [3, 1])                         # sketch 2 left out
    assert day9_pick.publish()['rankings']['A']['state'] == day9_pick.NOT_EACH_ONCE
    _ranking(day9, monkeypatch, 'A', A_SKETCHES, rows, [3, 7])                              # a best two not among them
    assert day9_pick.publish()['rankings']['A'] == {'file': 'ranking-A', 'state': day9_pick.RANKED, 'best_two': ['A-2.1'],
                                                   'why': "J1's best two name 7, not among its 3 sketches"}
    path = day9 / 'sketches' / 'ranking-A.json'
    ranking = json.loads(path.read_text())
    ranking['payload']['ranking'][0]['sketch'] = 'A-1.1'                                    # says once, names a word
    path.write_text(json.dumps(ranking))
    with pytest.raises(ValueError, match='not one of its 3 sketches'):
        day9_pick.publish()
    ranking['kind'] = 'sketch_ranking'                                                      # Day 8's ranking record
    path.write_text(json.dumps(ranking))
    with pytest.raises(ValueError, match='sketch_ranking_v2'):
        day9_pick.publish()


def test_day9pick_every_file_is_pinned_and_checked_rehashes_each(day9):
    record = day9_pick.publish()
    a2 = next(b for b in record['builds'] if b['id'] == 'A-2')
    assert set(a2['files']) == {'truthful', 'proof', 'name', 'arabic', 'finishes', 'media', 'checks', 'eye', 'ai', 'pdf',
                                'svg', 'build', 'verdict'}
    for role in [*a2['files'].values(), 'sketch-A-2.1', 'ranking-A', 'proof-effect']:
        item = record['downloads'][role]
        assert item['sha256'] == _sha(day9 / item['path'])
    assert record['downloads']['A-2-ai']['mime'] == 'application/postscript'
    assert day9_pick.checked()['below_the_bar'] == record['below_the_bar']
    assert day9_pick.state()['state'] == day9_pick.PUBLISHED
    _png(day9 / 'concepts' / 'A-2' / 'finish-proof.png', LID_PX, (0, 0, 0))
    with pytest.raises(day9_pick.Changed, match='A-2-proof'):
        day9_pick.checked()
    with pytest.raises(day9_pick.Changed):
        day9_pick.checked_file('A-2-proof')
    assert day9_pick.checked_file('A-2-truthful')[0].name == 'truthful.png'        # its own bytes still hold
    assert day9_pick.state() == {'state': day9_pick.CHANGED,
                                 'why': 'A-2-proof (concepts/A-2/finish-proof.png) changed since it was published'}
    (day9 / 'sketches' / 'X-loose' / 'lid.png').unlink()
    day9_pick.publish()
    (day9 / 'jury' / 'proof-effect.json').unlink()
    assert 'is gone since it was published' in day9_pick.state()['why']
    day9_pick.RECORD.write_text('{"downloads": ')
    assert day9_pick.state()['state'] == day9_pick.UNREADABLE


def test_day9pick_no_complete_build_refuses_and_day8_is_never_written(day9, tmp_path, monkeypatch):
    for folder in (day9 / 'concepts').iterdir():
        (folder / 'truthful.svg').unlink(missing_ok=True)
    with pytest.raises(ValueError, match='no Day 9 build is complete'):
        day9_pick.publish()
    assert not day9_pick.RECORD.exists() and day9_pick.state() == {'state': day9_pick.BEING_BUILT}
    day8 = tmp_path / 'day-8'
    monkeypatch.setattr(day9_pick, 'DAY8', day8)
    monkeypatch.setattr(day9_pick, 'RECORD', day8 / 'pick' / 'publication.json')
    with pytest.raises(ValueError, match='hash-pinned'):
        day9_pick.publish()
    assert not day8.exists()


def test_day9pick_the_section_says_each_rankings_state(day9, monkeypatch):
    """The view and the section template without a database: a ranking J1 did not answer is said for its direction."""
    from django.template.loader import render_to_string
    from apps.dashboard import day8_views
    _ranking(day9, monkeypatch, 'C', ['C-1.1', 'C-2.1', 'C-3.1'], [_row(1, 1, 7.5)], [1], stop_reason='max_tokens')
    day9_pick.publish()
    section = day8_views._day9()
    assert section['ranking_notes'] == [('C', "J1's ranking returned no answer (stop reason max_tokens)",
                                         '/dashboard/day9/files/ranking-C/', True)]
    html = render_to_string('dashboard/day9_pick_section.html', {'day9': section})
    assert ('Direction C: J1&#x27;s ranking returned no answer (stop reason max_tokens) — its sketches are shown unranked'
            in html) and 'C-1.1 · not ranked' in html
    assert 'must rebuild: geometric structure; foil or metallic' in html


def test_day9pick_an_unmeasured_finish_number_is_said_never_shown_as_none(day9):
    """A finish number the build could not measure (null in build.json) reads "not measured" on the build and "—" in
    the history; its floor is "not measured", never a pass."""
    from django.template.loader import render_to_string
    from apps.dashboard import day8_views
    _build_folder(day9, 'A-2', direction='A', sketch='A-2.1', j1=7.5, j2=7.0, shade=2,
                  finish=dict(FINISH, relief_pct=None, lines_per_cm_densest=None, foil_limits_hold=None))
    day9_pick.publish()
    html = render_to_string('dashboard/day9_pick_section.html', {'day9': day8_views._day9()})
    article = html[html.index('id="d9-A-2"'):html.index('id="d9-C-1"')]
    assert 'Foil or metallic ink: 12.4 % of the lid · relief: not measured — the area floor' in article
    assert 'at its densest: not measured — the floor (≥ 12): not measured' in article and 'None' not in article
    row = re.search(r'<tr><td><a href="[^"]*A-2-truthful/">A-2</a>.*?</tr>', html).group(0)
    assert row.endswith('<td>12.4</td><td>—</td><td>—</td></tr>')


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
def day8(tmp_path, monkeypatch):
    from apps.pipeline.services import day8_pick
    root = _day8(tmp_path / 'day-8')
    monkeypatch.setattr(day8_pick, 'DAY8', root)
    monkeypatch.setattr(day8_pick, 'RECORD', root / 'pick' / 'publication.json')
    return root


@pytest.fixture
def owner(client):
    from django.contrib.auth.models import User
    client.force_login(User.objects.create_superuser('owner9', 'o9@example.com', 'pw'))
    return client


def _day8_unchanged(body):
    """Day 8's own page test, read again below Day 9's section."""
    at = body.index('EYESHADOW PALETTE 124 · DAY 8')
    day8 = body[at:]
    assert 'Below the bar.' in day8 and 'X1 · Gravure' in day8 and 'the hero line is thin at 2 m' in day8
    assert 'width:84.0mm' in day8 and 'SIL Open Font License' in day8 and '/dashboard/day8/files/X1-truthful/' in day8
    return at


@pytest.mark.django_db
def test_day9pick_the_page_shows_day9_on_top_and_day8_below_unchanged(owner, day8, day9):
    day9_pick.publish()
    page = owner.get('/dashboard/palette-pick/')
    assert page.status_code == 200
    body = page.content.decode()
    assert body.index('DAY 9 · PALETTE ROUND 2') < _day8_unchanged(body)
    day9_part = body[:body.index('EYESHADOW PALETTE 124 · DAY 8')]
    # the proof's measured effect on the section's head
    assert "The finish proof moved Day 8's B3-r2 from 6.65 to 7.10</strong> on the stricter juror's mean (+0.45, rubric v2p)" in day9_part
    assert 'Below the bar.' in day9_part and day9_part.index('id="d9-A-2"') < day9_part.index('id="d9-C-1"') < day9_part.index('id="d9-B-1-r1"')
    article = day9_part[day9_part.index('id="d9-A-2"'):day9_part.index('id="d9-C-1"')]
    # the flat build and the finish proof side by side, at their own proportion
    pair = re.search(r'<div class="d9-pair">(.*?)</div>', article, re.S).group(1)
    assert pair.index('/dashboard/day9/files/A-2-truthful/') < pair.index('/dashboard/day9/files/A-2-proof/')
    assert pair.count('width="1536" height="970"') == 2
    # two columns at every width: no rule of the page's style stacks the pair
    style = body[body.index('<style>'):body.index('</style>')]
    pair_rules = [d for s, d in re.findall(r'([^{}]*)\{([^{}]*)\}', style) if 'd9-pair' in s]
    assert pair_rules and not any('grid-template-columns:1fr' in d for d in pair_rules)
    # the name and the Arabic at 1 : 1 (600 dpi crops drawn at 96 CSS px to the inch), the sketch, the jury, the finish
    assert '/dashboard/day9/files/A-2-name/" width="192" height="38"' in article
    assert '/dashboard/day9/files/A-2-arabic/" width="96" height="19"' in article
    assert 'The name, 50.8 × 10.16 mm at 1 : 1' in article
    assert '/dashboard/day9/files/sketch-A-2.1/' in article and 'J1 rank 1 · 7.9' in article
    assert 'Would she buy it partly for the lid? <strong>yes</strong> · Would she photograph it? <strong>no</strong>' in article
    assert DESIRE_WHY in article and 'J1: she would not photograph it — ' + DESIRE_WHY in article
    assert 'J1 finding on A-2' in article and 'J2 repair on A-2' in article
    assert '<td>colour contrast</td><td>7.5</td><td>7.0</td><td>7.0</td>' in article
    assert 'stricter 7.0 · both 7.25 · after the caps 7.0 · rejected · rubric v2p' in article
    assert 'Foil or metallic ink: 12.4 % of the lid · relief: 6.0 %' in article and 'at its densest: 14.2 lines per cm' in article
    assert 'an En ligature; a swash R; optical kerning' in article and 'Every measured check holds' in article
    # a build whose checks do not hold says which (C-1 on the sheet), never only that one fails
    c1 = day9_part[day9_part.index('id="d9-C-1"'):day9_part.index('id="d9-B-1-r1"')]
    assert ('<strong>Not every measured check holds:</strong> plate seam prints: 17 arc(s) of region 0 over ΔE00 3.0 '
            'on the colour across it') in c1
    # the history: every sketch and every build, the pending one and the one left out
    assert '<td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>review pending</td>' in day9_part
    assert 'C-3: finish-proof.png' in day9_part and 'X-loose · not ranked' in day9_part
    assert '<div class="d9-scroll"><table class="pick-scores">' in day9_part   # its 13 columns scroll in their box at phone width
    assert 'style="' not in day9_part
    # Day 8's tabs stay Day 8's, with Day 9 still on top
    for tab, words in (('history', 'went on to a build'), ('jury', 'Hourglass')):      # Day 8's own tab test
        other = owner.get('/dashboard/palette-pick/?tab=%s' % tab).content.decode()
        day8_at = other.index('EYESHADOW PALETTE 124 · DAY 8')
        assert other.index('DAY 9 · PALETTE ROUND 2') < day8_at and words in other[day8_at:]
        assert 'href="?tab=%s#day8"' % tab in other and '<header id="day8">' in other


def test_day9pick_the_names_lettering_is_said_in_words_from_the_shape_the_build_records():
    """build.json records the name's operations as lettering.logotype returns them — one list per line of the name,
    each a dict with its measured geometry; the page says them in words, never the dicts (the fixture's strings were
    not the shape production writes)."""
    from apps.dashboard.day8_views import _ops_said
    measured = {'centreline': [[53.7, 84.6], [54.6, 84.6]], 'thickness_mm': 0.457}
    recorded = [[{'op': 'join', 'kind': 'bridge', 'after': 't', 'height_em': 0.36, 'applied': True, 'pair': 'te', 'measured': measured},
                 {'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.04, 'applied': True, 'pair': 'Ro', 'measured': measured},
                 {'op': 'cut_in', 'at': 'R', 'shape': 'knockout', 'by': 'o', 'gap_em': 0.018, 'applied': True, 'glyph': 'R'}],
                [{'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.06], 'applied': True, 'glyph': 'R'},
                 {'op': 'alternate', 'at': 'E', 'feature': 'ss01', 'applied': False}]]
    said = _ops_said(recorded)
    assert said == ('a bridge joining te; Ro overlapped; R cut in under o, a hairline between them; '
                    'a swash from the bottom-right terminal of R; the ss01 alternate of E (not applied)')
    assert '{' not in said and 'measured' not in said
    assert _ops_said([[]]) == _ops_said([[], []]) == 'set as the face draws it (no lettering operation)'
    assert _ops_said(['an En ligature', 'a swash R']) == 'an En ligature; a swash R'


@pytest.mark.django_db
def test_day9pick_a_changed_day9_file_404s_on_its_route(owner, day8, day9):
    day9_pick.publish()
    served = owner.get('/dashboard/day9/files/A-2-proof/')
    assert served.status_code == 200 and served['Content-Type'] == 'image/png'
    assert b''.join(served.streaming_content) == (day9 / 'concepts' / 'A-2' / 'finish-proof.png').read_bytes()
    verdict = owner.get('/dashboard/day9/files/A-2-verdict/')
    assert verdict.status_code == 200 and verdict['Content-Type'] == 'application/json'
    assert 'attachment' in owner.get('/dashboard/day9/files/A-2-ai/')['Content-Disposition']
    assert owner.get('/dashboard/day9/files/no-such-role/').status_code == 404
    _png(day9 / 'concepts' / 'A-2' / 'finish-proof.png', LID_PX, (0, 0, 0))          # the bytes change after publishing
    assert owner.get('/dashboard/day9/files/A-2-proof/').status_code == 404
    page = owner.get('/dashboard/palette-pick/')
    assert page.status_code == 200
    body = page.content.decode()
    assert "Day 9's publication no longer matches its files: A-2-proof" in body and 'id="d9-A-2"' not in body
    _day8_unchanged(body)


@pytest.mark.django_db
def test_day9pick_with_no_day9_publication_the_page_says_being_built_and_serves_day8(owner, day8, tmp_path, monkeypatch):
    monkeypatch.setattr(day9_pick, 'DAY9', tmp_path / 'day-9-empty')
    monkeypatch.setattr(day9_pick, 'RECORD', tmp_path / 'day-9-empty' / 'pick' / 'publication.json')
    page = owner.get('/dashboard/palette-pick/')
    assert page.status_code == 200
    body = page.content.decode()
    assert "Day 9's round is being built." in body and body.index("Day 9's round is being built.") < _day8_unchanged(body)
    assert owner.get('/dashboard/day9/files/A-2-truthful/').status_code == 404
    assert owner.get('/dashboard/day8/files/X1-truthful/').status_code == 200
    _png(day8 / 'concepts' / 'X1' / 'truthful.png', (40, 25), (0, 0, 0))             # Day 8's own rule, unchanged
    assert owner.get('/dashboard/palette-pick/').status_code == 404


@pytest.mark.django_db
def test_day9pick_an_unreadable_day9_record_is_said_and_day8_still_serves(owner, day8, tmp_path, monkeypatch):
    record_path = tmp_path / 'day-9-odd' / 'pick' / 'publication.json'
    monkeypatch.setattr(day9_pick, 'DAY9', tmp_path / 'day-9-odd')
    monkeypatch.setattr(day9_pick, 'RECORD', record_path)
    record_path.parent.mkdir(parents=True)
    for text in ('{"downloads": ', json.dumps({'downloads': {}, 'sketches': [], 'builds': [], 'shown': ['nope'], 'passing': [],
                                               'crop_dpi': 600, 'proof_effect': None,
                                               'rankings': {'A': None, 'B': None, 'C': None}})):
        record_path.write_text(text)                        # broken JSON; then a record whose sheet names no build
        page = owner.get('/dashboard/palette-pick/')
        assert page.status_code == 200
        body = page.content.decode()
        assert "Day 9's publication could not be read" in body and body.index('could not be read') < _day8_unchanged(body)


@pytest.mark.django_db
def test_day9pick_the_page_and_day9s_files_need_a_member(client, day8, day9):
    from django.contrib.auth.models import User
    day9_pick.publish()
    client.force_login(User.objects.create_user('visitor9', 'v9@example.com', 'pw'))
    assert client.get('/dashboard/palette-pick/').status_code == 403
    assert client.get('/dashboard/day9/files/A-2-truthful/').status_code == 403
