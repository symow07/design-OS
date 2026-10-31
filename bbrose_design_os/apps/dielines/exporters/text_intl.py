"""Arabic text shaping for reportlab (2026-07-07).

reportlab draws glyphs exactly as given — no complex-script shaping, no bidi.
Arabic needs two passes before drawing:
  1. arabic_reshaper — join letters into their presentation forms
  2. python-bidi   — reorder logical text into visual (right-to-left) order

Wrapping MUST happen on the LOGICAL text (measuring reshaped widths) and the
bidi pass applied per LINE afterwards; wrapping after bidi scrambles the line
order (the classic RTL-wrap bug).

Everything degrades gracefully: if the libs or the Arabic font are missing,
has_ar_support() is False and the sticker renders EN/ES only.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


_keep_harakat_reshaper = None


def _libs(keep_harakat: bool = False):
    """(reshape_fn, bidi_fn) or None when the pure-Python deps are absent.

    §BH33(3): ``keep_harakat`` returns a reshaper configured to KEEP harakat
    and tanween (arabic_reshaper deletes them by default) — asked for by the
    non-exempt drawer only; every exempt caller takes the default, so the
    regulatory sticker's output is byte-identical before and after.
    """
    global _keep_harakat_reshaper
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        if keep_harakat:
            if _keep_harakat_reshaper is None:
                _keep_harakat_reshaper = arabic_reshaper.ArabicReshaper(
                    configuration={"delete_harakat": False})
            return _keep_harakat_reshaper.reshape, get_display
        return arabic_reshaper.reshape, get_display
    except Exception:  # noqa: BLE001 — optional dependency path
        return None


def shape_ar(text: str, *, keep_harakat: bool = False) -> str:
    """Logical Arabic -> visual presentation-form string ('' passthrough).
    §BH33(3): ``keep_harakat`` keeps harakat and tanween (non-exempt surfaces)."""
    if not text:
        return text
    libs = _libs(keep_harakat)
    if libs is None:
        return text
    reshape, get_display = libs
    try:
        return get_display(reshape(text))
    except Exception:  # noqa: BLE001 — never break an export over shaping
        logger.warning("arabic shaping failed; drawing unshaped text")
        return text


def wrap_ar(text: str, font_name: str, font_size: float, max_width: float,
            latin_font: str | None = None, keep_harakat: bool = False) -> list[str]:
    """``wrap_ar_logical``'s lines, each shaped and put in visual order."""
    libs = _libs(keep_harakat)
    lines = wrap_ar_logical(text, font_name, font_size, max_width, latin_font=latin_font, keep_harakat=keep_harakat)
    if libs is None:
        return lines
    reshape, get_display = libs
    shaped = []
    for line in lines:
        try:
            shaped.append(get_display(reshape(line)))
        except Exception:  # noqa: BLE001
            shaped.append(line)
    return shaped


def wrap_ar_logical(text: str, font_name: str, font_size: float, max_width: float,
                    latin_font: str | None = None, keep_harakat: bool = False) -> list[str]:
    """Wrap LOGICAL Arabic text to max_width points — the lines still in logical order ([his final goal, 2026-10-05,
    C5] a label's Arabic heading is drawn bold apart from its text, each shaped by its drawer).

    Greedy word wrap measuring the RESHAPED width of each candidate line so
    joined-form contractions are accounted for; get_display runs per final
    line, preserving the correct visual order line by line. ``latin_font``
    measures the non-Arabic runs (the Arabic face has no Latin glyphs, which
    would otherwise measure 0 and overflow the line). ``keep_harakat`` keeps the
    harakat and the shadda (a document that keeps its Arabic marks, his rule of
    2026-10-05: "the Arabic ملمّع as my brief writes it").
    """
    if not text:
        return []
    libs = _libs(keep_harakat)
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if libs is None:
        return [text]
    reshape, get_display = libs

    def width(logical: str) -> float:
        try:
            shaped = reshape(logical)
        except Exception:  # noqa: BLE001
            shaped = logical
        if not latin_font:
            return stringWidth(shaped, font_name, font_size)
        return sum(
            stringWidth(run, font_name if is_ar else latin_font, font_size)
            for is_ar, run in split_script_runs(shaped)
        )

    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and width(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def has_ar_support(arabic_font: str | None) -> bool:
    """True when both the shaping libs and a registered Arabic font exist."""
    return bool(arabic_font) and _libs() is not None


def _is_arabic_char(ch: str) -> bool:
    o = ord(ch)
    return (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F
            or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF)


def split_script_runs(display_text: str) -> list[tuple[bool, str]]:
    """[(is_arabic, run)] over a VISUAL-order line.

    Noto Naskh Arabic carries no Latin glyphs, so mixed lines (INCI names,
    'BBROSE' inside Arabic copy) must switch fonts per run. After bidi the
    line is already in left-to-right drawing order, so runs draw plainly.
    Neutral characters (spaces, punctuation) stick to the preceding run.
    """
    runs: list[tuple[bool, str]] = []
    current_ar: bool | None = None
    buf = ""
    for ch in display_text:
        if ch.isspace() or not ch.isalnum():
            ar = current_ar if current_ar is not None else False
        else:
            ar = _is_arabic_char(ch)
        if current_ar is None or ar == current_ar:
            buf += ch
            current_ar = ar
        else:
            runs.append((current_ar, buf))
            buf, current_ar = ch, ar
    if buf:
        runs.append((bool(current_ar), buf))
    return runs
