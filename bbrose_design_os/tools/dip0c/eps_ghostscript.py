"""EPS Ghostscript adapter — C1B (DIP-0C1): implemented but BLOCKED.

This adapter's job in DIP-0C1 is to env-detect gs and return an explicit blocked
record either way — never to convert, never to auto-install. Whether Ghostscript is
installed is a fact about the machine and is NOT asserted here: with no binary on
PATH the capability state is `GHOSTSCRIPT_NOT_INSTALLED`, and with one present it is
`GHOSTSCRIPT_PILOT_PENDING`. In both, geometry stays `REQUIRES_TOOL` and the adapter
status is `BLOCKED_TOOL_UNAVAILABLE`.

The full conversion path (EPS → temporary PDF *derivative* under
`var/.../temporary/eps_pdf/`, then audit via the dip0b PDF machinery, tier
`DERIVED_VIA_GHOSTSCRIPT`) is intentionally gated behind BOTH a present gs binary
AND an explicit `enable=True` flag, and even then DIP-0C1 does not run the bulk
conversion — a separate converter pilot + fidelity gate must pass first. The
derivative is never the canonical asset and the source EPS is never touched.
"""
from __future__ import annotations

import shutil

from tools.dip0.provenance import Inferred

from . import config as C

PARSER = f"{C.TOOL_NAME}.eps_ghostscript/{C.TOOL_VERSION}"

# Names the adapter would probe if it were ever enabled. Detection only.
GS_BINARIES = ("gs", "gsc", "gswin64c", "gswin32c")

# Safe-mode invocation the adapter WOULD use (recorded, not executed here).
SAFE_ARGS = ("-dSAFER", "-dNOPAUSE", "-dBATCH", "-dNOPROMPT",
             "-dMaxBitmap=0", "-sDEVICE=pdfwrite")


def detect_ghostscript() -> dict:
    """Detect gs on PATH. Detection only — never installs, never runs it."""
    for name in GS_BINARIES:
        path = shutil.which(name)
        if path:
            return {"present": True, "binary": name, "path": path}
    return {"present": False, "binary": None, "path": None}


def audit(rel_path: str, *, enable: bool = False) -> dict:
    """C1B entry. With gs absent (or `enable=False`) this returns the blocked
    record. It never converts in DIP-0C1 even when gs is present — bulk
    conversion waits for the converter pilot + fidelity gate."""
    gs = detect_ghostscript()
    if not gs["present"]:
        return _blocked(rel_path, C.EPS_GHOSTSCRIPT_NOT_INSTALLED,
                        "no Ghostscript binary on PATH", gs, enable)
    if not enable:
        return _blocked(rel_path, C.EPS_GHOSTSCRIPT_PILOT_PENDING,
                        "Ghostscript present but not explicitly enabled "
                        "(--enable-ghostscript); converter pilot + fidelity gate "
                        "must pass before any conversion", gs, enable)
    # gs present AND enabled: DIP-0C1 still defers the actual conversion to the
    # pilot harness (a later, reviewed step) rather than converting inline.
    return _blocked(rel_path, C.EPS_GHOSTSCRIPT_PILOT_PENDING,
                    "Ghostscript enabled; conversion deferred to the reviewed "
                    "converter pilot (not run inline in DIP-0C1)", gs, enable)


def _blocked(rel_path, capability_state, reason, gs, enable) -> dict:
    return {
        "format": ".eps",
        "parser": PARSER,
        "adapter_status": C.GHOSTSCRIPT_ADAPTER_BLOCKED,
        "eps_capability_state": capability_state,
        "ghostscript": {"detected": gs["present"], "binary": gs["binary"],
                        "path": gs["path"], "enabled_flag": enable,
                        "auto_install": False},
        "planned_invocation": {"args": list(SAFE_ARGS),
                               "network": "disabled",
                               "derivative_dir": C.relpath(C.OUT_EPS_PDF),
                               "note": "recorded for review; NOT executed"},
        "derived_geometry": _inf(None, C.TIER_REQUIRES_TOOL, "tool_unavailable",
                                 [reason], 0.0),
        "conversion": {"attempted": False, "reason": reason,
                       "source_untouched": True, "derivative": None},
        "licensing_note": ("Ghostscript is AGPL; if it becomes a production "
                           "dependency, record version + licence review in "
                           "native_tool_requirements.md before bundling"),
    }


def _inf(value, tier, source, evidence, confidence):
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d
