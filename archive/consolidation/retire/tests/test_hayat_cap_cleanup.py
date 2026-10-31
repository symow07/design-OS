"""The owner-reported cap cleanup must not alter the traced word or pink art."""
import hashlib
import json

import numpy as np
from PIL import Image

from apps.pipeline.services import round_balm_preservation as preservation


def test_cap_cleanup_is_local_and_preserves_original_trace_and_paint():
    out = preservation.OUT
    report = json.loads((out / 'repair/cap-cleanup.json').read_text())
    trace = json.loads((out / 'trace.json').read_text())
    load = lambda path: np.array(Image.open(out / path))
    before, after = load(report['before']), load(report['after'])
    changed = np.any(before != after, axis=2)
    allowed = load(report['allowed_mask']) > 0
    protected = load(report['protected_pink_mask']) > 0
    assert np.array_equal(changed, load(report['mask']) > 0)
    assert changed.sum() == report['changed_pixels_2x']
    assert changed.mean() == report['changed_share']
    assert not np.any(changed & ~allowed)
    fringe = load(report['construction_fringe_mask']) > 0
    assert not np.any(changed & protected & ~fringe)
    assert np.array_equal(load(report['protected_pink_difference']) > 0, changed & protected)
    assert int((changed & protected).sum()) == report['protected_pink_changed_pixels'] == 93
    assert fringe.sum() == report['construction_fringe_pixels'] == 99
    # A separate strong-pink selection must also survive; it does not use the
    # service's saved protection mask or component/dilation decisions.
    rgb = before.astype(int)
    actual_pink = (rgb[..., 0] > 175) & (rgb[..., 0] - rgb[..., 1] > 60) & (rgb[..., 0] - rgb[..., 2] > 50)
    assert actual_pink.sum() > 10000
    assert not np.any(changed & actual_pink)
    for relative, expected in [(report['original_underlay'], trace['raster_underlay_sha256']),
                                (report['trace_vector'], trace['vector_sha256'])]:
        assert hashlib.sha256((out / relative).read_bytes()).hexdigest() == expected
    assert report['trace_sha256_after'] == trace['vector_sha256']
    assert hashlib.sha256((out / report['after']).read_bytes()).hexdigest() == report['after_sha256']
    preservation.verify_sources()


def test_owner_reported_ground_dots_are_removed_without_replacing_the_paint():
    out = preservation.OUT
    before = np.array(Image.open(out / 'repair/cap-before.png')).astype(int)
    after = np.array(Image.open(out / 'repair/cap-after.png')).astype(int)
    # Independent hand-inspected centres of three pale dots on the right guide.
    # Every centre was on the ground, separate from the traced silhouette.
    for y in (47, 83, 155):
        assert before[y, 384].mean() - after[y, 384].mean() > 25
    # The large lower fragment's straight clipped top is explicitly preserved.
    fragment = before[206:230, 172:311]
    strong_ink = (fragment[..., 0] > 150) & (fragment[..., 0] - fragment[..., 1] > 55)
    assert strong_ink.sum() > 1000
    fringe = np.array(Image.open(out / 'repair/cap-construction-fringe-mask.png'))[206:230, 172:311] > 0
    assert np.array_equal(after[206:230, 172:311][strong_ink & ~fringe], fragment[strong_ink & ~fringe])


def test_only_two_explicit_vector_command_ranges_change_and_iou_remains_honest():
    out = preservation.OUT
    patch = json.loads((out / 'repair/cap-vector-patch.json').read_text())
    before = (out / patch['before_vector']).read_text()
    after = (out / patch['after_vector']).read_text()
    expected = before
    assert len(patch['patches']) == 2
    for row in patch['patches']:
        assert expected.count(row['removed_commands']) == 1
        expected = expected.replace(row['removed_commands'], row['replacement_commands'])
    assert after == expected
    assert hashlib.sha256(before.encode()).hexdigest() == patch['before_sha256']
    assert hashlib.sha256(after.encode()).hexdigest() == patch['after_sha256']
    assert patch['actual_saved_svg_iou_against_independent_original_sketch'] >= .95
    assert patch['outside_authorized_notch_boxes_max_mm'] <= .3
    trace = json.loads((out / 'trace.json').read_text())
    # The old guide notches remain in the independent reference; never hide their
    # intentional contour deviation by claiming the old global distance passed.
    assert trace['sketch_to_trace_max_mm'] > .3
    assert trace['holds']['overlay_within_0_3_mm'] is False
