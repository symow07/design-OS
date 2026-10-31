"""Real Adobe Illustrator execution adapter (Phase 2A-8 §11).

Runs a generated design_handoff.jsx inside an actual installed Illustrator
via macOS osascript (`do javascript`), captures the script's bounded summary
(the last-expression string the runtime builds without any JSON dependency)
and returns it parsed. The phase's verification claim comes from THIS
channel; a missing/failed Illustrator yields
ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED — a mocked object model never
counts as verification.

Safety: read-only toward the jsx; the runtime itself performs no writes and
leaves the document open, unsaved, for human inspection.
"""
from __future__ import annotations

import json
import shutil
import subprocess

DEFAULT_TIMEOUT_S = 180


def illustrator_available() -> bool:
    if shutil.which("osascript") is None:
        return False
    try:
        probe = subprocess.run(
            ["osascript", "-e",
             'exists application id "com.adobe.illustrator"'],
            capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        # a modal dialog in a running Illustrator blocks AppleEvents —
        # treat as unavailable rather than hanging the caller
        return False
    return probe.returncode == 0 and "true" in probe.stdout.lower()


def run_jsx(jsx_path: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    """Execute the handoff script in Illustrator; return the parsed summary.

    Returns {"executed": False, "reason": ...} when Illustrator is
    unavailable or execution fails — callers surface
    ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED in that case.
    """
    if not illustrator_available():
        return {"executed": False,
                "reason": "Adobe Illustrator not available via osascript"}
    # warm-up: freshly relaunched Illustrator can transiently fail text
    # attribute assignment ('MRAP') while its font index settles — one
    # trivial textFonts touch first absorbs the race
    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application id "com.adobe.illustrator" to do javascript '
             '"app.textFonts.length"'],
            capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        pass
    # [his goal of 2026-10-13, (10): no silent fallbacks] the Apple event waits as long as the run may take — by
    # default it gives up after two minutes while Illustrator goes on and saves, so a file built in 145 s was said
    # "not saved" and the layered file was not offered
    script = (
        f"with timeout of {int(timeout_s)} seconds\n"
        'tell application id "com.adobe.illustrator"\n'
        f'  do javascript (POSIX file "{jsx_path}") '
        "show debugger on runtime error\n"
        "end tell\n"
        "end timeout"
    )
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True,
                                timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"executed": False, "reason": f"timeout after {timeout_s}s"}
    if result.returncode != 0:
        return {"executed": False,
                "reason": (result.stderr or result.stdout).strip()[:500]}
    raw = result.stdout.strip()
    try:
        summary = json.loads(raw)
    except ValueError:
        return {"executed": True, "raw": raw[:1000],
                "reason": "summary was not parseable JSON"}
    summary["executed"] = True
    return summary


__all__ = ["illustrator_available", "run_jsx", "DEFAULT_TIMEOUT_S"]
