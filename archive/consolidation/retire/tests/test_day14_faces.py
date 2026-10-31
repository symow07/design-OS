"""D-D14-2/6: real exported copy, preserved art and geometry, and embedded drawing fonts.

These are builder regression checks. They neither render previews nor replace the fresh Part B2 audit.
"""
import hashlib
import json
from pathlib import Path

import fitz
import pytest

from apps.pipeline.services import stick_carton as sc

REPO = Path(__file__).resolve().parents[4]
DAY13 = REPO / 'docs/audit/day-13'
DAY14 = REPO / 'docs/audit/day-14'


def load(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize('folder', ['lipstick', 'balm'])
def test_carton_copy_is_live_tajawal_and_front_and_die_are_preserved(folder):
    source, current = DAY13 / folder / 'carton', DAY14 / folder / 'carton'
    assert (current / 'front-picture.png').read_bytes() == (source / 'front-picture.png').read_bytes()
    assert (current / 'carton-translations.json').read_bytes() == (source / 'carton-translations.json').read_bytes()
    old, new = load(source / 'carton-fold-check.json'), load(current / 'carton-fold-check.json')
    assert new['die'] == old['die'] and new['faces'] == old['faces']
    assert new['front']['picture']['placed_mm'] == old['front']['picture']['placed_mm']
    with fitz.open(current / 'carton-artwork.pdf') as pdf:
        spans = [sp for p in pdf for b in p.get_text('dict')['blocks'] if 'lines' in b
                 for line in b['lines'] for sp in line['spans'] if sp['text'].strip()]
        assert spans and all('Tajawal' in sp['font'] for sp in spans)
        assert all(sp['size'] >= 5.0 - 0.001 for sp in spans)
        latin = [sp for sp in spans if any('A' <= c <= 'Z' or 'a' <= c <= 'z' for c in sp['text'])]
        # Arabic paragraphs retain their embedded Latin brand names in the same Tajawal-derived PF face.
        assert latin and 'Tajawal-Medium' in {sp['font'] for sp in latin}
        assert {sp['font'] for sp in latin} <= {'Tajawal-Medium', 'TajawalPF-Medium'}
        assert all('Tajawal' in f[3] and len(pdf.extract_font(f[0])[3]) > 0
                   for p in pdf for f in p.get_fonts(full=True))


@pytest.mark.parametrize('folder', ['lipstick', 'balm'])
def test_carton_floor_crossings_and_every_overflow_remain_explicit(folder):
    current = DAY14 / folder / 'carton'
    fit, fold = load(current / 'carton-fit-report.json'), load(current / 'carton-fold-check.json')
    assert fit['body']['floor_pt'] == 5.0 and fit['smallest_pt'] >= 5.0
    assert fit['copy']['all_found'] and not fit['copy']['dropped'] and not fit['copy']['moved']
    assert fold['fold_check']['passed'] and fold['zero_crossings']['crossings'] == 0
    assert fold['zero_crossings']['nothing_across_a_crease'] and fold['zero_crossings']['no_box_on_another_face']
    overflow = [ln for ln in fit['lines'] if not ln['fits']]
    assert fit['overflow'] == overflow
    for line in overflow:
        assert line['overflow_lies'] and not line['overflow_lies']['cut_off']
        assert line['overflow_lies']['onto_faces'] == []
    assert fit['marked']['arabic_claims_owner_to_confirm']
    assert fold['clean']['status'] == 'NOT_RUN' and fold['clean']['holds'] is None
    assert not (current / 'carton-flat.png').exists()


def test_a_refused_collection_face_cannot_be_substituted(monkeypatch):
    from apps.ire import font_roles
    monkeypatch.setattr(font_roles, 'resolve_line_face', lambda *args: {'refused': True})
    with pytest.raises(ValueError, match='did not verify'):
        sc.collection_faces()


def test_day14_construction_keeps_the_same_die_and_owner_visibility_ruling():
    source, current = DAY13 / 'display/die', DAY14 / 'display/die'
    assert (source / 'die.json').read_bytes() == (current / 'die.json').read_bytes()
    sight = load(current / 'sightlines.json')['insert_sway']
    assert sight['lid_min_visible_fraction'] == 1.0  # above-stick region, unchanged
    assert sight['whole_lid_min_visible_fraction'] >= 0.98  # existing threshold, unchanged
    assert sight['whole_lid_min_visible_fraction'] == 0.9841  # D-D14-6: prototype accepted by owner
    ruling = load(current / 'day14-readback.json')['visibility_ruling']
    assert 'D-D14-6' in ruling and '0.9841' in ruling
