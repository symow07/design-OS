"""A38 — the firing-trace instrument. Declared BEFORE the manifest.

Records every fallback firing in measurement code: site, invoking
computation, triggering input, substituted value. Prospective only —
it discharges nothing already committed. Failure to log is a raised
error, never a silent skip: an empty trace must mean nothing fired,
not that the recorder failed, or the instrument is a member of the
SILENT_PLAUSIBLE_FALLBACK class it audits (1q).
"""
import json
import os
import time

TRACE_PATH_ENV = "M6_FIRING_TRACE_PATH"


class TraceWriteError(RuntimeError):
    """The trace could not be recorded. Raised, never swallowed."""


def log_firing(site, computation, trigger, substituted):
    """Append one firing record. Raises on any write failure."""
    path = os.environ.get(TRACE_PATH_ENV)
    if not path:
        raise TraceWriteError(
            f"{TRACE_PATH_ENV} is unset — a traced site fired with "
            "no trace destination; refusing to continue silently")
    record = {"ts": time.time(), "site": site,
              "computation": computation, "trigger": trigger,
              "substituted": substituted}
    try:
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        raise TraceWriteError(f"trace write failed: {exc}") from exc
    return record


def traced_zero(site, context):
    """A89 wiring — logs the firing when a trace destination is set,
    then returns the pre-trace fallback value unchanged. Observation
    only: no computation differs with or without the trace."""
    if os.environ.get(TRACE_PATH_ENV):
        log_firing(site, context, {"branch": "fallback"}, 0.0)
    return 0.0
