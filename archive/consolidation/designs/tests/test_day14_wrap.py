"""Builder regression for D-D14-3. Structural checks only: the owner forbids renders."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import fitz
import pytest

from apps.pipeline.services import day14_wrap as wrap


@pytest.fixture(scope='module')
def built_wrap():
    wrap.OUT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='builder-test-', dir=wrap.OUT) as folder:
        with patch.object(fitz.Page, 'get_pixmap', side_effect=AssertionError('D-D14-9: no rendering')):
            record = wrap.build(Path(folder))
        yield record, Path(folder) / 'lid-and-sides.pdf'


def test_composer_preserves_live_words_and_embedded_faces(built_wrap):
    record, path = built_wrap
    readback = record['readback']
    assert readback['live_copy']['source_objects'] == readback['live_copy']['output_objects'] == 10
    assert readback['live_copy']['all_live_copy_preserved']
    assert readback['actual_text'] == ['باليت', 'العيون', 'Eyeshadow', 'Palette', '18',
                                       'shades', '27', 'g', '℮', '0.95', 'oz']
    with fitz.open(path) as doc:
        assert {r['font'] for r in doc[0].get_texttrace()} == {'Tajawal-Medium', 'TajawalPF-Regular'}
        assert min(r['size'] for r in doc[0].get_texttrace()) >= 5
        assert all(doc.extract_font(f[0])[3] for page in doc for f in page.get_fonts(full=True))


def test_composer_preserves_artwork_and_both_vector_finish_plates(built_wrap):
    record, path = built_wrap
    assert record['sources_unchanged']
    for source in record['sources']:
        assert wrap.sha(wrap.ROOT / source['path']) == source['sha256']
    pages = record['readback']['page_preservation']
    assert all(p['source_content_streams_preserved'] for p in pages)
    assert [(p['source_vector_paths'], p['output_vector_paths']) for p in pages[:3]] == [(4, 4), (2, 2), (1, 1)]
    assert all(r['translation_error_mm_max'] < .001 and r['style_equal']
               for p in pages for r in p['source_path_translation'])
    with fitz.open(path) as doc:
        assert len(doc) == 4
        assert [doc[n].get_label().split()[1:4] for n in (1, 2)] == [
            ['wrap', 'rose-gold', 'foil'], ['wrap', 'relief', 'plate']]
        # Existing finish shapes stay black vectors; no raster finish rendering.
        assert all(not doc[n].get_images() for n in (1, 2))
        assert all(d['fill'] == (0., 0., 0.) for n in (1, 2) for d in doc[n].get_drawings())


def test_wrap_has_three_mm_bleed_and_only_the_four_original_side_crops(built_wrap):
    record, path = built_wrap
    assert set(record['bands']) == {'top', 'bottom', 'left', 'right'}
    assert all(b['crop_and_reflected_bleed_preserved'] for b in record['readback']['band_pixels'])
    central_crop = (142, 142, 2387, 1560)
    for band in record['bands'].values():
        x0, y0, x1, y1 = band['source_crop_px']
        cx0, cy0, cx1, cy1 = central_crop
        assert x1 <= cx0 or x0 >= cx1 or y1 <= cy0 or y0 >= cy1
        assert min(band['extension_mm_xy']) >= 3
        assert band['source_crop_unchanged']
    with fitz.open(path) as doc:
        assert len(doc[0].get_images()) == 5  # original live-master picture plus four cropped bands
        for page in doc:
            assert page.rect.width * wrap.MM == pytest.approx(220, abs=.001)
            assert page.rect.height * wrap.MM == pytest.approx(150, abs=.001)
            assert wrap.box_mm(page.trimbox) == pytest.approx([3, 3, 217, 147], abs=.001)
        assert set(record['readback']['pdf_info']['layers']) == {
            'picture', 'type', 'logo', 'foil', 'relief', 'guides',
            'adopted mirror sides and edge-extension bleed'}


def test_composer_uses_original_part_b_reader_without_rendering_or_mutating_it(built_wrap):
    record, _ = built_wrap
    assert not record['rendered'] and record['spend_usd'] == 0
    assert record['readback']['part_b_script']['sha256'] == wrap.sha(wrap.PART_B)
    assert all(record['readback']['checks'].values())
    assert 'not asserted to be vectors' in record['lettering']['limitation']
