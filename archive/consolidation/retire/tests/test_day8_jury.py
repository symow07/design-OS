"""Day 8 §3 — the jury's computed rules on fixtures: raw scores recorded before caps, the stricter juror, the pairwise
caps, the easy-to-make cap, the collection penalty, near-copy and banned-motif hard failures, the median record,
the cached anchor set and the strict output schema. No network: these never call a provider."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from apps.pipeline.services import jury
from apps.pipeline.services.concept_quality import DIMENSIONS


def payload(score=9.0, *, pairwise='clearly_better', **extra):
    base = {'dimensions': {k: {'score': score, 'observation': 'seen', 'location': 'lid', 'repair': 'none'} for k in DIMENSIONS},
            'hard_failures': [], 'banned_motif_seen': '', 'near_copy_of': '', 'observations': 'ok',
            'idea_read': 'a quiet gold line system on cream', 'idea_matches_direction': True, 'would_remove': '',
            'ai_or_template_signs': '', 'reads_first': 'name', 'reads_second': 'mark', 'reads_third': 'device',
            'pairwise': {'launched_a': 'similar', 'launched_b': 'similar', 'rejected_a': pairwise, 'rejected_b': pairwise},
            'top_issues': [], 'looks_easy_to_make': False, 'carries_collection': True,
            'foil_and_blind_lines_legible': True, 'printability_note': ''}
    base.update(extra)
    return base


def record(p):
    return {'payload': p, 'model': 'test-model', 'cost_usd': 0.0}


def test_stricter_juror_stands_and_raw_scores_are_recorded_before_caps():
    j1 = payload(9.0); j2 = payload(9.0)
    j2['dimensions']['typography']['score'] = 7.0
    out = jury.combine(record(j1), record(j2))
    assert out['raw']['scores']['J1']['typography'] == 9.0 and out['raw']['scores']['J2']['typography'] == 7.0
    assert out['capped']['typography'] == 7.0
    assert out['caps_applied'] == [] and out['verdict']['passed'] is True
    assert out['raw']['means'] == {'J1': 9.0, 'J2': 8.8}


def test_not_clearly_beating_both_rejected_anchors_caps_beauty_and_distinctiveness_at_six():
    out = jury.combine(record(payload(9.0)), record(payload(9.0, pairwise='similar')))
    assert out['raw']['scores']['J2']['beauty'] == 9.0            # raw stays
    assert out['capped']['beauty'] == 6.0 and out['capped']['distinctiveness'] == 6.0
    assert out['verdict']['passed'] is False and any('rejected anchors' in c for c in out['caps_applied'])


def test_easy_to_make_caps_and_collection_penalty_subtracts_one():
    j1 = payload(9.0, looks_easy_to_make=True)
    out = jury.combine(record(j1), record(payload(9.0)))
    assert out['capped']['beauty'] == 6.0 and any('easy to make' in c for c in out['caps_applied'])
    j1 = payload(9.0, carries_collection=False)
    out = jury.combine(record(j1), record(payload(9.0)))
    assert out['capped']['distinctiveness'] == 8.0 and out['capped']['beauty'] == 9.0
    assert any('D-D8-13' in c for c in out['caps_applied'])


def test_near_copy_and_banned_motif_are_hard_failures_from_either_juror():
    out = jury.combine(record(payload(9.0, near_copy_of='Some Brand')), record(payload(9.0)))
    assert out['verdict']['passed'] is False and any('near-copy of Some Brand' in h for h in out['verdict']['hard_failures'])
    out = jury.combine(record(payload(9.0)), record(payload(9.0, banned_motif_seen='rose petals as the hero')))
    assert any('banned motif' in h for h in out['verdict']['hard_failures'])


def test_idea_mismatch_is_an_issue_not_a_failure():
    out = jury.combine(record(payload(9.0, idea_matches_direction=False, idea_read='a floral')), record(payload(9.0)))
    assert out['verdict']['passed'] is True
    assert any('reads the idea as' in i for i in out['verdict']['issues'])


def test_incomplete_juror_leaves_the_verdict_pending():
    out = jury.combine({'payload': None}, record(payload(9.0)))
    assert out['verdict']['review_status'] == 'review_pending' and out['capped'] is None


def test_median_record_is_an_actual_record():
    rs = [record(payload(6.0)), record(payload(9.0)), record(payload(8.0))]
    chosen = jury._median_record(rs)
    assert chosen is rs[2]
    assert jury._median_record([{'payload': None}, record(payload(7.0))]) is not None


def test_raw_pass_rule_matches_the_owner_thresholds():
    assert jury.raw_passes({k: 8.0 for k in DIMENSIONS})
    low = {k: 8.0 for k in DIMENSIONS}; low['beauty'] = 6.9
    assert not jury.raw_passes(low)


def test_anchor_blocks_carry_one_cache_breakpoint_on_the_last_rejected_anchor(tmp_path):
    paths = []
    for i in range(4):
        p = tmp_path / f'{i}.png'; Image.new('RGB', (1600, 1000), (i * 40, 0, 0)).save(p); paths.append(p)
    blocks, rec = jury.anchor_blocks(paths[:2], paths[2:])
    images = [b for b in blocks if b['type'] == 'image']
    assert len(images) == 4 and [b.get('cache_control') for b in images] == [None, None, None, {'type': 'ephemeral'}]
    assert len(rec['launched']) == 2 and len(rec['rejected']) == 2 and rec['edge_px'] == 768
    with pytest.raises(ValueError):
        jury.anchor_blocks(paths[:1], paths[2:])


def test_resized_png_bounds_the_edge_and_the_shelf_width(tmp_path):
    p = tmp_path / 'lid.png'; Image.new('RGB', (1536, 970), 'white').save(p)
    data, size = jury.resized_png(p, long_edge=768); assert size == [768, 485]
    data, size = jury.resized_png(p, width=330); assert size[0] == 330
    data, size = jury.resized_png(p, width=4000); assert size == [1536, 970]


def test_verdict_schema_is_strict_and_juror_specific():
    for juror in ('J1', 'J2'):
        s = jury.verdict_schema(juror)
        assert s['additionalProperties'] is False and set(s['required']) == set(s['properties'])
        item = s['properties']['dimensions']['items']
        assert item['properties']['dimension']['enum'] == list(DIMENSIONS) and item['additionalProperties'] is False
        assert {'vs_launched_a', 'vs_launched_b', 'vs_rejected_a', 'vs_rejected_b'} <= set(s['properties'])


def test_the_array_answer_is_normalised_to_one_row_per_dimension_and_one_pairwise_object():
    rows = [{'dimension': k, 'score': 8, 'observation': 'o', 'location': 'l', 'repair': 'r'} for k in DIMENSIONS]
    rows.append({'dimension': 'beauty', 'score': 1, 'observation': 'dup', 'location': 'l', 'repair': 'r'})
    answer = {'dimensions': rows, 'vs_launched_a': 'similar', 'vs_launched_b': 'worse', 'vs_rejected_a': 'clearly_better',
              'vs_rejected_b': 'clearly_better', 'top_issues': [{'observation': str(i), 'location': 'l', 'repair': 'r'} for i in range(7)]}
    out = jury._normalise(answer)
    assert set(out['dimensions']) == set(DIMENSIONS) and out['dimensions']['beauty']['score'] == 8     # the first stands
    assert out['pairwise'] == {'launched_a': 'similar', 'launched_b': 'worse', 'rejected_a': 'clearly_better',
                               'rejected_b': 'clearly_better'}
    assert len(out['top_issues']) == 5
    missing = jury._normalise({'dimensions': rows[:9]})
    assert len(missing['dimensions']) == 9
    from apps.pipeline.services.concept_quality import evaluate
    assert evaluate({'dimensions': missing['dimensions'], 'hard_failures': []})['review_status'] == 'review_pending'
    assert 'looks_easy_to_make' in jury.verdict_schema('J1')['properties'] and 'looks_easy_to_make' not in jury.verdict_schema('J2')['properties']
    assert 'foil_and_blind_lines_legible' in jury.verdict_schema('J2')['properties']
    json.dumps(jury.verdict_schema('J1')); json.dumps(jury.RANK_SCHEMA); json.dumps(jury.IDEA_SCHEMA)


def test_both_jurors_share_one_cached_prefix_and_the_rubric_is_product_neutral():
    """The rubric is the whole system prompt (no juror role in it), so J1, J2, the sketch ranking and the idea check read one
    cache entry; the role comes after the anchors; the rubric never assumes the candidate is a palette lid."""
    assert jury._system('v1') == jury._system('v1') and len(jury._system('v1')) == 1
    text = jury._system('v1')[0]['text']
    assert 'YOUR ROLE' not in text and jury.ROLE_J1 not in text and jury.ROLE_J2 not in text
    assert 'closed lid of an eyeshadow palette' not in text and 'stated with each candidate' in text
    assert jury._role('J1')['text'].endswith(jury.ROLE_J1) and jury._role('J2')['text'].endswith(jury.ROLE_J2)
    assert 'eyeshadow palette, 190 × 120 mm' in jury.LID_WHAT


def test_no_array_length_keywords_reach_the_api():
    for schema in (jury.verdict_schema('J1'), jury.verdict_schema('J2'), jury.RANK_SCHEMA, jury.IDEA_SCHEMA):
        blob = json.dumps(schema)
        assert 'maxItems' not in blob and 'minItems' not in blob and 'minimum' not in blob and 'maximum' not in blob


def test_cost_counts_cache_reads_at_the_read_price(settings):
    settings.CLAUDE_PRICES = dict(settings.CLAUDE_PRICES, **{'claude-opus-5-5': (0.004, 0.020)})
    usage = {'input_tokens': 1000, 'output_tokens': 1000, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 10000}
    cost = jury.cost_usd('claude-opus-5-5', usage)
    assert abs(cost - (0.004 + 0.020 + 10 * 0.0002)) < 1e-6
    assert jury.cost_usd('claude-opus-5-5', {}) is None


def test_rubric_names_the_banned_motifs_the_scale_and_the_gate():
    for version in ('v1', 'v2'):
        text = jury.RUBRICS[version]
        assert 'THE GATE' in text and 'Pentawards' in text and 'NEAR-COPY' in text
        for motif in ('rose flowers', 'lips and cherries', 'botanical line-art wallpaper', 'twelve-rosette'):
            assert motif in text
    assert jury.RUBRIC_V2.startswith(jury.RUBRIC_V1)


def test_calibration_reads_raw_scores_before_the_caps():
    def v(score, pairwise='clearly_better'):
        return jury.combine(record(payload(score, pairwise=pairwise)), record(payload(score, pairwise=pairwise)))
    results = [{'label': 'D1', 'kind': 'negative', 'verdict': v(6.0)},
               {'label': 'D2', 'kind': 'negative', 'verdict': v(5.0)},
               {'label': 'D3', 'kind': 'negative', 'verdict': v(4.0)},
               {'label': 'X', 'kind': 'negative', 'verdict': v(9.0, pairwise='similar')},     # capped, but raw passes
               {'label': 'P1', 'kind': 'positive', 'verdict': v(9.0)},
               {'label': 'P2', 'kind': 'positive', 'verdict': v(7.0)},
               {'label': 'D1', 'kind': 'negative', 'run': 2, 'verdict': v(6.8)}]
    s = jury.calibration_summary(results, repeat_label='D1')
    assert s['negatives']['raw_passes'] == ['X'] and s['negatives']['all_fail_on_raw'] is False
    x = next(r for r in s['rows'] if r['label'] == 'X')
    assert x['raw_passes'] is True and x['capped_passes'] is False             # raw and capped side by side
    assert s['positives']['share_passing'] == 0.5 and s['positives']['meets_75_percent'] is False
    assert s['order']['owner_order_held'] is True and s['order']['spread'] == 2.0
    assert s['repeatability']['movement'] == 0.8 and s['repeatability']['finalists_scored_three_times'] is True


def test_the_sketch_ranking_sets_each_measured_check_under_its_sketch(tmp_path, monkeypatch):
    """Day 8 §5 Stage 1: J1 ranks the six beside the anchors with the checks that apply to a sketch — the copy OCR
    found is measured by code and set under each picture; the record keeps them."""
    sketches = []
    for i in range(2):
        path = tmp_path / f's{i}.png'
        Image.new('RGB', (300, 190), (40 * i, 20, 60)).save(path)
        sketches.append(path)
    sent = {}

    class Response:
        stop_reason = 'end_turn'
        content = [type('B', (), {'type': 'text', 'text': json.dumps(
            {'ranking': [{'sketch': 1, 'rank': 1, 'score': 7.5, 'why': 'w', 'banned_motif_seen': '', 'copy_present': True,
                          'ai_artefacts': ''}], 'best_two': [1, 2, 2], 'note': ''})})()]

        def model_dump(self, mode='json'):
            return {'usage': {'input_tokens': 10, 'output_tokens': 10}}

    def fake_paid(invoke, **kwargs):
        sent.update(kwargs)
        return Response()

    monkeypatch.setattr(jury, 'paid_operation', fake_paid)
    monkeypatch.setattr(jury, '_client', lambda: type('C', (), {'messages': type('M', (), {'create': None})()})())
    rec = jury.rank_sketches(sketches, anchors=([], {}), facts='facts', spec='spec', direction_idea='idea',
                             operation='day8/sketches/rank-T', destination=tmp_path / 'rank.json', model='test-model',
                             checks=['OCR found 10 of 10.', 'OCR found 4 of 10; missing: 27, g'])
    texts = [b['text'] for b in sent['messages'][0]['content'] if b.get('type') == 'text']
    assert 'Measured by code on sketch 1: OCR found 10 of 10.' in texts
    assert 'Measured by code on sketch 2: OCR found 4 of 10; missing: 27, g' in texts
    assert texts.index('Sketch 2:') < texts.index('Measured by code on sketch 2: OCR found 4 of 10; missing: 27, g')
    assert rec['checks'][1].startswith('OCR found 4') and rec['payload']['best_two'] == [1, 2]


# --- the gate review of Day 8 (jury.py: cost_usd, judge and calibration_summary): a missing count, an unknown cost
# or an unscored item never stands in for a measured value or a passed check ---------------------------------------

def test_a_usage_without_both_token_counts_has_no_cost(settings):
    """A usage missing input_tokens or output_tokens was priced as if the count were 0, an understated cost on the
    record; both counts are required now (None without either). Only the two cache counters are optional: the
    provider's usage types them Optional, and null there is a call that read or wrote no cache."""
    settings.CLAUDE_PRICES = dict(settings.CLAUDE_PRICES, **{'claude-opus-5-5': (0.004, 0.020)})
    full = {'input_tokens': 1000, 'output_tokens': 1000, 'cache_creation_input_tokens': None, 'cache_read_input_tokens': None}
    assert abs(jury.cost_usd('claude-opus-5-5', full) - (0.004 + 0.020)) < 1e-6
    for counter in ('input_tokens', 'output_tokens'):
        assert jury.cost_usd('claude-opus-5-5', {k: v for k, v in full.items() if k != counter}) is None
        assert jury.cost_usd('claude-opus-5-5', dict(full, **{counter: None})) is None
        assert jury.cost_usd('claude-opus-5-5', dict(full, **{counter: True})) is None


def test_the_verdicts_cost_is_unknown_when_any_jurors_cost_is_unknown(tmp_path):
    """The verdict's cost is the sum of its calls only when every call's cost is known; one unknown makes it None (null
    in verdict.json), never $0 for that call. The jurors' records are read back (``ask`` never pays twice), so no
    provider is called."""
    candidate = tmp_path / 'lid.png'
    Image.new('RGB', (40, 25), 'white').save(candidate)
    for folder, costs in (('known', (0.1, 0.12)), ('unknown', (None, 0.12))):
        (tmp_path / folder).mkdir()
        for juror, cost in zip(('J1', 'J2'), costs):
            (tmp_path / folder / f'{juror}.json').write_text(json.dumps(dict(record(payload(9.0)), cost_usd=cost)))
    out = jury.judge(candidate, anchors=([], {}), facts='f', operation_prefix='t', destination_dir=tmp_path / 'known')
    assert out['cost_usd'] == 0.22 and out['verdict']['passed'] is True
    out = jury.judge(candidate, anchors=([], {}), facts='f', operation_prefix='t', destination_dir=tmp_path / 'unknown')
    assert out['cost_usd'] is None and out['verdict']['passed'] is True
    assert json.loads((tmp_path / 'unknown' / 'verdict.json').read_text())['cost_usd'] is None


def test_calibration_never_counts_an_unscored_item_or_an_unknown_cost():
    """A review that never came back (raw_passes None) is pending, named under its kind, and is neither a failing
    negative nor a failing positive: all_fail_on_raw holds only when every negative was scored and failed; the
    positives' share, the 75 % check and calibrated_on_the_positive_side wait for every positive; the calibration's
    cost is None when any verdict's cost is unknown."""
    def v(score, cost=0.1):
        return dict(jury.combine(record(payload(score)), record(payload(score))), cost_usd=cost)
    unscored = dict(jury.combine({'payload': None}, record(payload(9.0))), cost_usd=0.1)
    results = [{'label': 'D1', 'kind': 'negative', 'verdict': v(5.0)},
               {'label': 'D2', 'kind': 'negative', 'verdict': unscored},
               {'label': 'P1', 'kind': 'positive', 'verdict': v(9.0)},
               {'label': 'P2', 'kind': 'positive', 'verdict': unscored}]
    s = jury.calibration_summary(results)
    assert s['negatives']['raw_passes'] == [] and s['negatives']['all_fail_on_raw'] is False     # D2 was never scored
    assert s['negatives']['pending'] == ['D2']
    assert s['positives']['raw_passes'] == ['P1'] and s['positives']['pending'] == ['P2']
    assert s['positives']['share_passing'] is None and s['positives']['meets_75_percent'] is None
    assert s['positives']['calibrated_on_the_positive_side'] is False
    assert s['cost_usd'] == 0.4
    results[1]['verdict'], results[3]['verdict'] = v(6.0), v(8.5)       # every item scored: the measured values stand
    s = jury.calibration_summary(results)
    assert s['negatives']['pending'] == [] and s['negatives']['all_fail_on_raw'] is True
    assert s['positives']['pending'] == [] and s['positives']['share_passing'] == 1.0
    assert s['positives']['meets_75_percent'] is True and s['positives']['calibrated_on_the_positive_side'] is True
    results[0]['verdict'] = v(5.0, cost=None)
    assert jury.calibration_summary(results)['cost_usd'] is None          # one unknown call, never counted as $0


# --- Day 8 residual: the repeatability block — an unscored repeat run is pending, one scored run measures nothing ---

CALIBRATION = Path(__file__).resolve().parents[4] / 'docs' / 'audit' / 'day-8' / 'jury' / 'calibration'


def scored(mean):
    """A verdict both jurors scored, every dimension at ``mean``: its raw stricter mean is ``mean``."""
    return jury.combine(record(payload(mean)), record(payload(mean)))


def unscored():
    """A verdict whose J1 review never came back: pending, no raw stricter mean."""
    return jury.combine({'payload': None}, record(payload(9.0)))


def d1_runs(*verdicts):
    """The calibration's own shape: D1's first run beside D2 and D3, then D1's repeats as runs 2, 3, …"""
    runs = [{'label': 'D1', 'kind': 'negative', 'run': i + 1, 'verdict': v} for i, v in enumerate(verdicts)]
    return runs[:1] + [{'label': 'D2', 'kind': 'negative', 'verdict': scored(5.0)},
                       {'label': 'D3', 'kind': 'negative', 'verdict': scored(4.0)}] + runs[1:]


def test_a_single_scored_run_leaves_the_repeatability_unmeasured():
    """v2's shape: D1 scored once and never repeated. One scored run measures no movement, so whether the finalists
    are scored three times is unmeasured (None), never False ('stable, score finalists once')."""
    rep = jury.calibration_summary(d1_runs(scored(6.0)), repeat_label='D1')['repeatability']
    assert rep['movement'] is None
    assert rep['finalists_scored_three_times'] is None
    assert rep['raw_stricter_means'] == [6.0] and rep['pending'] == []


def test_an_unscored_repeat_run_is_named_pending_never_dropped_unseen():
    """D1 run 2's review never came back: it is named (by run) under pending, never silently dropped, and one scored
    run leaves the decision unmeasured."""
    rep = jury.calibration_summary(d1_runs(scored(6.0), unscored()), repeat_label='D1')['repeatability']
    assert rep['movement'] is None and rep['finalists_scored_three_times'] is None
    assert rep['raw_stricter_means'] == [6.0] and rep['pending'] == [2]


def test_a_small_movement_waits_for_a_pending_run_and_a_large_one_stands():
    """Two scored runs measure a movement over those runs. With a run pending, a movement of 0.5 or less is not yet
    'stable' (the pending run could still move it past 0.5): None. A movement over 0.5 is True whatever is pending
    (more runs only widen the spread)."""
    rep = jury.calibration_summary(d1_runs(scored(6.0), scored(6.2), unscored()), repeat_label='D1')['repeatability']
    assert rep['movement'] == 0.2 and rep['finalists_scored_three_times'] is None
    assert rep['raw_stricter_means'] == [6.0, 6.2] and rep['pending'] == [3]
    rep = jury.calibration_summary(d1_runs(scored(6.0), unscored(), scored(6.8)), repeat_label='D1')['repeatability']
    assert rep['movement'] == 0.8 and rep['finalists_scored_three_times'] is True
    assert rep['raw_stricter_means'] == [6.0, 6.8] and rep['pending'] == [2]


def test_every_run_scored_decides_as_before():
    """The normal path is unchanged (this test passes before and after the fix): every run scored, a movement over 0.5
    is True, and 0.5 or less (the threshold itself included) is False."""
    for means, movement, three_times in (((6.0, 6.1, 6.1), 0.1, False), ((6.0, 6.5), 0.5, False),
                                         ((6.0, 6.8, 6.2), 0.8, True)):
        rep = jury.calibration_summary(d1_runs(*(scored(m) for m in means)), repeat_label='D1')['repeatability']
        assert rep['movement'] == movement and rep['finalists_scored_three_times'] is three_times
        assert rep['raw_stricter_means'] == list(means)


def test_the_repeatability_block_keeps_every_key_and_adds_pending():
    rep = jury.calibration_summary(d1_runs(scored(6.0), scored(6.8)), repeat_label='D1')['repeatability']
    assert set(rep) == {'label', 'raw_stricter_means', 'movement', 'finalists_scored_three_times', 'pending'}
    assert rep['label'] == 'D1' and rep['pending'] == []


def test_no_repeat_label_measures_nothing():
    """Without a repeat label nothing was repeated: unmeasured (None), never False."""
    rep = jury.calibration_summary(d1_runs(scored(6.0), scored(6.8)))['repeatability']
    assert rep['label'] is None and rep['movement'] is None
    assert rep['finalists_scored_three_times'] is None
    assert rep['raw_stricter_means'] == [] and rep['pending'] == []


def replay(version):
    """A recorded calibration's results rebuilt from its own rows and verdict files (run 1 in <label>/, run N in
    <label>-runN/), read only, and summarised again."""
    folder = CALIBRATION / version
    recorded = json.loads((folder / 'summary.json').read_text())
    results = [{'label': r['label'], 'kind': r['kind'], 'run': r['run'],
                'verdict': json.loads((folder / (r['label'] if r['run'] == 1 else f"{r['label']}-run{r['run']}")
                                       / 'verdict.json').read_text())}
               for r in recorded['rows']]
    return recorded, jury.calibration_summary(results, repeat_label=recorded['repeatability']['label'])


def test_the_recorded_calibrations_replay_v1_unchanged_and_v2_unmeasured():
    """v1 scored D1 three times (4.1, 4.2, 4.2): its movement 0.1 and False stand, nothing pending. v2 never repeated
    D1 (one scored run): it now reads movement None and finalists_scored_three_times None (unmeasured). The decision
    to score finalists once rests on v1."""
    recorded, out = replay('v1')
    assert out['rows'] == recorded['rows']                                  # the verdict files reproduce the record
    assert out['repeatability'] == dict(recorded['repeatability'], pending=[])
    assert out['repeatability']['movement'] == 0.1 and out['repeatability']['finalists_scored_three_times'] is False
    recorded, out = replay('v2')
    assert out['rows'] == recorded['rows']
    assert out['repeatability'] == {'label': 'D1', 'raw_stricter_means': [4.1], 'pending': [], 'movement': None,
                                    'finalists_scored_three_times': None}
