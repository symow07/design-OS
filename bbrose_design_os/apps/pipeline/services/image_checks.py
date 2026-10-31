"""Deterministic, model-free image checks for QA.

These run alongside Claude's visual judgment to provide signals that cannot
drift between runs:

  - ``palette_distance`` — how close the image's dominant colors are to the
    brand palette (perceptual CIE-Lab ΔE). A real pass/fail signal.
  - ``aspect_ok``        — whether the image aspect ratio matches the intended
    packaging ratio. A real pass/fail signal.
  - ``text_is_placeholder`` (OCR) — INFORMATIONAL ONLY. Flags that AI-rendered
    text looks like garbled placeholder. Never used to fail a *concept* render,
    where final type is added later in vector.

Every check degrades gracefully: a missing file, an unreadable image, missing
brand hexes, or a missing ``tesseract`` binary returns a neutral result with an
explanatory ``note`` rather than raising. Only dependency is Pillow (already
installed); pytesseract is optional.

The thresholds below are deliberately lenient. A concept render shifts colors
through lighting, shadow, and highlight, so the palette check is tuned to catch
*gross* misses (a cold blue/silver/black render) without vetoing legitimate
blush/nude/cream work. Claude's vision handles the subtle "feels clinical" read.
"""

from __future__ import annotations

import re

# The target ratio follows the configured render size (settings.IMAGE_SIZE,
# e.g. "1024x1536" for gpt-image portrait, "1024x1792" for legacy dall-e-3) so
# the QA aspect check stays correct when the image model changes.
def _target_ratio_from_settings() -> float:
    try:
        from django.conf import settings
        w, h = settings.IMAGE_SIZE.lower().split("x")
        return float(w) / float(h)
    except Exception:  # unconfigured/parse failure — legacy portrait fallback
        return 1024 / 1792


DEFAULT_TARGET_RATIO = _target_ratio_from_settings()

# ΔE76 in Lab space: ~2.3 is "just noticeable", ~10 clearly different but
# related, 25+ a different colour family. We accept up to 25 as "near brand".
PALETTE_TOLERANCE_DE = 25.0
# Fraction of the image's visual weight that must sit near the palette to pass.
PALETTE_MIN_COVERAGE = 0.40
# Aspect ratio may drift ±18% (crop/letterbox tolerance) and still pass.
ASPECT_TOLERANCE = 0.18


# --- colour helpers --------------------------------------------------------

def _hex_to_rgb(hex_str):
    """'#E8B4B8' / 'e8b4b8' / '#eab' -> (232, 180, 184), or None if malformed."""
    if not hex_str:
        return None
    h = str(hex_str).strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _rgb_to_lab(rgb):
    """sRGB (0-255) -> CIE-Lab (D65) for perceptual distance."""
    def _lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _lin(rgb[0]), _lin(rgb[1]), _lin(rgb[2])
    # linear RGB -> XYZ
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    # normalise by D65 white point
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883

    def _f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = _f(x), _f(y), _f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e(lab1, lab2):
    """CIE76 ΔE — Euclidean distance in Lab. Good enough for a guardrail."""
    return sum((a - b) ** 2 for a, b in zip(lab1, lab2)) ** 0.5


def _dominant_colors(path, max_colors=8, sample=128):
    """Return [(weight, (r,g,b)), ...] sorted by weight (desc), weights sum ~1.

    Thumbnails the image for speed, then adaptive-quantizes to a small palette.
    """
    from PIL import Image

    with Image.open(path) as im:
        img = im.convert('RGB')
        img.thumbnail((sample, sample))
        quant = img.quantize(colors=max_colors)
        palette = quant.getpalette()
        counts = quant.getcolors() or []

    total = sum(c for c, _ in counts) or 1
    out = []
    for count, idx in counts:
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        out.append((count / total, rgb))
    out.sort(reverse=True, key=lambda t: t[0])
    return out


# --- public checks ---------------------------------------------------------

#: [His test blocker on design 122, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 3: "the product's colour comes from my
#: brief, the BACKGROUND is chosen to contrast with it ... the picture the map reads must be clean and contrasting."] a
#: concept stands on a plain backdrop that contrasts with it, so the palette is the design's, never its backdrop's: the
#: colours within BACKDROP_DE of a plain border's median (its spread at most BACKDROP_SPREAD) are left out of the
#: palette's weights, where at least BACKDROP_MIN_REST of the picture is something else
BACKDROP_DE = 12.0
BACKDROP_SPREAD = 8.0
BACKDROP_MIN_REST = 0.15
#: the border is read off the same thumbnail the palette is sampled from
BACKDROP_SAMPLE = 128


def backdrop_lab(path):
    """The picture's plain backdrop — the median Lab of its border — or None where its border is not plain."""
    from PIL import Image

    with Image.open(path) as im:
        img = im.convert('RGB')
        img.thumbnail((BACKDROP_SAMPLE, BACKDROP_SAMPLE))
    w, h = img.size
    px = img.load()
    edge = ([px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
            + [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)])
    labs = [_rgb_to_lab(c) for c in edge]
    med = tuple(sorted(lab[i] for lab in labs)[len(labs) // 2] for i in range(3))
    spread = sorted(_delta_e(lab, med) for lab in labs)[len(labs) // 2]
    return med if spread <= BACKDROP_SPREAD else None


def palette_distance(path, brand_hexes,
                     tolerance=PALETTE_TOLERANCE_DE,
                     min_coverage=PALETTE_MIN_COVERAGE):
    """How much of the image sits near the brand palette.

    Returns a dict with ``on_brand`` (bool | None), ``coverage`` (0-1 weighted
    fraction within ``tolerance`` ΔE of any brand colour), ``mean_delta_e``,
    and the image's ``dominant_colors`` (hex) for transparency in logs.
    """
    brand_labs = [_rgb_to_lab(rgb) for rgb in
                  (_hex_to_rgb(h) for h in (brand_hexes or [])) if rgb]
    if not brand_labs:
        return {'available': False, 'on_brand': None,
                'note': 'no brand hex colours available'}
    try:
        colors = _dominant_colors(path)
    except Exception as e:  # noqa: BLE001 — any decode failure degrades gracefully
        return {'available': False, 'on_brand': None,
                'note': f'could not read image: {e}'}
    if not colors:
        return {'available': False, 'on_brand': None,
                'note': 'no colours sampled from image'}
    # [his test blocker on design 122, item 3] the design's palette, never its plain backdrop's
    backdrop_left_out = False
    try:
        backdrop = backdrop_lab(path)
    except Exception as e:  # noqa: BLE001 — a border that cannot be read leaves the palette as it was
        return {'available': False, 'on_brand': None, 'note': f'could not read image: {e}'}
    if backdrop is not None:
        rest = [(weight, rgb) for weight, rgb in colors if _delta_e(_rgb_to_lab(rgb), backdrop) > BACKDROP_DE]
        kept = sum(weight for weight, _rgb in rest)
        if kept >= BACKDROP_MIN_REST:
            colors = [(weight / kept, rgb) for weight, rgb in rest]
            backdrop_left_out = True

    on_brand_weight = 0.0
    distances = []
    dominant_hex = []
    for weight, rgb in colors:
        nearest = min(_delta_e(_rgb_to_lab(rgb), bl) for bl in brand_labs)
        distances.append(nearest)
        if nearest <= tolerance:
            on_brand_weight += weight
        dominant_hex.append('#%02X%02X%02X' % rgb)

    coverage = round(on_brand_weight, 3)
    mean_d = round(sum(distances) / len(distances), 1)
    return {
        'available': True,
        'on_brand': coverage >= min_coverage,
        'coverage': coverage,
        'mean_delta_e': mean_d,
        'dominant_colors': dominant_hex,
        'backdrop_left_out': backdrop_left_out,
        'note': (f'{int(coverage * 100)}% of visual weight within '
                 f'ΔE {tolerance:g} of the brand palette'
                 + (' — its plain backdrop left out' if backdrop_left_out else '')),
    }


def aspect_ok(path, target_ratio=DEFAULT_TARGET_RATIO, tolerance=ASPECT_TOLERANCE):
    """Whether the image's width/height ratio matches the intended ratio."""
    from PIL import Image

    try:
        with Image.open(path) as img:
            w, h = img.size
    except Exception as e:  # noqa: BLE001
        return {'available': False, 'ok': None,
                'note': f'could not read image: {e}'}
    if not h or not target_ratio:
        return {'available': False, 'ok': None, 'note': 'degenerate dimensions'}

    ratio = w / h
    diff = abs(ratio - target_ratio) / target_ratio
    return {
        'available': True,
        'ok': diff <= tolerance,
        'ratio': round(ratio, 3),
        'target_ratio': round(target_ratio, 3),
        'note': (f'aspect {ratio:.3f} vs target {target_ratio:.3f} '
                 f'(±{int(tolerance * 100)}%)'),
    }


def text_is_placeholder(path):
    """INFORMATIONAL ONLY — flag whether rendered text looks like placeholder.

    Never used to fail a concept render (final type is added later in vector).
    Gracefully skips if pytesseract or the tesseract binary is unavailable.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {'available': False, 'is_placeholder': None,
                'note': 'pytesseract not installed (OCR optional)'}
    try:
        with Image.open(path) as img:
            text = pytesseract.image_to_string(img)
    except Exception as e:  # noqa: BLE001 — TesseractNotFoundError lands here too
        return {'available': False, 'is_placeholder': None,
                'note': f'OCR unavailable: {e}'}

    tokens = re.findall(r'[A-Za-z]{2,}', text)
    if not tokens:
        return {'available': True, 'is_placeholder': None, 'text_found': '',
                'note': 'no legible text detected'}

    def _wordlike(t):
        return len(t) >= 3 and bool(re.search(r'[aeiouAEIOU]', t))

    ratio = sum(1 for t in tokens if _wordlike(t)) / len(tokens)
    placeholder = ratio < 0.5
    return {
        'available': True,
        'is_placeholder': placeholder,
        'text_found': ' '.join(tokens)[:120],
        'wordlike_ratio': round(ratio, 2),
        'note': ('rendered text looks like placeholder/garbled'
                 if placeholder else 'rendered text looks word-like'),
    }


def run_image_checks(path, brand_hexes, target_ratio=DEFAULT_TARGET_RATIO):
    """Convenience: run all deterministic checks and return them keyed."""
    return {
        'palette': palette_distance(path, brand_hexes),
        'aspect': aspect_ok(path, target_ratio),
        'ocr': text_is_placeholder(path),
    }


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("input QC of inherently 8-bit sources — the display frame is the authentic artifact")
