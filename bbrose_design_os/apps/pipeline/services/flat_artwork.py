"""The border colour of an image, sampled for the container's body (P4 v2, 2026-07-04).

``dominant_color_hex`` reads an image's border colour; the product container paints its body with it, sampled from
the approved concept (``apps/pipeline/targets/container/__init__.py``, ``_composer_inputs``).

[The clean-up of 2026-10-04 (E1, on the owner's approval of the final clean-up list, transcribed at b5892f9): the
carton's raster image edit — ``make_flat_artwork`` with its "full" and "background pattern" prompts — and
``match_background_tone`` are removed. Nothing had called them since cd52e1f, the owner's finding on design 119: "KILL
THE RASTER PATH". Git history keeps them.]
"""
from __future__ import annotations


def _border_rgb(im) -> tuple[int, int, int]:
    im = im.convert("RGB")
    im.thumbnail((64, 64))
    w, h = im.size
    px = im.load()
    border = (
        [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
        + [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    )
    n = len(border)
    return (sum(p[0] for p in border) // n,
            sum(p[1] for p in border) // n,
            sum(p[2] for p in border) // n)


def dominant_color_hex(image_path: str, default: str = "#EFE9E4") -> str:
    """Artwork border color — fills the panels/flaps around the contained
    artwork so the flat reads as one seamless carton."""
    try:
        from PIL import Image

        with Image.open(image_path) as im:
            r, g, b = _border_rgb(im)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:  # noqa: BLE001
        return default
