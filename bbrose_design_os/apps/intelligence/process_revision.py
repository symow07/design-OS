"""Development-only running-revision stamp — DIP-1C-5C-CORR-4.

The duplicate-record incident was a deployment-version mismatch, not a code defect: the dev
server ran with `--noreload` and predated two committed corrections, so the browser executed
old mutation behaviour while the repository and its tests were correct.

A reviewer had no way to see that. This stamps the revision the PROCESS is running, read
once at import — never per request, and never by shelling out inside a view. It renders only
when DEBUG is on; it is a development aid, not a deployment system.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from django.conf import settings


def _read_revision() -> str:
    """Resolved once at import. Falls back to UNKNOWN rather than guessing."""
    root = Path(settings.BASE_DIR).parent
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False)
        revision = (result.stdout or "").strip()
        if not revision:
            return "UNKNOWN"
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=False)
        return f"{revision}+dirty" if (dirty.stdout or "").strip() else revision
    except Exception:                       # never let a dev banner break a page
        return "UNKNOWN"


#: Evaluated at import: this is the revision THIS process loaded, which is exactly the
#: question the incident could not answer.
PROCESS_REVISION = _read_revision()


def process_revision_banner():
    """`{revision, show}` — shown only in DEBUG."""
    return {"revision": PROCESS_REVISION, "show": bool(settings.DEBUG)}
