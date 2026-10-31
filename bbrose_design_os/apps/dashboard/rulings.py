"""The owner's rulings and his review queue, read on the site (§BH55 Phase 3, 2026-09-20).

OWNER STANDING ORDER §BH55, PHASE 3: "Every capability the engine has is reachable and labelled in words a designer
understands." The register of his rulings (OWNER_BLOCKER_CLEARANCE.md) and his review queue (OWNER_REVIEW_QUEUE.md) —
the files every rule of this system cites — were read only through the brain, an MCP tool no page can call. Both are
read here as they stand: their `## ` sections, newest first, each one's text a click away, searchable by words. Both
files are appended to and never rewritten above their end, so a section's first line is a stable address for it.

Beside each ruling, the status the brain MEASURES — live, or superseded and by what — is shown as what it is: derived,
from the brain's last rebuild (var/brain/brain.sqlite, read-only), and never the truth, which is the register's own
text. Without the brain the page shows the rulings and no status. The brain's second, meaning-based search is not
offered; the search here is by words.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path

from django.conf import settings

SOURCES = {"register": ("RULINGS_REGISTER", "OWNER_BLOCKER_CLEARANCE.md", "The register of rulings"),
           "queue": ("RULINGS_QUEUE", "OWNER_REVIEW_QUEUE.md", "The review queue")}
_HEADING = re.compile(r"^## (.+)$")
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[—-]\s*")
_ID = re.compile(r"§[A-Z]+\d*(?:\([a-z0-9]+\))?")
STATUS_WORDS = {"LIVE": "live", "UNCLASSIFIED": "not classified", "ABSENT": "not found"}
SNIPPET = 220

_lock = threading.Lock()
_cache: dict = {}


def path_of(source: str) -> Path:
    setting, name, _ = SOURCES[source]
    configured = getattr(settings, setting, None)
    return Path(configured) if configured else Path(settings.BASE_DIR).resolve().parent / name


def title_of(source: str) -> str:
    return SOURCES[source][2]


def sections(source: str) -> list[dict] | None:
    """The file's `## ` sections in its order — each with its first line, its heading, its date and its § id where the
    heading names one — read once per change of the file. None when the file is not on this machine."""
    path = path_of(source)
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (source, str(path), stat.st_size, stat.st_mtime_ns)
    with _lock:
        if _cache.get(source, (None,))[0] != key:
            lines = path.read_text(encoding="utf-8").splitlines()
            found = []
            for n, line in enumerate(lines, 1):
                m = _HEADING.match(line)
                if m:
                    heading = m.group(1).strip()
                    d = _DATE.match(heading)
                    ident = _ID.search(heading)
                    found.append({"line": n, "heading": heading, "date": d.group(1) if d else "",
                                  "title": heading[d.end():] if d else heading, "id": ident.group(0) if ident else ""})
            for i, s in enumerate(found):
                s["end"] = (found[i + 1]["line"] - 1) if i + 1 < len(found) else len(lines)
            _cache[source] = (key, found, lines)
        return _cache[source][1]


def _lines(source: str) -> list[str]:
    sections(source)
    return _cache.get(source, (None, None, []))[2]


def text_of(source: str, line: int) -> dict | None:
    """The section that begins on ``line``, its whole text, and the sections before and after it."""
    found = sections(source) or []
    for i, s in enumerate(found):
        if s["line"] == line:
            body = "\n".join(_lines(source)[s["line"] - 1:s["end"]])
            return {**s, "text": body, "prev": found[i - 1] if i else None,
                    "next": found[i + 1] if i + 1 < len(found) else None}
    return None


def search(source: str, q: str) -> list[dict]:
    """The sections whose text holds every word asked for (longer than two letters), newest first, each with a snippet
    around the first word found."""
    words = [w for w in re.findall(r"[\w§()]+", (q or "").lower()) if len(w) > 2]
    if not words:
        return []
    lines = _lines(source)
    out = []
    for s in reversed(sections(source) or []):
        body = "\n".join(lines[s["line"] - 1:s["end"]])
        low = body.lower()
        if all(w in low for w in words):
            at = low.find(words[0])
            start = max(0, at - SNIPPET // 2)
            out.append({**s, "snippet": ("…" if start else "") + body[start:start + SNIPPET].replace("\n", " ") + "…"})
    return out


def brain_statuses() -> dict:
    """{§id: {status, superseded_by}} for the register's sections, as the brain measured them at its last rebuild, with
    that rebuild's time — {} without the brain. Read-only; derived, never the truth."""
    root = Path(settings.BASE_DIR).resolve().parent / "var" / "brain"
    db = Path(getattr(settings, "RULINGS_BRAIN_DB", None) or root / "brain.sqlite")
    if not db.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute("select id, status, superseded_by from sections where path = ?",
                               ("OWNER_BLOCKER_CLEARANCE.md",)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    built = ""
    try:
        built = json.loads((db.parent / "freshness.json").read_text()).get("built_at") or ""
    except (OSError, ValueError):
        pass
    return {"built_at": built,
            "by_id": {i: {"status": s, "superseded_by": sb} for i, s, sb in rows if i}}


def status_words(measured: dict | None) -> str:
    if not measured:
        return ""
    status = measured.get("status") or ""
    if status.startswith("SUPERSEDED"):
        return f"superseded by {measured.get('superseded_by') or status.partition('BY ')[2] or 'a later ruling'}"
    return STATUS_WORDS.get(status, status.lower())
