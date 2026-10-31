"""Folded fit and actual ink boundaries for the provisional regulated leaflet."""
import math

import pytest

from apps.pipeline.services import balm_leaflet


def test_six_panel_leaflet_fits_the_carton_with_arabic_read_from_the_right():
    result = balm_leaflet.layout()
    assert result['sheet_mm'] == [108, 71]
    assert result['folded_mm'] == [18, 71]
    assert result['planar_fit'] and result['provisional']
    assert result['panels'][0]['safe_mm'] == [1.5, 1.5, 16.5, 69.5]
    assert result['panels'][-1]['safe_mm'] == [91.5, 1.5, 106.5, 69.5]
    assert result['reading_order']['ar'] == ['ar1', 'ar2']
    assert result['panel_order_left_to_right'][-2:] == ['ar2', 'ar1']
    assert [fold['fold'] for fold in result['folds']] == ['valley', 'mountain', 'valley', 'mountain', 'valley']
    assert len(result['cuts']) == 4


def test_dimensions_follow_carton_interior_instead_of_a_fixed_sheet():
    result = balm_leaflet.layout((22, 22, 83))
    assert result['folded_mm'] == [20, 81]
    assert result['sheet_mm'] == [120, 81]


@pytest.mark.parametrize('inside', [(0, 20, 73), (4, 20, 73), (20, 20, 4),
                                    (20, -1, 73), (math.nan, 20, 73), (True, 20, 73), (20, 73)])
def test_impossible_or_invalid_carton_does_not_get_a_fit_claim(inside):
    with pytest.raises(ValueError):
        balm_leaflet.layout(inside)


def test_safe_text_holds_but_margin_intrusion_and_fold_crossing_do_not():
    geometry = balm_leaflet.layout()
    good = {'name': 'EN line 1', 'panel': 'en1', 'box_mm': [2, 3, 16, 5]}
    assert balm_leaflet.check_printed_lines(geometry, [good])['holds']
    margin = {'name': 'ES intrusion', 'panel': 'es1', 'box_mm': [36.45, 3, 50, 5]}
    crossing = {'name': 'Crossing', 'panel': 'en1', 'box_mm': [16, 6, 20, 8]}
    result = balm_leaflet.check_printed_lines(geometry, [good, margin, crossing])
    assert not result['holds'] and not result['all_inside_safe']
    assert result['crossings'] == 1
    assert [row['name'] for row in result['outside_safe_area']] == ['ES intrusion', 'Crossing']


def test_box_on_a_different_panel_is_not_accepted_as_its_named_panel():
    result = balm_leaflet.check_printed_lines(balm_leaflet.layout(), [
        {'name': 'Misplaced Arabic', 'panel': 'ar1', 'box_mm': [2, 3, 10, 5]}])
    assert not result['holds'] and result['crossings'] == 0


@pytest.mark.parametrize('rows', [[], [{'name': 'NaN', 'panel': 'en1', 'box_mm': [2, 3, math.nan, 5]}],
                                   [{'name': 'Flat', 'panel': 'en1', 'box_mm': [2, 3, 10, 3]}],
                                   [{'name': 'Unknown', 'panel': 'missing', 'box_mm': [2, 3, 10, 5]}]])
def test_missing_or_malformed_ink_evidence_cannot_pass(rows):
    with pytest.raises(ValueError):
        balm_leaflet.check_printed_lines(balm_leaflet.layout(), rows)
