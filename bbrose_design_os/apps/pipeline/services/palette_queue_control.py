"""A98 — the run-level trace control. Structural, not a convention.

A38's positive control was satisfied at the INSTRUMENT level and never
at the RUN level, which left the 88-frame combined-manifest queue
unable to distinguish "trace live, zero firings" from "trace dead in
this process". Per 2o that distinction is created by the run emitting
its own control record at the time, or it never exists.

Two halves, both raising:

- ``begin_traced_queue`` is the FIRST act of every render queue whose
  output will be cited as trace evidence. It sets the trace
  destination, fires a deliberate control through the identical path
  every wired site uses, reads the record back from disk, and stamps
  the queue ledger. A process that cannot prove its trace live before
  frame one does not render frame one.

- ``read_trace_evidence`` is the citing path. A queue ledger carrying
  no control stamp is not trace evidence: its trace observations are
  unreadable in both directions — absence of firings cannot be read
  as zero, presence cannot be read as complete — and the reader
  REJECTS it. Rejection is a raise, never a warning.
"""
import json
import os

from apps.pipeline.services import palette_firing_trace as FT

CONTROL_SITE = "queue_control:first_act"
LEDGER_KEY = "trace_controls"

#: The control stamp emitted by THIS process, or None. A ledger save
#: path may consult this via assert_process_controlled so that frames
#: cannot enter a ledger from a process that never proved its trace.
_PROCESS_CONTROL = None


class QueueControlError(RuntimeError):
    """The queue has no readable run-level control. Raised, never
    warned: the trace observations are unreadable in both directions."""


def begin_traced_queue(queue_name, trace_path, ledger,
                       declaration_identity):
    """The queue's first act, before frame one. Raises on any failure.

    A159: the governing declaration's identity is part of the
    first-act stamp, so declared-before is STRUCTURAL for every queue
    rather than inferred from commit ordering — the standing limit
    (committed evidence orders declaration-commit against
    results-commit but cannot time the renders) is closed forward."""
    global _PROCESS_CONTROL
    if not declaration_identity:
        raise QueueControlError(
            "no governing declaration identity — a queue whose spend "
            "declaration cannot be named in its first act is not "
            "declared-before in any checkable sense; refusing")
    abs_path = os.path.abspath(trace_path)
    os.environ[FT.TRACE_PATH_ENV] = abs_path
    record = FT.log_firing(CONTROL_SITE, queue_name,
                           {"branch": "deliberate_first_act_control"},
                           "CONTROL_NO_VALUE_SUBSTITUTED")
    with open(abs_path) as f:
        lines = [json.loads(line) for line in f if line.strip()]
    landed = [r for r in lines
              if r["site"] == CONTROL_SITE and r["ts"] == record["ts"]]
    if not landed:
        raise QueueControlError(
            "control firing did not land in the trace file it was "
            "written to — the trace is not live; refusing to render")
    stamp = {"control_site": CONTROL_SITE, "queue": queue_name,
             "trace_path": abs_path, "ts": record["ts"],
             "declaration_identity": declaration_identity}
    if LEDGER_KEY not in ledger:
        ledger[LEDGER_KEY] = []
    ledger[LEDGER_KEY].append(stamp)
    _PROCESS_CONTROL = stamp
    return stamp


def assert_process_controlled(ledger):
    """Writer-side guard for the runner's save path: frames may not be
    recorded by a process that has not emitted a stamped control."""
    if _PROCESS_CONTROL is None:
        raise QueueControlError(
            "this process emitted no first-act control — frames from "
            "it may not be recorded")
    if LEDGER_KEY not in ledger:
        raise QueueControlError(
            "ledger carries no control stamps — frames may not be "
            "recorded against it")
    if _PROCESS_CONTROL not in ledger[LEDGER_KEY]:
        raise QueueControlError(
            "this process's control stamp is not in the ledger — "
            "frames may not be recorded against it")


def read_trace_evidence(ledger, trace_path):
    """The only sanctioned way to cite a queue's trace as evidence.

    Returns the non-control firing records (empty list == zero
    firings, readable as zero ONLY because the controls prove the
    trace was live). Raises QueueControlError otherwise.
    """
    if LEDGER_KEY not in ledger:
        raise QueueControlError(
            "queue ledger carries no first-act control stamp — its "
            "trace observations are unreadable in both directions "
            "and it is not trace evidence")
    stamps = ledger[LEDGER_KEY]
    if not stamps:
        raise QueueControlError(
            "queue ledger's control stamp list is empty — its trace "
            "observations are unreadable in both directions and it "
            "is not trace evidence")
    for stamp in stamps:
        for key in ("control_site", "queue", "trace_path", "ts"):
            if key not in stamp:
                raise QueueControlError(
                    f"control stamp is missing '{key}' — the record "
                    "did not travel intact; unreadable")
    if not os.path.exists(trace_path):
        raise QueueControlError(
            "ledger stamps a control but the trace file is absent — "
            "the record did not travel with the ledger; unreadable")
    with open(trace_path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records:
        raise QueueControlError(
            "ledger stamps a control but the trace file is empty — "
            "the control record did not travel; unreadable")
    first = records[0]
    if first["site"] != CONTROL_SITE or first["ts"] != stamps[0]["ts"]:
        raise QueueControlError(
            "the trace's first record is not the ledger's first "
            "stamped control — the control was not the queue's first "
            "act; unreadable")
    stamped = {(s["control_site"], s["ts"]) for s in stamps}
    for stamp in stamps:
        hits = [r for r in records
                if r["site"] == stamp["control_site"]
                and r["ts"] == stamp["ts"]]
        if not hits:
            raise QueueControlError(
                "a stamped control is absent from the trace file — "
                "that process's liveness is unproven; unreadable")
    return [r for r in records
            if (r["site"], r["ts"]) not in stamped]
