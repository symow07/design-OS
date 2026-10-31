"""Shared font/fit helpers for palette review boards."""
from __future__ import annotations

from PIL import Image, ImageFont

_FONT = "/System/Library/Fonts/Helvetica.ttc"


def font(size):
    try:
        return ImageFont.truetype(_FONT, size)
    except OSError:                                    # pragma: no cover
        return ImageFont.load_default()


def fit(img, max_w, max_h):
    """Uniform scale only — aspect ratio is never distorted."""
    s = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * s)),
                       max(1, int(img.height * s))), Image.LANCZOS)
