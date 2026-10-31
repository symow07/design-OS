"""Test-session hygiene for the DIP-0C tools (frozen-artifact protection).

Point milestone WRITES at a throwaway temp directory for the whole test session — set
BEFORE any `tools.dip0c` module is imported, so ordinary tests never rewrite the frozen,
committed milestone tree under `docs/design_intelligence/dip0c/`. Reads of frozen inputs
(pilot manifests, prior reconciliations, the taxonomy) still resolve to the committed tree.

Regenerating the committed artifacts stays explicit and opt-in
(`DIP0C_ALLOW_MILESTONE_WRITE=1`, and normally a dedicated command) — it is never a side
effect of running the test suite. An explicit regeneration environment is not clobbered, and a
folder it names is never removed: only the two folders made here are, when the test process exits.
"""
import atexit
import os
import shutil
import tempfile


def _throwaway(prefix):
    """A temp folder for this test process, removed when the process exits."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path


if "DIP0C_MILESTONE_OUTPUT" not in os.environ:
    os.environ["DIP0C_MILESTONE_OUTPUT"] = _throwaway("dip0c-milestone-test-")
if "DIP0C_C3A_OUTPUT_ROOT" not in os.environ:
    os.environ["DIP0C_C3A_OUTPUT_ROOT"] = _throwaway("dip0c-c3a-test-")
