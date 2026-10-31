"""Day 10 §9 — the master of the owner's pick (§1), the back sticker (§3), the open palette (§2), the box (§4), the pick
page (§6) and the image guard re-rooted for Day 10.

The measuring functions are tested on synthetic inputs, each with a control that must fail; the day's records are read
where they are on this machine (skipped where they are not), and the cheap proofs are re-run on the real pick."""
import json
import shutil

import numpy as np
import pytest


# --- colour and similarity -------------------------------------------------------------------------------------------


# --- §1: the upscale ---------------------------------------------------------------------------------------------------


# --- §1: placement, the trace, the logo, the masks ---------------------------------------------------------------------

def _unit(x0, y0, x1, y1):
    return {'box_mm': (x0, y0, x1, y1)}


# --- §3: the sticker -----------------------------------------------------------------------------------------------------


# --- §2 and §4: the tray and the box -------------------------------------------------------------------------------------


# --- the image guard and the call log ------------------------------------------------------------------------------------

def test_the_guard_allows_the_pick_only_as_itself(tmp_path, settings):
    from apps.pipeline.services import round_calls as ig
    settings.IMAGE_MODEL = 'gpt-image-2'
    path, sha = ig.APPROVED_PICK
    if not path.exists():
        pytest.skip('the owner\'s pick is not on this machine')
    deny = {'rejected': {sha: 'the pick under Day 9\'s rejected root'}, 'web': {}}
    checked = ig.check([{'role': 'the owner\'s pick', 'path': path}], 'the open tray', deny=deny)
    assert checked[0]['sha256'] == sha
    copy = tmp_path / 'lid.png'
    shutil.copyfile(path, copy)
    with pytest.raises(ig.ImageCallRefused):
        ig.check([{'role': 'the owner\'s pick', 'path': copy}], 'the open tray', deny=deny)
    assert ig._is_approved_logo({'path': str(path), 'sha256': sha})
    assert not ig._is_approved_logo({'path': str(copy), 'sha256': sha})


# --- §6: the pick page ---------------------------------------------------------------------------------------------------


