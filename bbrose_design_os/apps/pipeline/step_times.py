"""What a working design is doing now, and roughly how long that takes — measured, never assumed.

[His goal of 2026-10-06, item 2 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a9ac953): "While it works, it shows clearly
what step it's on and roughly how long."] Each step a design works through in the background is named here by the log
line that opens it and the one that ends it — the lines the pipeline already writes (agents/aria.py,
services/trend_board.py). "Roughly how long" is the median of that step's own durations on this site's designs: every
opening line followed in the same design by its ending line, with no pause for a person between (a step that waited on
him is not a step's time). A step with fewer than ``MIN_MEASURED`` measurements says it is not measured yet.
"""
from __future__ import annotations

import re
import statistics

#: (key, words, the line that opens it, the line that ends it, unused)
STEPS = (
    ("trends", "Finding current trend pictures on the web",
     r"^ARIA: searching the web for current trends",
     r"^ARIA: (\d+ trend picture\(s\) (found and ticked|used)|no trend|no trend picture)", None),
    ("plan", "Making three design directions",
     r"^ARIA: planning design directions",
     r"^ARIA: (three design directions (ready|planned and validated)|reached Gate 1)", None),
    ("draw", "Drawing one concept picture for each direction",
     r"^ARIA: (three design directions planned and validated|rendering three variations|drawing one picture for each "
     r"direction|drawing the three directions again|reference-grounded (Gate-1 )?regeneration of)",
     r"^ARIA: (reached Gate 1|rerun complete|reference-grounded regeneration complete)", None),
    # [his test blocker on design 122, 2026-10-07, item 2] each concept checked — and redrawn where it must be — before
    # it is shown
    ("check", "Checking each concept can be drawn before it is shown",
     r"^ARIA: (checking each concept can be drawn|redrawing '.+' so it can be drawn, as you asked)",
     r"^ARIA: (each concept checked|back at Gate 1 — the concept you asked to be redrawn)", None),
    ("read", "Reading the chosen concept and proposing its size or shape",
     r"^ARIA: Gate 1 approved",
     r"^ARIA: reached (dimension gate|container-profile gate|Gate 2)", None),
    ("compose", "Drawing the design",
     r"^ARIA: (container profile confirmed|dimensions confirmed)",
     r"^ARIA: (reached Gate 2|dieline ready)", None),
)
#: a working status no step's line has opened yet: what it is doing, in words (its time is not measured — the files
#: are saved in the moment after Gate 2 and no line opens that step)
UNOPENED = {"queued": "Starting", "gate_2_approved": "Preparing the finished files"}
WORDS = {key: words for key, words, *_ in STEPS}
#: the planned directions and their pictures are one step now (his final goal, B4: no step of his between them)
CONCEPTS = ("plan", "draw")
CONCEPTS_WORDS = "Making three design directions and drawing one concept picture for each"
MIN_MEASURED = 3
#: the latest measurements of a step only — the pipeline of today, not of July (a drawing now builds the native file)
LATEST = 15
#: the longest a step is taken to have run — a pair further apart than this waited on something
MAX_SECONDS = 3600
_CACHE_KEY = "step_times/1.0"
_CACHE_SECONDS = 600


def _measure() -> dict:
    """``{key: (median seconds, how many)}`` over every design on record."""
    from apps.pipeline.models import AgentLog
    opens = {key: re.compile(o) for key, _w, o, _e, _p in STEPS}
    ends = {key: re.compile(e) for key, _w, _o, e, _p in STEPS}
    durations = {key: [] for key, *_ in STEPS}          # (when it ended, seconds), sorted by when below
    started: dict = {}
    rows = AgentLog.objects.filter(action__startswith="ARIA: ").order_by("task_id", "timestamp", "id").values_list(
        "task_id", "timestamp", "action")
    last_task = None
    for task_id, at, action in rows.iterator():
        if task_id != last_task:
            started, last_task = {}, task_id
        for key in durations:
            if key in started and ends[key].search(action):
                seconds = (at - started.pop(key)).total_seconds()
                if 0 <= seconds <= MAX_SECONDS:
                    durations[key].append((at, seconds))
        for key in durations:
            if opens[key].search(action):
                started[key] = at
    latest = {key: [sec for _at, sec in sorted(d)[-LATEST:]] for key, d in durations.items()}
    return {key: (statistics.median(d), len(d)) for key, d in latest.items() if len(d) >= MIN_MEASURED}


def typical() -> dict:
    """The measured steps, cached for ten minutes."""
    from django.core.cache import cache
    found = cache.get(_CACHE_KEY)
    if found is None:
        found = _measure()
        cache.set(_CACHE_KEY, found, _CACHE_SECONDS)
    return found


def last_step_words(task) -> str:
    """[His test findings on design 121, 2026-10-07, item 3] the step a design was on when it stopped, in words — the
    latest step its log opened and did not end — or "" when no step opened."""
    if task is None or getattr(task, "pk", None) is None:
        return ""
    opens = [(key, re.compile(o), re.compile(e)) for key, _w, o, e, _p in STEPS]
    current = None
    for action in task.logs.filter(action__startswith="ARIA: ").order_by("timestamp", "id").values_list(
            "action", flat=True):
        if current is not None and dict((k, e) for k, _o, e in opens)[current].search(action):
            current = None
        for key, o, _e in opens:
            if o.search(action):
                current = key
    return WORDS.get(current, "") if current else ""


#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010).] a working
#: design has stopped moving when its log has been quiet this many times its step's measured time (the longest measured
#: step's, where its own is not measured yet): 14 s into its step, 123's Garden Wrap was offered "Not moving? Resume",
#: and the resume ran the step again beside the one still working — its map read twice, the second read refused
STALLED_TIMES = 2.0
#: … and, where no step has been measured on this system yet (a fresh one, the suite's own), this many seconds — said
#: as the one figure not measured
STALLED_UNMEASURED_SECONDS = 180.0
#: [his goal of 2026-10-13, (3): "no progress for well past its usual time"] and never sooner than this after its last
#: line, however short its step measures — a step measured at a few seconds offered Resume the moment it went quiet
STALLED_LEAST_SECONDS = 120.0


#: the working states a design can stop moving in — each resumes from its own step (``TaskRetryView.RETRYABLE``)
MOVING = ("gate_1_approved", "generating_dieline", "gate_2_approved")
#: the hold before any concept is drawn: it has stopped only once everything it waits for exists and it has not gone on
HELD = "awaiting_gate1_generation_configuration"


def stalled(task) -> bool:
    """[His goal of 2026-10-13, (3).] Whether a design has truly stopped, for every state: a working design whose log has
    been quiet ``STALLED_TIMES`` its step's measured time (True for one whose log holds no line), a held design whose
    prerequisites all exist; False while it works, waits for him, is finished or failed (a failed design says why, with
    its own way on)."""
    if task.status == HELD:
        from apps.pipeline.services import gate1_checkpoint as ckpt
        ready, _missing = ckpt.generation_prerequisites(task)
        return bool(ready)
    if task.status not in MOVING:
        return False
    from django.utils import timezone
    last = task.logs.order_by("-timestamp", "-id").values_list("timestamp", flat=True).first()
    if last is None:
        return True
    step = working_step(task) or {}
    measured = typical()
    seconds = step.get("typical_seconds") or max((v[0] for v in measured.values()), default=STALLED_UNMEASURED_SECONDS)
    return (timezone.now() - last).total_seconds() > max(STALLED_TIMES * float(seconds), STALLED_LEAST_SECONDS)


def working_step(task) -> dict | None:
    """The step a working design is on: ``{key, words, started_at, typical_seconds, measured_on}`` — the latest step
    its log opened and has not ended; while its directions and their pictures are made, the two together, their
    medians added. None for a design not working, or one whose step has not opened a line yet."""
    from apps.pipeline.live_views import WORKING_STATUSES
    if task.status not in WORKING_STATUSES or task.status == "awaiting_trend_review":
        return None
    opens = [(key, re.compile(o), re.compile(e)) for key, _w, o, e, _p in STEPS]
    current, started_at = None, None
    for at, action in task.logs.filter(action__startswith="ARIA: ").order_by("timestamp", "id").values_list(
            "timestamp", "action"):
        if current is not None and dict((k, e) for k, _o, e in opens)[current].search(action):
            current, started_at = None, None
        for key, o, _e in opens:
            if o.search(action):
                current, started_at = key, at
    if current is None:
        return {"key": "unopened", "words": UNOPENED.get(task.status, "Working"), "started_at": None,
                "typical_seconds": None, "measured_on": 0}
    measured = typical()
    words, keys = WORDS[current], (current,)
    if current == "plan":
        words, keys = CONCEPTS_WORDS, CONCEPTS
    if all(k in measured for k in keys):
        seconds = sum(measured[k][0] for k in keys)
        on = min(measured[k][1] for k in keys)
    else:
        seconds, on = None, 0
    return {"key": current, "words": words, "started_at": started_at.isoformat() if started_at else None,
            "typical_seconds": round(seconds) if seconds is not None else None, "measured_on": on}
