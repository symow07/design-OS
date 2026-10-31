"""A record's own text, said on screen in words (the owner's goal of 2026-09-25, (d): "Plain words everywhere. No engine
codes on screen."). The record keeps what it wrote; only what the page shows changes."""
import re
from datetime import datetime

from django import template

register = template.Library()

_CAPS = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]{2,})+\b")
_SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
_GATE = re.compile(r"\bgate[ _]?([12])\b", re.I)
#: a fingerprint the record wrote into its text — a sha256, or a digest cut from one — with the word naming it
_PRINT = re.compile(r"(?:\b(?:sha256|sha|hash|digest|fingerprint)\b[:= ]*)?\b[0-9a-fA-F]{16,}\b")


@register.filter
def plain(value) -> str:
    """A code the record wrote into its text — "WEB_GROUNDED_NEW_PRODUCT_MODE", "container_rejected",
    "straight_tuck_end_carton" — said as words ("web grounded new product mode", "container rejected"); a fingerprint
    in it ("hash dc9d799dea50a744…") as an ellipsis, the record keeping it whole. For text, never a file's name or an
    address."""
    text = _PRINT.sub("…", str(value if value is not None else ""))
    text = _CAPS.sub(lambda m: m.group(0).lower().replace("_", " "), text)
    text = _SNAKE.sub(lambda m: m.group(0).replace("_", " "), text)
    return _GATE.sub(lambda m: "concept" if m.group(1) == "1" else "review", text)   # its two stops, as every screen says


@register.filter
def target(value) -> str:
    """What is designed, in the words every screen uses ("product_container" -> "Product container")."""
    from apps.dashboard.words import target_words
    return target_words(value)


@register.filter
def when(value) -> str:
    """A record's ISO time — "2026-09-17T08:55:11Z" — as a date and a time ("17 September 2026, 08:55"); what does not
    parse, as written."""
    if isinstance(value, datetime):
        return value.strftime("%-d %B %Y, %H:%M")
    text = str(value or "")
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return at.strftime("%-d %B %Y") if len(text) <= 10 else at.strftime("%-d %B %Y, %H:%M")   # a date alone, as written
