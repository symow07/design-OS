"""Independent invariants of the selected HAYAT pixels and cap-only trace."""
import hashlib
import json
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image
import pytest
from scipy.ndimage import distance_transform_edt

from apps.pipeline.services import round_balm_preservation as preservation

ROOT = preservation.OUT


def rgb(path):
    return np.array(Image.open(path).convert('RGB'))


@pytest.mark.parametrize('panel', preservation.PANELS)
def test_pinned_plate_is_exact_two_times_lanczos_without_retouched_pixels(panel):
    original = rgb(preservation.SOURCE / f'{panel}.png')
    actual = rgb(ROOT / 'plates' / f'{panel}.png')
    expected = cv2.resize(original, (original.shape[1] * 2, original.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4)
    assert np.array_equal(actual, expected)
    report = json.loads((ROOT / 'fidelity.json').read_text())['panels'][panel]
    crop = json.loads((preservation.SOURCE / 'crop.json').read_text())['panels'][panel]
    ppi = min(original.shape[1] / crop['mm'][0], original.shape[0] / crop['mm'][1]) * 25.4
    assert report['effective_ppi_at_trim'] == pytest.approx(ppi)
    assert report['nominal_ppi_at_trim'] == pytest.approx(ppi * 2)
    assert report['ppi_300_met'] is (ppi >= 300)
    assert report['source_sha256'] == hashlib.sha256((preservation.SOURCE / f'{panel}.png').read_bytes()).hexdigest()


def test_modified_pinned_input_is_refused_before_build(tmp_path, monkeypatch):
    first = next(iter(preservation.SOURCE_PINS))
    (tmp_path / first).write_bytes(b'not the selected design')
    monkeypatch.setattr(preservation, 'SOURCE', tmp_path)
    with pytest.raises(ValueError, match='pinned D1/A source mismatch'):
        preservation.build_plates(tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def independently_sample_original_cap():
    original = rgb(preservation.SOURCE / 'cap.png').astype(float)
    alpha = np.maximum(0, np.minimum(1, (original[..., 0] - 95) / 80))
    alpha[original[..., 0] - original[..., 1] <= 35] = 0
    region = np.zeros(alpha.shape, dtype=bool)
    region[20:101, 53:240] = True
    _, components, stats, _ = cv2.connectedComponentsWithStats(((alpha >= .5) & region).astype('uint8'), 8)
    # Four independently observed letter-component bounding boxes in the sketch.
    wanted_boxes = {(61, 26, 23, 15), (62, 46, 20, 29), (105, 26, 124, 53), (151, 83, 22, 14)}
    wanted = [i for i, row in enumerate(stats) if tuple(row[:4]) in wanted_boxes]
    assert len(wanted) == 4
    selected = cv2.dilate(np.isin(components, wanted).astype('uint8'), np.ones((3, 3), 'uint8')) > 0
    # The separate spurious 1 (122,33,24,29) is not a selected component.
    assert not any(tuple(stats[i][:4]) == (122, 33, 24, 29) for i in wanted)
    alpha *= selected & region
    h, w = alpha.shape
    return cv2.resize(alpha.astype('float32'), (w * 16, h * 16), interpolation=cv2.INTER_CUBIC) >= .5


def test_saved_svg_reads_back_with_iou_against_original_sketch_not_itself():
    ref = independently_sample_original_cap()
    saved_reference = np.array(Image.open(ROOT / 'logotype/sketch-silhouette.png')) > 127
    assert np.array_equal(ref, saved_reference)
    svg = (ROOT / 'logotype/hayat.svg').read_bytes()
    assert b'<text' not in svg
    with fitz.open(stream=svg, filetype='svg') as doc:
        page = doc[0]
        h, w = ref.shape
        pix = page.get_pixmap(matrix=fitz.Matrix(w / page.rect.width, h / page.rect.height), alpha=True)
        actual = np.frombuffer(pix.samples, 'uint8').reshape(h, w, pix.n)[..., -1] >= 128
    iou = (actual & ref).sum() / (actual | ref).sum()
    report = json.loads((ROOT / 'trace.json').read_text())
    assert iou >= .95
    assert report['actual_svg_iou'] == pytest.approx(iou, abs=1e-12)
    assert report['all_other_fragments_raster'] is True
    assert report['no_font_substitution'] is True
    assert report['vector_sha256'] == hashlib.sha256(svg).hexdigest()


def test_emboss_proposal_clearance_is_measured_and_never_leaks_into_master():
    report = json.loads((ROOT / 'proposals/cap-emboss-proof.json').read_text())
    reference = np.array(Image.open(ROOT / 'logotype/actual-svg-silhouette.png')) > 127
    h, w = reference.shape
    mm_x, mm_y = 58.5 / w, 32 / h
    rx, ry = int(np.ceil(.15 / mm_x)), int(np.ceil(.15 / mm_y))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rx * 2 + 1, ry * 2 + 1))
    centers = cv2.erode(reference.astype('uint8'), kernel) > 0
    distances = distance_transform_edt(reference, sampling=(mm_y, mm_x))
    centers &= distances >= .15
    retained = (cv2.dilate(centers.astype('uint8'), kernel) > 0) & reference
    actual = np.array(Image.open(ROOT / report['mask'])) > 127
    excluded = np.array(Image.open(ROOT / report['excluded_mask'])) > 127
    assert np.array_equal(actual, retained)
    assert np.array_equal(excluded, reference & ~retained)
    assert 2 * distances[centers].min() >= .3
    assert report['minimum_feature_mm'] == pytest.approx(min(2 * rx * mm_x, 2 * ry * mm_y))
    assert report['excluded_pixels'] == int(excluded.sum())
    assert report['applied_to_master'] is False
    assert 'NOT APPLIED' in report['status']
    for file in ('body-wrap.ai', 'cap-wrap.ai', 'label.ai', 'carton-artwork.ai'):
        path = ROOT / file
        if path.exists():
            with fitz.open(path) as doc:
                layer_names = [ocg['name'].lower() for ocg in doc.get_ocgs().values()]
                assert not any('emboss' in name or 'relief' in name for name in layer_names)
