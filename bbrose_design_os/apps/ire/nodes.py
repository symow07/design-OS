"""Shared Design Graph node builders (Phase B, 2026-07-08).

Small, pure, transform-agnostic helpers (absolute mm coords) used by every
target composer so packaging and container don't reinvent rectangle clips,
optional images, or luminance-based ink. They build nodes in the ONE shared
Design Graph — no target-specific types.
"""
from __future__ import annotations

import os

from apps.ire.graph import ClosePath, Color, Image, LineTo, MoveTo, Segment, TextRun


def rect_clip(x: float, y: float, w: float, h: float) -> list[Segment]:
    """Closed rectangle as a clip/outline segment list (mm, y-down)."""
    return [MoveTo(x=x, y=y), LineTo(x=x + w, y=y),
            LineTo(x=x + w, y=y + h), LineTo(x=x, y=y + h), ClosePath()]


def image_node(name: str, src: str | None, x: float, y: float, w: float,
               h: float, clip: list[Segment] | None = None) -> Image | None:
    """An Image node, or None when the source file is absent (caller filters).
    Rasters are the flagged exception — callers group/label them explicitly."""
    if not (src and os.path.exists(src)):
        return None
    return Image(name=name, src=src, x=x, y=y, w=w, h=h, clip=clip)


def intrinsic_aspect(src: str | None) -> float | None:
    """``height/width`` of a raster asset as the FILE states it, or None when
    the file cannot be measured.

    A composer that picks a logo height picks a distortion: the artwork
    stretches to whatever the number says. The height is therefore read from
    the asset, never chosen. When it cannot be read there is no aspect and the
    caller places nothing — a guessed aspect is the exact defect this exists to
    prevent, and an absent logo reads at the visual-quality gate as UNMEASURED,
    which is blocking, rather than as artwork nobody stretched.

    Deliberately separate from ``container_logo_metrics``, which measures the
    placed result. One shared reader would make the distortion check compare a
    number against itself; kept apart, a bug on either side surfaces as a
    measured FAIL instead of a silent PASS.
    """
    if not (src and os.path.exists(src)):
        return None
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(src) as im:
            width, height = im.size
    except Exception:  # noqa: BLE001 — any decode failure is unmeasurable
        return None
    if not width or not height:
        return None
    return height / width


def ink_for(bg: Color) -> Color:
    """Readable ink for text over ``bg`` — warm white on dark, rose on light."""
    lum = 0.299 * bg.r + 0.587 * bg.g + 0.114 * bg.b
    return Color.from_hex("#F7F0E6") if lum < 0.5 else Color.from_hex("#59283A")


def centered_text(name: str, text: str, cx: float, y: float, size_pt: float,
                  color: Color, font: str = "regular",
                  print_scope=None) -> TextRun:
    # §BH50(f)(1): an optional declaration passes through; the default keeps
    # every existing call byte-identical
    return TextRun(name=name, text=text, x=cx, y=y, size_pt=size_pt,
                   color=color, font=font, align="center",
                   print_scope=print_scope)
