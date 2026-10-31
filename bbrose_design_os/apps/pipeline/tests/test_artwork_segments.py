"""Motif segmentation into separate elements (2026-07-07)."""
from __future__ import annotations

import pytest
from django.test import SimpleTestCase

from apps.pipeline.services.artwork_segments import segment_artwork

_BG = "#EFE9E4"


def _image_with_discs(tmp_path, n, size=400, disc_r=36):
    """n dark discs in a grid on the flat background color."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (size, size), (0xEF, 0xE9, 0xE4))
    d = ImageDraw.Draw(im)
    cols = int(n ** 0.5) or 1
    step = size // (cols + 1)
    drawn = 0
    for i in range(cols + 1):
        for j in range(cols + 1):
            if drawn >= n:
                break
            cx, cy = step * (i + 1) - step // 2, step * (j + 1) - step // 2
            # distinct color per disc so reportlab can't dedupe the crops
            d.ellipse([cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
                      fill=(120, 40 + drawn * 13, 60 + drawn * 7))
            drawn += 1
    p = tmp_path / f"discs_{n}.png"
    im.save(p)
    return str(p)


class SegmentArtworkTests(SimpleTestCase):
    @pytest.fixture(autouse=True)
    def _tmp(self, tmp_path):
        self.tmp_path = tmp_path

    def test_discs_become_separate_segments(self):
        path = _image_with_discs(self.tmp_path, 4)
        segs = segment_artwork(path, _BG)
        assert len(segs) == 4
        for s in segs:
            assert s.image.mode == "RGBA"
            # corners of the bbox are background → transparent
            assert s.image.getpixel((0, 0))[3] == 0
            # center of the disc is opaque
            cx, cy = s.w // 2, s.h // 2
            assert s.image.getpixel((cx, cy))[3] == 255
            assert 0 <= s.x and 0 <= s.y

    def test_uniform_image_returns_empty(self):
        from PIL import Image
        p = self.tmp_path / "flat.png"
        Image.new("RGB", (200, 200), (0xEF, 0xE9, 0xE4)).save(p)
        assert segment_artwork(str(p), _BG) == []

    def test_full_bleed_gradient_returns_empty(self):
        from PIL import Image
        im = Image.new("RGB", (200, 200))
        im.putdata([(x % 256, (x // 200) % 256, 90)
                    for x in range(200 * 200)])
        p = self.tmp_path / "grad.png"
        im.save(p)
        assert segment_artwork(str(p), _BG) == []

    def test_element_cap_respected(self):
        path = _image_with_discs(self.tmp_path, 9, size=600, disc_r=28)
        segs = segment_artwork(path, _BG, max_elements=5)
        assert len(segs) == 5

    def test_single_element_keeps_single_raster(self):
        path = _image_with_discs(self.tmp_path, 1)
        assert segment_artwork(path, _BG) == []


