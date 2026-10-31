"""Running code revision (Phase 2A-6C-CORR §8).

Task #49's retry failed on a worker that booted before the fix commit, and it
took process-start-time forensics to prove it. This makes the running
revision a first-class, logged fact: the worker stamps it at boot, every
Creative Director run records it, and the web process exposes it, so a
web/worker revision mismatch (a stale worker) is visible operationally
instead of inferred after the fact.

The revision is resolved once and cached. Order: an explicit build stamp
(CODE_REVISION env / setting, for deployments that ship without a .git), then
`git rev-parse`, then "unknown".
"""
from __future__ import annotations

import functools
import subprocess
from pathlib import Path

from django.conf import settings


@functools.lru_cache(maxsize=1)
def current_revision() -> str:
    """The short git revision (or build stamp) this process is running."""
    stamp = str(getattr(settings, "CODE_REVISION", "") or "").strip()
    if stamp:
        return stamp
    try:
        root = Path(settings.BASE_DIR)
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root), capture_output=True, text=True, timeout=5, check=False)
        rev = out.stdout.strip()
        if rev:
            return rev
    except (OSError, ValueError):
        pass
    return "unknown"


def revision_report() -> dict:
    """A bounded, credential-free description of the running revision."""
    return {"code_revision": current_revision()}


__all__ = ["current_revision", "revision_report"]
