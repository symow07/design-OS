"""Script detection for text runs — §BH32(d)(i).

A text run's direction is a property of its TEXT, not a flag a producer
remembers to set. §BH31 measured that no producer ever set ``TextRun.rtl``,
so an Arabic product name reached the emitter as a left-to-right run and
would have been drawn with a Latin face carrying no Arabic glyph. The rule
here is the Unicode bidi paragraph rule (P2/P3): the FIRST strong-directional
character decides — Arabic-script letters are right-to-left, Latin letters
are left-to-right, everything else (digits, punctuation, space) is neutral
and decides nothing. ``split_script_runs`` is the per-run companion the
selection layer (§BH32(e)) uses so a face only ever receives the script it
carries.
"""
from __future__ import annotations

ARABIC_RANGES = (
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
)
LATIN_RANGES = (
    (0x0041, 0x005A), (0x0061, 0x007A),   # A-Z a-z
    (0x00C0, 0x024F),                     # Latin-1 Supplement letters + Extended-A/B
    (0x1E00, 0x1EFF),                     # Latin Extended Additional
)
ARABIC = "arabic"
LATIN = "latin"
NEUTRAL = "neutral"


def _in(ranges, ch: str) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in ranges)


def is_arabic_char(ch: str) -> bool:
    return _in(ARABIC_RANGES, ch)


def is_latin_char(ch: str) -> bool:
    return _in(LATIN_RANGES, ch)


def script_of_char(ch: str) -> str:
    if is_arabic_char(ch):
        return ARABIC
    if is_latin_char(ch):
        return LATIN
    return NEUTRAL


def first_strong_script(text: str) -> str | None:
    """The script of the first strong-directional character, or None when the
    text carries no letter of either script (digits-only, empty, symbols)."""
    for ch in text or "":
        s = script_of_char(ch)
        if s != NEUTRAL:
            return s
    return None


def is_rtl(text: str) -> bool:
    """Right-to-left iff the first strong character is Arabic (bidi P2/P3)."""
    return first_strong_script(text) == ARABIC


def scripts_in(text: str) -> set[str]:
    """The strong scripts present in ``text`` (subset of {arabic, latin})."""
    return {script_of_char(ch) for ch in (text or "")} - {NEUTRAL}


def split_script_runs(text: str) -> list[tuple[str, str]]:
    """``[(script, chunk), ...]`` — consecutive chunks by strong script; neutral
    characters attach to the chunk in progress (or to the first strong chunk
    that follows, when the text starts neutral). A text with no strong
    character yields one ``(neutral, text)`` chunk."""
    runs: list[list] = []
    pending = ""
    for ch in text or "":
        s = script_of_char(ch)
        if s == NEUTRAL:
            if runs:
                runs[-1][1] += ch
            else:
                pending += ch
            continue
        if runs and runs[-1][0] == s:
            runs[-1][1] += ch
        else:
            runs.append([s, pending + ch])
            pending = ""
    if not runs:
        return [(NEUTRAL, text or "")] if (text or "") else []
    return [(s, chunk) for s, chunk in runs]


__all__ = ["ARABIC", "LATIN", "NEUTRAL", "is_arabic_char", "is_latin_char",
           "script_of_char", "first_strong_script", "is_rtl", "scripts_in",
           "split_script_runs"]


#: [his final goal, 2026-10-05, C8: "A LINE THAT BREAKS DROPS ITS SEPARATOR. When "LIP GLOSS · ملمّع الشفاه" breaks onto
#: two lines, the "·" goes."] the marks that separate two phrases set on one line — kept on one line, dropped where the
#: line breaks between them. A dash is not one of them: "BATCH —" is a blank for the filler to fill
SEPARATORS = frozenset("·•|/")


def drop_break_separators(lines: list) -> list:
    """``lines`` (the lines one phrase was broken into) with each separator standing at a break taken away: a
    separator ending a line that another follows, or starting a line that follows another. A separator inside a line —
    the phrase unbroken there — is kept."""
    out = []
    for i, line in enumerate(lines):
        words = str(line).split()
        if i < len(lines) - 1:
            while words and words[-1] in SEPARATORS:
                words.pop()
        if i > 0:
            while words and words[0] in SEPARATORS:
                words.pop(0)
        out.append(" ".join(words))
    return out

