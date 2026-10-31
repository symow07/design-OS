"""H2 design-request pipeline — DELEGATING SHIM.

The fail-closed stage validators that lived here through both live arcs
were PROMOTED VERBATIM into engine code at
``apps/pipeline/services/h2_design_request.py`` (§O-session work item 2 —
promotion, not rewrite; the two run trees validating unchanged under the
promoted module is the recorded regression). This shim keeps the CLI and
the function names every launcher and session script already uses.

Stdlib-only import via file location: no Django, no venv, no package chain
— ``python3 h2_pipeline.py <request_dir>`` keeps working exactly as before.
"""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_ENGINE = HERE.parents[2] / "apps" / "pipeline" / "services" / \
    "h2_design_request.py"

_spec = importlib.util.spec_from_file_location("h2_design_request", _ENGINE)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("h2_design_request", _mod)
_spec.loader.exec_module(_mod)

MEASUREMENT_TIERS = _mod.MEASUREMENT_TIERS
LEDGER_ENTRY_REQUIRED = _mod.LEDGER_ENTRY_REQUIRED
CANDIDATE_REQUIRED = _mod.CANDIDATE_REQUIRED
CANDIDATE_MIN, CANDIDATE_MAX = _mod.CANDIDATE_MIN, _mod.CANDIDATE_MAX
KNOWN_REQUEST_DIRS = _mod.KNOWN_REQUEST_DIRS
validate_brief = _mod.validate_brief
validate_ledger = _mod.validate_ledger
validate_candidates = _mod.validate_candidates
validate_request = _mod.validate_request


if __name__ == "__main__":
    out = validate_request(sys.argv[1] if len(sys.argv) > 1
                           else HERE / "es3083_lid_alt_01")
    print(json.dumps(out, indent=1))
    sys.exit(0 if out["verdict"] == "PASS" else 1)
