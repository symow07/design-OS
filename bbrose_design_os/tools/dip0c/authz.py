"""Reviewer authorisation — COMPATIBILITY WRAPPER (DIP-1A-2 decoupling).

The policy used to live here. It now lives in the deployable application package, at
`bbrose_design_os/apps/accounts/authz_policy.py`, so the production Django app no longer
depends on this audit-tool package to boot. **There is exactly one policy definition**;
this module re-exports it verbatim and adds only the DIP-audit-specific glue that depends
on `tools.dip0c.config` (and therefore cannot live in the pure, Django-startup-safe
canonical module):

* `PARSER` — this tool's identity string;
* `STATE_ACTION` / `action_for_state()` — mapping DIP ownership/licence *states* to the
  action that confirming them requires (states are a DIP-ledger concept);
* `policy_document()` — the canonical policy plus the state mapping, unchanged so existing
  DIP reports (e.g. run_c3b2) serialise byte-for-byte as before.

Import direction: the audit tool depends on the app's canonical policy, never the reverse.
Adding the app package to `sys.path` here is an **audit-side** convenience so the DIP tools
keep running standalone from the repo root; production never runs this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Reach the deployable app package (repo_root/bbrose_design_os) so we can import the ONE
# canonical policy. This path insertion is on the AUDIT side only — the production Django
# app imports apps.accounts.authz_policy directly and never touches this module.
_APP_ROOT = Path(__file__).resolve().parents[2]  # the app folder (dip0c sits in its tools/ since 2026-10-04)
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from apps.accounts.authz_policy import *  # noqa: E402,F401,F403 — verbatim re-export
from apps.accounts import authz_policy as _canon  # noqa: E402

from . import config as C  # noqa: E402

PARSER = f"{C.TOOL_NAME}.authz/{C.TOOL_VERSION}"
POLICY_VERSION = _canon.POLICY_VERSION

# --- DIP-only: ownership/licence STATE -> the action confirming it requires --------
# States are a DIP-ledger concept (from tools.dip0c.config); they are not part of the
# pure authorization policy, so they stay here rather than in the canonical module.
STATE_ACTION = {
    C.OWN_BBROSE_CONFIRMED: _canon.CONFIRM_OWNERSHIP,
    C.OWN_THIRD_PARTY_CONFIRMED: _canon.CONFIRM_THIRD_PARTY,
    C.OWN_LICENSED_LIMITED: _canon.APPROVE_LIMITED_USE,
    C.OWN_JOINT_OR_CONTRACTED: _canon.APPROVE_LIMITED_USE,
    C.LIC_APPROVED: _canon.APPROVE_LICENSE,
    C.LIC_INTERNAL_ONLY: _canon.APPROVE_LICENSE,
    C.LIC_ATTRIBUTION_REQUIRED: _canon.APPROVE_LICENSE,
    C.LIC_MODIFICATION_RESTRICTED: _canon.APPROVE_LICENSE,
    C.LIC_EMBEDDING_RESTRICTED: _canon.APPROVE_LICENSE,
    C.LIC_REDISTRIBUTION_RESTRICTED: _canon.APPROVE_LICENSE,
}


def action_for_state(state: str) -> str:
    """Which action does confirming this state require?"""
    if state not in STATE_ACTION:
        raise _canon.NotAuthorized(f"{state!r} is not a human-confirmable state")
    return STATE_ACTION[state]


def policy_document() -> dict:
    """The canonical policy plus the DIP state mapping. Output unchanged from DIP-0C3b2."""
    return {
        "policy_version": _canon.POLICY_VERSION,
        "roles": list(_canon.ROLES),
        "actions": list(_canon.ACTIONS),
        "policy": {a: list(r) for a, r in _canon.POLICY.items()},
        "state_requires_action": dict(STATE_ACTION),
        "notes": [
            "no role may do everything",
            "SYSTEM_ADMIN may revoke and quarantine but may NOT confirm ownership "
            "or approve a licence — administrative power is not legal authority",
            "DESIGN_REVIEWER may review evidence but may not decide ownership",
            "APPROVE_LICENSE is LEGAL_REVIEWER only",
            "OBSERVER is read-only and appears in no policy entry",
            "git authorship is PROVENANCE, not AUTHORISATION",
        ],
    }
