"""Owner-authorized two-patch repair recovers existing pixels, never redraws."""
import hashlib
import json

import cv2
import numpy as np
from PIL import Image
import pytest

from apps.pipeline.services import round_balm_repair as repair


@pytest.mark.parametrize('panel', ['side_left', 'side_right'])
def test_repaired_core_is_exact_existing_raw_and_unchanged_outside_disclosed_mask(panel):
    out = repair.p.OUT
    report = json.loads((out / 'repair/repair.json').read_text())
    row = report['panels'][panel]
    raw_path = repair.p.SOURCE / 'raw.png'
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == report['raw_sha256'] == repair.RAW_SHA256
    with Image.open(raw_path) as image:
        source = np.array(image.convert('RGB').crop(row['raw_sheet_crop_box_px']))
    raw2 = cv2.resize(source, (source.shape[1] * 2, source.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4)
    before = np.array(Image.open(out / row['before']).convert('RGB'))
    after = np.array(Image.open(out / row['after']).convert('RGB'))
    mask = np.array(Image.open(out / row['mask'])) > 0
    alpha = np.array(Image.open(out / row['blend_alpha'])) > 0
    x0, y0, x1, y1 = row['authorized_source_rectangle_px']
    assert np.array_equal(after[y0 * 2:y1 * 2, x0 * 2:x1 * 2], raw2[y0 * 2:y1 * 2, x0 * 2:x1 * 2])
    assert np.array_equal(after[~alpha], before[~alpha])
    assert np.array_equal(mask, np.any(before != after, axis=2))
    assert mask.sum() == row['changed_pixels_2x']
    assert mask.mean() == pytest.approx(row['changed_share_of_panel'])
    assert row['newly_drawn_or_generated_strokes'] == 0
    assert report['source_and_exact_upscale_plates_unchanged'] is True
    # The preserved baseline itself still equals the selected panel's exact2×.
    original = np.array(Image.open(repair.p.SOURCE / f'{panel}.png').convert('RGB'))
    baseline = np.array(Image.open(out / 'plates' / f'{panel}.png').convert('RGB'))
    assert np.array_equal(baseline, cv2.resize(original, (original.shape[1] * 2, original.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4))
