"""The border colour of an image (2026-07-07; rewritten in the clean-up of 2026-10-04).

The flat-artwork extraction this file first tested — the "background" motif prompt and the motif's tone matching —
was removed in the clean-up of 2026-10-04 (E1, approved by the owner); nothing had called it since cd52e1f, the
owner's finding on design 119. What stays is ``dominant_color_hex``: the product container's body is sampled from the
approved concept with it (``apps/pipeline/targets/container/__init__.py``, ``_composer_inputs``).
"""
from __future__ import annotations

from apps.pipeline.services.flat_artwork import dominant_color_hex


class TestDominantColorHex:
    def _png(self, tmp_path, name, rgb, middle=None):
        from PIL import Image
        im = Image.new("RGB", (40, 40), rgb)
        if middle is not None:
            im.paste(middle, (10, 10, 30, 30))          # the border left as it was
        p = tmp_path / name
        im.save(p)
        return str(p)

    def test_a_solid_image_gives_its_own_colour(self, tmp_path):
        assert dominant_color_hex(self._png(tmp_path, "solid.png", (0xEF, 0xE9, 0xE4))) == "#EFE9E4"

    def test_the_border_is_read_and_the_middle_is_not(self, tmp_path):
        framed = self._png(tmp_path, "framed.png", (250, 230, 235), middle=(20, 20, 20))
        assert dominant_color_hex(framed) == "#FAE6EB"

    def test_an_unreadable_image_gives_the_default(self, tmp_path):
        assert dominant_color_hex(str(tmp_path / "nope.png")) == "#EFE9E4"
        assert dominant_color_hex(str(tmp_path / "nope.png"), default="#123456") == "#123456"
