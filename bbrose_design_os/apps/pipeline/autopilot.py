"""THE PITCH RUN — [His goal after the pitch page, 2026-10-15, B (9)-(11)]: "Write 3 BRAND-NEW briefs ... Run each from
brief to final files with no manual fixes: pick the trend-led concept automatically. ... Report for each: total time
from Start to final files, cost, any stop or error ... Every page must be calm during the run: no stops, no pop-ups, the
page moving on by itself, one clear button per step."

A design started with ``DesignTask.options["autopilot"]`` takes every step that waits on a person by itself, exactly as
the step's one button takes it, through the SAME door the button posts to (``_door``: the view itself, as the task's own
starter) — never a re-implementation that could drift:

  * the trend pictures — pressed on as they are ticked (``trend_board.proceed``, the service the button's view calls,
    with the pitch run named as how, so the board never records his click);
  * the directions — the TREND-LED one (``creative_rules.role_at``);
  * Gate 1 — the concept drawn for the trend-led direction, its decision noted as the pitch run's own pick;
  * the shape — the proposal as the page opens it (``static/js/confirm_profile.js`` ``_openingSizes``, lines 64-82 and
    the variant and closure defaults at 128-143), its print areas confirmed as the page's ticks confirm them;
  * the size — the estimate as the page fills it (``static/js/gates.js`` ``showDimensionGate``/``submitDimensions``,
    lines 391-470 and 634-665: what was entered first, the board-thickness box ticked, inside as referenced, back on a
    sticker).

It STOPS at Gate 2: Gate 2 needs the owner's own recorded acceptance of the drawing, and the pitch run never records an
acceptance or approves Gate 2. The final files exist there already, so the run's clock stops there (``files_at``).

Every choice is said in the design's log in plain words and kept, with its time, in ``options["autopilot"]["steps"]``;
the log row's payload carries the same step (``STEP_KEY``) — the log is append-only, so it is the record a step is read
back from, and the options the copy the status page shows. A step is taken once for each visit of its status: a status
the run comes back to after taking it once (a concept that could not be drawn, a drawing that failed) is a STOP, said in
words, left for him. Every error is caught, said and kept as a stop — never raised into the pipeline.

Trigger: ``signals._autopilot_on_status_change`` → ``watch`` → on commit, the Celery task ``tasks.autopilot_step`` →
``drive``. While one ``drive`` is taking steps in this thread (an eager run's resume runs inside the door it posted),
``watch`` stands down and ``drive`` reads the status again after each step."""
from __future__ import annotations

import logging
import threading

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

#: the option's key on ``DesignTask.options``
OPTION = "autopilot"
#: the key a log row's payload carries the step under, and the files' time under
STEP_KEY = "autopilot_step"
FILES_KEY = "autopilot_files_at"
STOP_KEY = "autopilot_stop"
#: the statuses the pitch run takes by itself, as each one's button does
TAKEN = ("awaiting_trend_review", "awaiting_direction_selection", "awaiting_gate_1", "awaiting_container_profile",
         "awaiting_dimensions")
#: where the final files exist — the run's clock stops at the first of them
FILES = ("awaiting_gate_2", "completed")
#: where a design stopped
STOPPED = ("failed", "rejected", "container_stage_visually_rejected")
#: a wait no button of the pitch run takes — said as a stop, left for him
UNTAKEN = ("awaiting_gate1_generation_configuration", "awaiting_structure_confirmation",
           "awaiting_design_intent_confirmation")
#: the most steps one design's pitch run takes
MAX_STEPS = 12
#: the pause before a step is taken, so the stage that reached the wait has finished writing (a live worker only)
COUNTDOWN = 2
#: how long the page shows a step as being taken before the run has claimed it — past it (a worker that never ran the
#: step), the step's own form and its one button come back, so the page never waits on nothing
PATIENCE = 120
#: how the trend board records the press (``TrendBoard.confirmed_how``, at most 40 characters)
BY_THE_PITCH_RUN = "the pitch run, by itself"
#: what every pick is, said with it
NOT_HIS = "the pitch run's own pick, never the owner's approval"
#: the one line the page shows in place of a step's form while the run takes it
TAKING_WORDS = "The system is taking this step by itself…"

_here = threading.local()


class Stop(Exception):
    """A step the pitch run cannot take as its button would — its words are the stop's."""


# --- the option -----------------------------------------------------------------------------------------------------

def asked(value) -> bool:
    """Whether a Start request asks for the pitch run — sent as the page's form sends a tick ("true")."""
    return str(value).strip().lower() in ("true", "1", "on", "yes")


def new_record() -> dict:
    """The option as a design is started with it: on, its Start time, nothing taken yet."""
    return {"on": True, "started_at": timezone.now().isoformat(), "steps": [], "stops": [], "files_at": None}


def record_of(task) -> dict | None:
    """The design's pitch-run record, or None for a design started without it (``True`` reads as a fresh record)."""
    options = task.options if isinstance(task.options, dict) else {}
    value = options.get(OPTION)
    if value is True:
        return {"on": True, "steps": [], "stops": []}
    if isinstance(value, dict) and value.get("on") is not False:
        return value
    return None


def inherited(project, prev_task) -> dict:
    """[His goal after the pitch page, 2026-10-15, B (9)] a Complete Product's next stage is a pitch run when its project
    was started as one: a fresh record — its own clock and steps — for the stage, else nothing."""
    started_as_one = bool((project.metadata or {}).get(OPTION)) if project is not None else False
    if prev_task is not None and record_of(prev_task) is not None:
        started_as_one = True
    return {OPTION: new_record()} if started_as_one else {}


# --- the trigger ----------------------------------------------------------------------------------------------------

def watch(task) -> None:
    """Called on every status change: a pitch-run design at a status the run reads is handed to the worker once the
    change commits — unless a ``drive`` in this thread is taking its steps already (it reads the status again)."""
    if record_of(task) is None or getattr(_here, "driving", False):
        return
    status = task.status
    if status not in TAKEN + FILES + STOPPED + UNTAKEN:
        return
    seen_at = timezone.now().isoformat()
    task_id = task.pk

    def _enqueue():
        from apps.pipeline.tasks import autopilot_step
        autopilot_step.apply_async(args=(task_id, status, seen_at), countdown=COUNTDOWN)
    transaction.on_commit(_enqueue)


def drive(task_id: int, seen_at: str | None = None) -> None:
    """Take the design's waiting steps, one after another while each moves it on — at most ``MAX_STEPS``. Never
    raises: an error is said in the log and kept as a stop."""
    was = getattr(_here, "driving", False)
    _here.driving = True
    try:
        for n in range(MAX_STEPS + 1):
            if not _once(task_id, seen_at if n == 0 else None):
                return
    except Exception as exc:  # noqa: BLE001 — the pitch run never raises into the pipeline
        logger.exception("pitch run on design %s", task_id)
        _stop_safely(task_id, "", "the pitch run met an error and stopped taking steps: %s" % exc)
        return
    finally:
        _here.driving = was


# --- one step -------------------------------------------------------------------------------------------------------

def _once(task_id: int, seen_at: str | None) -> bool:
    """One look at the design: its files' time kept, a stop said, or one step taken. True when a step was taken and
    the design should be read again."""
    from apps.dashboard.words import status_words, stop_words
    from apps.pipeline.models import DesignTask

    task = DesignTask.objects.filter(pk=task_id).first()
    if task is None or record_of(task) is None:
        return False
    status = task.status
    if status in FILES:
        _files(task, seen_at)
        return False
    if status in STOPPED:
        _stop(task, status, "the design stopped (%s): %s" % (status_words(status), stop_words(task)))
        return False
    if status in UNTAKEN:
        _stop(task, status, "the design waits at \"%s\", a step the pitch run does not take — it is yours"
              % status_words(status))
        return False
    if status not in TAKEN:
        return False
    if task.created_by is None:
        _stop(task, status, "the design has no person who started it, so no step can be taken in their name")
        return False
    try:
        choice = CHOOSERS[status](task)
    except Stop as stop:
        _stop(task, status, str(stop))
        return False
    step = _claim(task, status, choice)
    if step is None:
        return False
    code, said = DOORS[status](task, task.created_by, choice)
    if 200 <= code < 300:
        return True
    if DesignTask.objects.filter(pk=task_id).exclude(status=status).exists():
        # refused because the design had moved on already — a person's click or the step taken by another trigger:
        # no stop, the run reads the design again
        return True
    _stop(task, status, "the pitch run's step at \"%s\" was refused (%d): %s" % (status_words(status), code, said))
    return False


def _steps(task) -> list:
    """The steps taken on the design, oldest first, from its log (append-only)."""
    from apps.pipeline.models import AgentLog
    rows = AgentLog.objects.filter(task=task, payload__has_key=STEP_KEY).order_by("pk").values_list("payload", flat=True)
    return [row[STEP_KEY] for row in rows]


def _version(task) -> str:
    from apps.pipeline.live_views import where_of
    return where_of(task)["version"]


def _claim(task, status: str, choice: dict) -> dict | None:
    """The step written down before its door is posted to — under the design's row lock, so two triggers of one visit
    take it once. None when this visit was taken already (nothing said), when the run comes back to a status it took
    (a stop, said) or when the run has taken its most steps (a stop, said)."""
    from apps.dashboard.words import status_words
    from apps.pipeline.models import AgentLog, DesignTask

    with transaction.atomic():
        locked = DesignTask.objects.select_for_update().get(pk=task.pk)
        if locked.status != status:
            return None
        version = _version(locked)
        taken = _steps(locked)
        if any(s["status"] == status and s["version"] == version for s in taken):
            return None
        if any(s["status"] == status for s in taken):
            _stop(locked, status, "the design came back to \"%s\" after the pitch run took that step once — it waits "
                  "for you there" % status_words(status))
            return None
        if len(taken) >= MAX_STEPS:
            _stop(locked, status, "the pitch run took its most steps (%d) and stopped" % MAX_STEPS)
            return None
        step = {"status": status, "at": timezone.now().isoformat(), "version": version, "words": choice["words"],
                "choice": {k: v for k, v in choice.items() if k != "words"}}
        AgentLog.objects.create(task=locked, agent_name="ARIA", action="Pitch run: %s" % choice["words"],
                                payload={STEP_KEY: step}, actor=locked.created_by)
        _write(locked, lambda record: record.setdefault("steps", []).append(step))
    return step


def _write(task, change) -> None:
    """The record changed on the design's options alone — never a full save, which would carry a stale status."""
    from apps.pipeline.models import DesignTask
    with transaction.atomic():
        locked = DesignTask.objects.select_for_update().get(pk=task.pk)
        options = dict(locked.options) if isinstance(locked.options, dict) else {}
        record = record_of(locked)
        if record is None:
            return
        record = dict(record)
        change(record)
        options[OPTION] = record
        DesignTask.objects.filter(pk=task.pk).update(options=options)


def _stop(task, status: str, words: str) -> None:
    """A stop said in the log and kept on the record — once for each status and words."""
    from apps.pipeline.models import AgentLog
    record = record_of(task)
    if record is None:
        return
    if AgentLog.objects.filter(task=task, payload__has_key=STOP_KEY, payload__autopilot_stop__status=status,
                               payload__autopilot_stop__words=words).exists():
        return
    stop = {"status": status, "at": timezone.now().isoformat(), "words": words}
    AgentLog.objects.create(task=task, agent_name="ARIA", level="warning", action="Pitch run stopped: %s" % words,
                            payload={STOP_KEY: stop})
    _write(task, lambda rec: rec.setdefault("stops", []).append(stop))


def _stop_safely(task_id: int, status: str, words: str) -> None:
    from apps.pipeline.models import DesignTask
    try:
        task = DesignTask.objects.filter(pk=task_id).first()
        if task is not None:
            _stop(task, status or task.status, words)
    except Exception:  # noqa: BLE001 — the last word of a run that met an error must never raise
        logger.exception("pitch run on design %s: its stop could not be kept", task_id)
        return


def _files(task, seen_at: str | None) -> None:
    """The final files' time, the first time the design reaches them — said with Start → final files."""
    from apps.pipeline.models import AgentLog
    record = record_of(task)
    if record is None or record.get("files_at") or \
            AgentLog.objects.filter(task=task, payload__has_key=FILES_KEY).exists():
        return
    at = seen_at if seen_at else timezone.now().isoformat()
    took = _between(record.get("started_at") or task.created_at.isoformat(), at)
    AgentLog.objects.create(
        task=task, agent_name="ARIA", payload={FILES_KEY: at},
        action="Pitch run: the final files are made — Start → final files: %s. It stops at Gate 2: the design waits "
               "there for the owner's own look and approval, which the pitch run never gives." % _words(took))
    _write(task, lambda rec: rec.update(files_at=at))


# --- what each step chooses, as its page shows it -------------------------------------------------------------------

def _trend_led(task) -> dict:
    """The design's trend-led direction (``creative_rules.role_at``)."""
    from apps.pipeline.creative_rules import role_at
    from apps.pipeline.models import CreativeBrief
    brief = CreativeBrief.objects.filter(task=task).first()
    directions = (brief.directions if brief is not None else None) or []
    for i, direction in enumerate(directions):
        if isinstance(direction, dict) and role_at(i, direction) == "TREND-LED":
            return direction
    raise Stop("the design has no trend-led direction to choose")


def choose_trends(task) -> dict:
    return {"words": "the system pressed on with the trend pictures as they are ticked, by itself — %s" % NOT_HIS}


def choose_direction(task) -> dict:
    direction = _trend_led(task)
    name = str(direction.get("name") or "")
    return {"direction_id": direction.get("direction_id"), "name": name,
            "words": "the system chose the trend-led direction, \"%s\", by itself — %s" % (name, NOT_HIS)}


def choose_concept(task) -> dict:
    from apps.pipeline.services.gate1_review import image_is_selectable
    direction = _trend_led(task)
    name = str(direction.get("name") or "")
    current = [i for i in task.images.filter(superseded=False).order_by("pk") if image_is_selectable(i)]
    picked = [i for i in current if direction.get("direction_id") and i.direction_id == direction.get("direction_id")]
    if not picked:
        picked = [i for i in current if name and i.direction_name == name]
    if not picked:
        # [his goal after the pitch page, B (11): "no stops ... the page moving on by itself"] the trend-led concept not
        # there to choose (refused by its check before it was shown): the next of the design's directions in their
        # order — bold, then minimal — that has one, said so; a stop only where none can be chosen
        from apps.pipeline.models import CreativeBrief
        brief = CreativeBrief.objects.filter(task=task).first()
        order = [d.get("direction_id") for d in ((brief.directions if brief is not None else None) or [])
                 if isinstance(d, dict)]
        ranked = sorted(current, key=lambda i: order.index(i.direction_id) if i.direction_id in order else len(order))
        if not ranked:
            raise Stop("no concept of the trend-led direction, \"%s\", can be chosen at Gate 1 — the concepts wait "
                       "for you" % name)
        image = ranked[0]
        return {"image_id": image.pk, "direction_name": image.direction_name,
                "words": "the trend-led concept, \"%s\", was not there to choose, so the system chose the next "
                         "direction's, \"%s\", by itself — %s" % (name, image.direction_name, NOT_HIS)}
    image = picked[0]
    return {"image_id": image.pk, "direction_name": image.direction_name,
            "words": "the system chose the trend-led concept, \"%s\", by itself — %s" % (image.direction_name, NOT_HIS)}


def _range_of(form: dict, rows: list, key: str) -> tuple:
    own = (form.get("ranges") or {}).get(key) or {}
    row = next((r for r in rows if r.get("key") == key), {})
    low = own["min"] if "min" in own else row.get("min")
    high = own["max"] if "max" in own else row.get("max")
    return low, high


def choose_profile(task) -> dict:
    """The shape as the page opens its editor (confirm_profile.js 64-143): the proposed form, its variant and closure,
    each size the proposal's, else the brief's where it lies inside the form's limits, else the form's own starting
    size; a neck only where the form has one."""
    from apps.pipeline.targets.ui import container_profile_editor_config
    editor = container_profile_editor_config(task)
    proposed = editor.get("proposed") or {}
    archetype = proposed.get("archetype")
    form = next((a for a in editor.get("archetypes") or [] if a.get("key") == archetype), None)
    if not archetype or form is None:
        raise Stop("the shape step proposes no form — the shape waits for you")
    given = proposed.get("proportions") or {}
    brief = editor.get("brief_sizes") or {}
    nominal = form.get("nominal") or {}
    rows = editor.get("proportions") or []
    profile = {"archetype": archetype}
    variants = [v["key"] for v in form.get("variants") or []]
    caps = [c["key"] for c in form.get("caps") or []]
    variant = proposed.get("variant")
    if not variant and variants and not editor.get("unknown_shape"):
        variant = variants[0]
    cap = proposed.get("cap_style")
    if not cap and caps:
        cap = caps[0]
    if variant:
        profile["variant"] = variant
    if cap:
        profile["cap_style"] = cap
    for key in ("height_mm", "width_mm", "depth_mm"):
        low, high = _range_of(form, rows, key)
        said = brief.get(key)
        in_range = isinstance(said, (int, float)) and low is not None and high is not None and low <= said <= high
        value = given.get(key)
        if value is None and in_range:
            value = said
        if value is None:
            value = nominal.get(key)
        if value is not None:
            profile[key] = value
    if variant in ("round", "cushion") and archetype in ("compact", "tin") and profile.get("width_mm") is not None:
        # [his goal after the pitch page, B (11); the third brand-new brief, 137: its round compact confirmed at the
        # form's 110 x 95, refused by the shape step] a round lid is as long as it is wide, as the page's editor sets it
        profile["height_mm"] = profile["width_mm"]
    if "neck_ratio" in (form.get("proportions") or []):
        neck = given.get("neck_ratio")
        if neck is None:
            neck = nominal.get("neck_ratio")
        if neck is not None:
            profile["neck_ratio"] = neck
    return {"profile": profile,
            "words": "the system confirmed the proposed shape (%s) and its print areas, by itself — %s"
                     % (form.get("label") or archetype, NOT_HIS)}


def choose_dimensions(task) -> dict:
    """The size as the page fills it (gates.js 391-470, 634-665): what was entered first, else the estimate; the
    board-thickness box as entered, else ticked; inside as referenced and the back on a sticker, the page's own
    defaults. A size the page asks by hand, or a structure it asks him to choose, is his."""
    output = task.current_output()
    spec = (output.spec_sheet if output is not None else None) or {}
    estimate = spec.get("estimated_dimensions") or {}
    entered = spec.get("entered_dimensions") or (spec.get("size_confirmed") or {}).get("dims") or {}
    if (spec.get("structural_selection") or {}).get("candidates"):
        raise Stop("the size step asks for the carton's structure to be chosen — that choice is yours")
    dims = {}
    for key in ("width_mm", "depth_mm", "height_mm"):
        field = estimate.get(key) or {}
        value = entered.get(key)
        if value is None:
            value = field.get("value")
        if value is None or value == "":
            raise Stop("the size step has no %s to confirm — it needs a value by hand" % key.replace("_mm", ""))
        dims[key] = float(value)
    dims["thickness_compensation"] = entered["thickness_compensation"] if "thickness_compensation" in entered \
        else True
    return {"dimensions": dims, "inside_print": "referenced", "back_info": "sticker",
            "words": "the system confirmed the proposed size, %g × %g × %g mm, by itself — %s"
                     % (dims["width_mm"], dims["depth_mm"], dims["height_mm"], NOT_HIS)}


CHOOSERS = {"awaiting_trend_review": choose_trends, "awaiting_direction_selection": choose_direction,
            "awaiting_gate_1": choose_concept, "awaiting_container_profile": choose_profile,
            "awaiting_dimensions": choose_dimensions}


# --- the doors the buttons post to ----------------------------------------------------------------------------------

def _host() -> str:
    from django.conf import settings
    named = [h for h in settings.ALLOWED_HOSTS if h and "*" not in h and not h.startswith(".")]
    return named[0] if named else "localhost"


def _door(view_class, task, user, body: dict) -> tuple:
    """The view a button posts to, posted to as the design's own starter: (status code, the answer's words)."""
    from rest_framework.test import APIRequestFactory, force_authenticate
    request = APIRequestFactory().post("/api/tasks/%d/" % task.pk, body, format="json", HTTP_HOST=_host())
    force_authenticate(request, user=user)
    response = view_class.as_view()(request, task_id=task.pk)
    return response.status_code, response.data


def _said(data) -> str:
    if not isinstance(data, dict):
        return str(data)[:400]
    for key in ("words", "reason", "error", "detail", "message"):
        if data.get(key):
            return str(data[key])[:400]
    return str(data)[:400]


def take_trends(task, user, choice) -> tuple:
    # the service TrendContinueView calls, named as the pitch run's — the button's view names his click
    from apps.pipeline.services import trend_board
    from apps.pipeline.models import DesignTask
    if trend_board.proceed(task.pk, BY_THE_PITCH_RUN, user):
        return 200, "queued"
    if DesignTask.objects.filter(pk=task.pk).exclude(status="awaiting_trend_review").exists():
        return 200, "the review window closed first — the directions are being made with the pictures as ticked"
    return 409, "the trend board could not be pressed on"


def take_direction(task, user, choice) -> tuple:
    from apps.pipeline.views import SelectDirectionView
    code, data = _door(SelectDirectionView, task, user, {"direction_id": choice["direction_id"]})
    return code, _said(data)


def take_concept(task, user, choice) -> tuple:
    from apps.pipeline.views import Gate1ApproveView
    code, data = _door(Gate1ApproveView, task, user, {"image_id": choice["image_id"], "notes": NOT_HIS})
    return code, _said(data)


def take_profile(task, user, choice) -> tuple:
    """The shape confirmed; print areas handed back with a refusal confirmed as the page's ticks confirm them, and sent
    again — at most twice."""
    from apps.pipeline.views import ConfirmContainerProfileView
    body = {"profile": choice["profile"]}
    code, data = _door(ConfirmContainerProfileView, task, user, body)
    for _again in range(2):
        if code != 409 or not isinstance(data, dict) or not data.get("zones"):
            break
        zones = [dict(z, user_confirmation_state="USER_CONFIRMED") for z in data["zones"]]
        code, data = _door(ConfirmContainerProfileView, task, user, dict(body, zones=zones))
    return code, _said(data)


def take_dimensions(task, user, choice) -> tuple:
    from apps.pipeline.views import ConfirmDimensionsView
    code, data = _door(ConfirmDimensionsView, task, user, {k: v for k, v in choice.items() if k != "words"})
    return code, _said(data)


DOORS = {"awaiting_trend_review": take_trends, "awaiting_direction_selection": take_direction,
         "awaiting_gate_1": take_concept, "awaiting_container_profile": take_profile,
         "awaiting_dimensions": take_dimensions}


# --- what the page is told ------------------------------------------------------------------------------------------

def _between(start: str, end: str) -> float:
    from django.utils.dateparse import parse_datetime
    first, last = parse_datetime(start), parse_datetime(end)
    if first is None or last is None:
        return 0.0
    return max(0.0, (last - first).total_seconds())


def _words(seconds: float) -> str:
    whole = int(round(seconds))
    minutes, rest = divmod(whole, 60)
    return "%d min %d s" % (minutes, rest) if minutes else "%d s" % rest


def status_payload(task) -> dict | None:
    """The pitch run as the status page reads it — None for a design started without it: its steps and stops (from
    the log, which is never overwritten), its Start and files times and Start → final files in words, and whether the
    system is taking the step the design waits at (the page then shows ``TAKING_WORDS`` in place of its form)."""
    from apps.dashboard.words import stop_words
    from apps.pipeline.models import AgentLog
    record = record_of(task)
    if record is None:
        return None
    started = record.get("started_at") or task.created_at.isoformat()
    files_at = record.get("files_at")
    if not files_at:
        files_at = (AgentLog.objects.filter(task=task, payload__has_key=FILES_KEY).order_by("pk")
                    .values_list("payload", flat=True).first() or {}).get(FILES_KEY)
    steps = _steps(task)
    stops = [row[STOP_KEY] for row in AgentLog.objects.filter(task=task, payload__has_key=STOP_KEY).order_by("pk")
             .values_list("payload", flat=True)]
    if task.status == "failed" and not any(s["status"] == "failed" for s in stops):
        stops.append({"status": "failed", "at": task.updated_at.isoformat(), "words": stop_words(task)})
    took = _between(started, files_at) if files_at else None
    version = _version(task)
    claimed = any(s["status"] == task.status and s["version"] == version for s in steps)
    waited = (timezone.now() - task.updated_at).total_seconds()
    taking = (task.status in TAKEN and len(steps) < MAX_STEPS
              and not any(s["status"] == task.status for s in stops)
              and not any(s["status"] == task.status and s["version"] != version for s in steps)
              and (claimed or waited < PATIENCE))
    project = _project_clock(task)
    return {"on": True, "started_at": started, "files_at": files_at, "steps": steps, "stops": stops,
            "project": project,
            "start_to_files_seconds": took,
            "start_to_files_words": ("Start → final files: %s" % _words(took)) if took is not None else "",
            "taking": taking, "taking_words": TAKING_WORDS if taking else ""}


def _project_clock(task) -> dict | None:
    """[B (10)] a Complete Product's brief timed whole: its first stage's Start → its last stage's final files, with
    the time its earlier stages waited at Gate 2 for the owner said apart (each stage keeps its own clock above); None
    for a design of no project, or a project not started as a pitch run."""
    from apps.pipeline.models import AgentLog, DesignTask
    if not task.project_id:
        return None
    stages = list(DesignTask.objects.filter(project_id=task.project_id).order_by("pk"))
    records = [(stage, record_of(stage)) for stage in stages]
    if any(record is None for _stage, record in records):
        return None
    started = records[0][1].get("started_at") or stages[0].created_at.isoformat()
    ends = []
    for stage, record in records:
        end = record.get("files_at") or (AgentLog.objects.filter(task=stage, payload__has_key=FILES_KEY)
                                         .order_by("pk").values_list("payload", flat=True).first() or {}).get(FILES_KEY)
        ends.append(end)
    waited = 0.0
    for (stage, record), end in zip(records[1:], ends[:-1]):
        if end and record.get("started_at"):
            waited += _between(end, record["started_at"])
    last = ends[-1]
    whole = _between(started, last) if last else None
    return {"stages": len(stages), "started_at": started, "files_at": last, "start_to_files_seconds": whole,
            "owner_gate_2_seconds": waited,
            "start_to_files_words": ("Start → final files of every stage: %s, of which %s waited at Gate 2 for the "
                                     "owner" % (_words(whole), _words(waited))) if whole is not None else ""}
