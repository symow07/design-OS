"""The owner's part 3 (2026-10-31): a further shade by rule, the shade and bare-board checks on the chain, density by coverage."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.pipeline.services import round_files_faces as faces
from apps.pipeline.services import round_files_gate as gate
from apps.pipeline.services import round_flow as flow

FAMILY = [{'name': 'Rose Glass', 'hex': '#C9707A'}, {'name': 'Fig Nectar', 'hex': '#8E4A5C'}, {'name': 'Ember Glow', 'hex': '#C2553A'}]


@pytest.fixture
def a_round(tmp_path, settings, db):
    from django.contrib.auth import get_user_model
    from apps.pipeline.models import Round
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    owner = get_user_model().objects.create_superuser(username='part3-' + uuid4().hex, email='part3@example.invalid', password='fixture-password')
    brief = {'dimensions_mm': {'width': 15, 'depth': 15, 'height': 100, 'cap_height': 30}, 'shades': FAMILY, 'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss'}}
    return Round.objects.create(slug='part3-' + uuid4().hex, request_key=uuid4().hex, created_by=owner, product_brief=brief, state='complete', current_step='pick', budget_usd=2)


def test_a_further_shade_is_three_new_colours_told_apart_from_the_family_and_each_other():
    rows = faces.shade_candidates(FAMILY, '#1F3A33')
    assert len(rows) == 3
    assert not {row['hex'] for row in rows} & {shade['hex'] for shade in FAMILY}
    assert rows == faces.shade_candidates(FAMILY, '#1F3A33')                 # by rule: the same every time
    for row in rows:
        assert row['away_de'] >= faces.SHADE_APART_DE and row['name'] and row['why']
        assert not any(word in row['name'].lower() for word in ('rose', 'petal', 'arch', 'lip', 'kiss', 'drip', 'splash', 'honey', 'bee'))


def test_the_owners_wait_his_pick_and_the_engines_first_marked(a_round):
    proposals = gate.propose_shade(a_round, columns=4)
    assert gate.propose_shade(a_round, columns=4)['at'] == proposals['at']   # the wait starts once
    assert gate.resolve_shade(a_round) is None                              # he still has time
    assert len(gate.shades_of(a_round)) == 3
    late = timezone.now() + timedelta(minutes=gate.SHADE_PICK_MINUTES + 1)
    first = gate.resolve_shade(a_round, now=late)
    assert first['status'] == 'owner to confirm' and first['shade']['name'] == proposals['candidates'][0]['name']
    assert gate.shades_of(a_round)[-1]['fourth_status'] == 'owner to confirm'
    # his later word replaces it, and nothing replaces his
    (flow.round_root(a_round) / 'PICK').write_text('2\n')
    second = gate.resolve_shade(a_round, now=late)
    assert second['status'] == 'owner' and second['shade']['name'] == proposals['candidates'][1]['name']
    (flow.round_root(a_round) / 'PICK').write_text('3\n')
    assert gate.resolve_shade(a_round, now=late)['shade']['name'] == second['shade']['name']
    assert len(gate.shades_of(a_round)) == 4 and a_round.product_brief['shades'] == FAMILY


def test_a_pick_file_reads_a_name_or_his_own_colour_and_refuses_what_it_cannot_read(a_round):
    gate.propose_shade(a_round, columns=4)
    pick = flow.round_root(a_round) / 'PICK'
    pick.write_text('banana')
    with pytest.raises(ValueError, match='names no shade'):
        gate.resolve_shade(a_round)
    pick.write_text('Velvet Ochre #AA7711')
    assert gate.resolve_shade(a_round)['shade'] == {'name': 'Velvet Ochre', 'hex': '#AA7711'}


def test_a_column_carries_one_shade_left_to_right():
    assert [row['name'] for row in faces.column_shades(FAMILY + [{'name': 'Four', 'hex': '#111111'}], 4)] == ['Rose Glass', 'Fig Nectar', 'Ember Glow', 'Four']
    assert [row['column'] for row in faces.column_shades(FAMILY, 4)] == [1, 2, 3, 4]
