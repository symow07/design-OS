"""Day 9 §4–§8 — the builds: the shared build core (rich_concept), the recipes of the six chosen sketches (day9_recipes),
the foil trap, and the image-call log's audit. DB-free; $0 (every image-model and vision call is a fake)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from apps.pipeline.services import round_calls as ig

CHOSEN = ('A-2.3', 'A-2.2', 'B-1.3', 'B-2.2', 'C-2.2', 'C-1.1')


@pytest.fixture
def mark_on(settings):
    """The approved mark looked up on file (the suite turns the lookup off by default), or skip on another machine."""
    settings.BRAND_MARK_APPROVAL_LOOKUP = True
    from apps.ire import brand_mark
    if brand_mark.approved_master()['master'] is None:
        pytest.skip('the approved mark is not on this machine')
    return True


def _toy_ornament(*, x0, y0, x1, y1, pitch_mm, line_mm):
    marks, y = [], y0
    while y <= y1:
        marks.append({'points': [(x0, y), (x1, y)], 'closed': False, 'width': line_mm, 'ink': 'gold_foil', 'fill': None, 'finishes': ['foil']})
        y += pitch_mm
    block = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lid = [(0, 0), (190, 0), (190, 120), (0, 120)]
    return {'kind': 'toy', 'marks': marks, 'regions': {'paint': [lid], 'relief': [block], 'footprint': [block]}, 'params': {}, 'measures': {}}


DAY9_CALL_LOG = ig.REPO / 'docs' / 'audit' / 'day-9' / 'image-calls.jsonl'


def test_the_day9_image_call_log_audits_clean(monkeypatch):
    """§8: every Day 9 image call is gpt-image-2 through the guard, sent its inputs with their sha256, carried no rejected
    design and no web picture (the approved logo exempt only as itself), and named no competitor. [Day 10] the guard now
    roots Day 10 (Day 9's pictures rejected, the pick apart): Day 9's closed log is audited under Day 9's own roots."""
    monkeypatch.setattr(ig, 'REJECTED_ROOTS', tuple(r for r in ig.REJECTED_ROOTS if r != ig.REPO / 'docs' / 'audit' / 'day-9'))
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day9/')
    a = ig.audit(DAY9_CALL_LOG)
    assert a['log_present'] and not a['log_empty'] and a['holds'], a
    assert a['rejected_or_web_inputs'] == 0 and a['competitor_prompts'] == 0 and a['non_openai_or_named_tool'] == 0
    rows = [json.loads(l) for l in DAY9_CALL_LOG.read_text(encoding='utf-8').split('\n') if l.strip()]
    assert all(r['operation'].startswith('day9/') for r in rows)


def test_the_audit_exempts_the_approved_logo_by_path_and_sha_only(tmp_path, monkeypatch):
    """A copy of the logo's bytes anywhere else is still a rejected design to the audit; the approval's own raster is not."""
    logo_path, logo_sha = ig.APPROVED_LOGO
    copy = tmp_path / 'logo-copy.png'
    shutil.copyfile(logo_path, copy)
    monkeypatch.setattr(ig, 'denylist', lambda refresh=False: {'rejected': {logo_sha: 'a rejected copy'}, 'web': {}})

    def row(path):
        return {'operation': 'day9/sketches/x', 'provider': 'openai', 'model': 'gpt-image-2', 'outcome': 'made', 'prompt': 'a lid',
                'inputs': [{'role': 'logo', 'path': str(path), 'sha256': logo_sha}]}
    for path, holds in ((logo_path, True), (copy, False)):
        log = tmp_path / ('log-%s.jsonl' % holds)
        log.write_text(json.dumps(row(path)) + '\n', encoding='utf-8')
        assert ig.audit(log)['holds'] is holds


# --- the plate's seams and residue, as they print (Day 9's close: the second-agent verifier's findings) ----------------


def _picture(rows=320, cols=480, seed=7):
    """A textured picture: smoothed noise round mid-grey, fine detail everywhere (a ring always has energy)."""
    import cv2
    rng = np.random.default_rng(seed)
    base = rng.normal(128, 18, (rows, cols, 3)).astype(np.float32)
    return np.clip(cv2.GaussianBlur(base, (0, 0), 1.2), 0, 255).astype(np.uint8)


