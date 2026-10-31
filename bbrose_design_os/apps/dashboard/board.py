"""THE BOARD — where every design stands, read ONCE for every screen (the owner's answer to the UI directions, 2026-09-25).

His goal (OWNER_BLOCKER_CLEARANCE.md, "OWNER GOAL — THE UI, DESIGNED THIS TIME", (d)): "What is running, what is waiting
for me, and what failed are always visible." His pick: B's board — the six steps as columns, the "Needs attention" lane on
top — with the three counts in the top bar of every page. His fold: "Yes, fold away the old acceptance walkthroughs (tasks
53–57) and the demo carton, along with your planning tests. They are tests, not my work, and they should not count as
"waiting for me"."

ONE classification — each design's step, what it waits on and in which words, whether it is folded away, and the three
counts — read by the top bar, the board, Status and Designs, so no two screens can disagree. It reads rows and writes
nothing: no save, no create, no AgentLog, no file.

What each count means, measured and not assumed:
- WORKING ON IT: the machine is working on the design now — a working status whose last sign of life (its own last save,
  or its last log row) is younger than the worker's hard time limit, `CELERY_TASK_TIME_LIMIT` (settings: 1800 s). No step
  of the worker runs longer than that limit: the worker kills it there.
- STOPPED MOVING, counted under NEEDS ATTENTION: a working status silent for longer than that limit. Measured on
  2026-09-25: tasks 12, 13 and 14 were queued on 28 May and carry no log row at all — they never started.
- WAITING FOR YOU: a status where the next act is a person's on this site.
- NEEDS ATTENTION: a design that stopped (failed or rejected) with no later try of the same design that went on, a design
  rejected at review and not redrawn since, and a design that stopped moving.
- A stopped try with a LATER try of the same design that went on is not hidden and not counted twice: it is listed under
  its later try ("tried again") on the board and on Status, with its own reason.
- CAN'T MOVE ON HERE: a design at a step no view or worker on this site moves it from — listed in its column with why,
  never counted as waiting for him.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import timezone

from apps.dashboard.words import status_words, target_words

#: the six steps, in the order a design meets them (B's board; the step bar on a design reads the same order)
LANES = (
    ("describe", "Describe"),
    ("direction", "Choose a direction"),
    ("concept", "Choose a concept"),
    ("size", "Confirm the size"),
    ("review", "Review the design"),
    ("finished", "Finished"),
)
LANE_WORDS = dict(LANES)

WORKING = "working"
WAITING = "waiting"
ATTENTION = "attention"
STUCK = "stuck"
FINISHED = "finished"
TRIED_AGAIN = "tried_again"
FOLDED = "folded"

#: what each state is called on screen — the top bar's three pills use the first three
STATE_WORDS = {WORKING: "Working on it", WAITING: "Waiting for you", ATTENTION: "Needs attention",
               STUCK: "Can't move on here", FINISHED: "Finished", TRIED_AGAIN: "Stopped — tried again",
               FOLDED: "Folded away"}

#: the statuses the machine works in (apps/dashboard/status.py WORKING, the one list)
MACHINE = ("queued", "running", "awaiting_trend_review", "gate_1_approved", "generating_dieline", "gate_2_approved")
STOPPED = ("failed", "rejected")

# status -> (step, state, what the card says happens next). A status the map does not know is shown in its own words
# (status_words), in the Describe column, as waiting — never hidden (words.py's rule).
_STEP = {
    "awaiting_direction_selection": ("direction", WAITING, "Choose a direction"),
    # §BH71 PART 2: the machine moves it on when the review window closes — working, and watched for a stall like the
    # other working steps (MACHINE, status.WORKING)
    "awaiting_trend_review": ("describe", WORKING, "Trend pictures found — untick any you dislike before the "
                                                   "directions"),
    "awaiting_design_intent_confirmation": ("direction", WAITING, "Confirm what the palette should be"),
    "awaiting_gate1_generation_configuration": ("concept", WAITING, "Set up the concept pictures"),
    "awaiting_gate_1": ("concept", WAITING, "Choose a concept"),
    "awaiting_dimensions": ("size", WAITING, "Confirm the size"),
    "awaiting_container_profile": ("size", WAITING, "Confirm the shape and size"),
    # [the clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow"] the structure step is gone: a design
    # recorded at it (task 50) stays on record and readable; nothing on this site moves it, never counted as waiting
    "awaiting_structure_confirmation": ("size", STUCK, "Paused at a structure check this site no longer runs — "
                                                       "nothing waits on you"),
    "awaiting_gate_2": ("review", WAITING, "Review the design"),
    "gate_1_approved": ("size", WORKING, "Getting the size ready"),
    "generating_dieline": ("review", WORKING, "Laying out the design"),
    "gate_2_approved": ("finished", WORKING, "Approved — preparing the files"),
    "completed": ("finished", FINISHED, "Finished — the files are ready"),
    # MEASURED 2026-09-25 (grep of apps/ at c50abc7): palette_confirmation_flow.py:98 sets it, and no view, task or
    # agent reads it as the status to move a design on from — so it is a step this site cannot move a design past
    "design_intent_confirmed": ("direction", STUCK, "Its design intent is confirmed — nothing on this site moves it "
                                                    "further yet"),
}

#: THE OWNER'S FOLD, by task, in his words (2026-09-25): "fold away the old acceptance walkthroughs (tasks 53–57) and
#: the demo carton ... They are tests, not my work". Task 17 is the one design whose brief is headed "[DEMO]" (a carton).
HIS_FOLD = {53: "acceptance walkthrough", 54: "acceptance walkthrough", 55: "acceptance walkthrough",
            56: "acceptance walkthrough", 57: "acceptance walkthrough", 17: "demo carton"}
#: the fold as it is read — his, by task number, which is his database's own numbering; a test database numbers its
#: designs as it creates them, so a test that is not about the fold empties this one (never HIS_FOLD)
#: [His word after the fix for design 118, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 1dea9c5): "Fold 118 away as
#: a test."] design 118, his Rose Glaze Lip Gloss started as Packaging where he meant a Complete Product
HIS_FOLD_2026_10_03 = {118: "test"}
#: [His goal of 2026-10-06, item 4 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a9ac953): "Fold design 120 away as a
#: test."] design 120, his Rose Rebel Hand Cream, his test that stopped on its blockers (items 1–3)
HIS_FOLD_2026_10_06 = {120: "test"}
#: [His word after the fixes for design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md): "Fold 121 away as a test."] design 121,
#: his Rose Blossom Hand Cream, his test that stopped at its concept step (his test findings on design 121)
HIS_FOLD_2026_10_07 = {121: "test"}
OWNER_FOLD = {**HIS_FOLD, **HIS_FOLD_2026_10_03, **HIS_FOLD_2026_10_06, **HIS_FOLD_2026_10_07}
OWNER_FOLD_WORDS = ("Yes, fold away the old acceptance walkthroughs (tasks 53–57) and the demo carton, along with your "
                    "planning tests. They are tests, not my work, and they should not count as \"waiting for me\".")
#: ...and "your planning tests": the executor's planning probes, each marked on its project when it was made
PROBE_MARKERS = ("bh68_planning_probe", "planning_probe")
FOLD_GROUP_WORDS = {"planning test": "System planning tests", "acceptance walkthrough": "Acceptance walkthroughs",
                    "test": "Your tests",
                    "demo carton": "Demo carton", "publication record": "Read-only publication records"}
# [the owner, 2026-10-29, round 4: "The top bar shows 'Needs attention 2'. Tell me what those two are and fix them."]
# A read-only master publication's record (options "publication_only": task 158, HAYAT, made 25 Oct by the page
# now in archive/) is queued by construction and never meant to run, so it is history, not a stalled design.
PUBLICATION_ONLY_OPTION = "publication_only"
# [his last goal before the pitch, 2026-10-16, Step 1 (4): "Board: fold every design older than 7 days or started by the
# executor as a test into "Your tests"; Needs attention and Waiting show only live work."]
#: how long a design stays live work on the board without a sign of life (its own last save, or its last log row)
LIVE_DAYS = 7
#: the executor's own test of a design, as its record marks it: ``DesignTask.options["test_run"]`` — written only where
#: the executor makes or continues a design himself (his goal of 2026-10-13, (11); his goal for the pitch, C (11): "the
#: executor's showcase run"), never by the New design form. MEASURED on his database, 2026-10-16: tasks 126–131.
TEST_RUN_OPTION = "test_run"
#: the pitch run (``options["autopilot"]``) is a tick the New design form offers HIM, so it alone never marks a test.
#: MEASURED on his database, 2026-10-16: every pitch run on record — tasks 133–141, the executor's three unaided briefs
#: run three times each (his goal after the pitch page, B (9): "Write 3 BRAND-NEW briefs ... Run each") — was started
#: before 06:00 UTC that day, and none by him; a pitch run started after it is his live work and stays on the board.
PITCH_RUN_TESTS_BEFORE = datetime.datetime(2026, 10, 16, 6, 0, tzinfo=datetime.timezone.utc)
#: the pitch run's key on a task's options — apps/pipeline/autopilot.py's OPTION, named here (the owner's goal of
#: 2026-10-29, §0) so that reading a fold never imports the old pipeline: the Library's products, Home and Designs
#: reach the board's fold without loading autopilot, the old task API and the ARIA agent behind it
AUTOPILOT_OPTION = "autopilot"


def stall_seconds() -> int:
    """How long a working design may be silent before it has stopped: the worker's hard time limit, which kills any
    step that runs longer (config/settings.py CELERY_TASK_TIME_LIMIT)."""
    return int(getattr(settings, "CELERY_TASK_TIME_LIMIT", 1800) or 1800)


@dataclass
class Card:
    """One design on the board."""
    task_id: int
    status: str
    target: str
    product_id: int | None
    lane: str
    state: str
    next_words: str
    title: str
    what: str
    product_name: str
    product_name_ar: str
    brief_start: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    last_sign: datetime.datetime
    reason: str = ""
    fold: str = ""
    later_try: int | None = None
    earlier_stops: list = field(default_factory=list)
    #: where it stands with its fold set aside — its own page says that, never "Folded away" (Step 1 (4))
    unfolded_state: str = ""

    @property
    def lane_words(self) -> str:
        return LANE_WORDS.get(self.lane, "")

    @property
    def state_words(self) -> str:
        return STATE_WORDS.get(self.state, "")

    @property
    def url(self) -> str:
        return "/dashboard/designs/%d/" % self.task_id


def _first_line(text: str, limit: int = 60) -> str:
    """The first line of a brief, cut at a word when it is longer than ``limit``."""
    lines = (text or "").strip().splitlines()
    first = lines[0].strip() if lines else ""
    if len(first) <= limit:
        return first
    cut = first[:limit - 1]
    if first[limit - 1] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:—-") + "…"


#: what is being designed, for a product container, by the form its profile names (archetypes.py's own keys)
#: [§BH70(1): lipstick, mascara and pencil say their own names — they read "product container" until now]
_FORM_WORDS = {"compact": "compact lid", "jar": "jar", "tube": "tube", "lipstick": "lipstick", "mascara": "mascara",
               "pencil": "pencil"}


def _container_words(task, spec: dict | None) -> str:
    """What a product-container design draws: its confirmed profile's form when there is one, else the form its brief
    proposes (the proposer the profile editor itself uses), else the target's own name."""
    if (getattr(task, "options", None) or {}).get("authoring_backend") == "hybrid_bottle":
        return "serum artwork master"
    profile = (spec or {}).get("container_profile/1.0") or {}
    cap = ((profile.get("fields") or {}).get("cap_type") or {}).get("value")
    form, closure = profile.get("archetype"), str(cap or profile.get("cap_style") or "")
    if not form:
        try:
            from apps.pipeline.targets.container import _infer_profile
            inferred = _infer_profile(task)
            form, closure = inferred.archetype, str(getattr(inferred, "cap_style", "") or "")
        except Exception:        # noqa: BLE001 — a proposal that cannot be read names nothing; the target's name stands
            form = None
    if form == "bottle":
        return "dropper bottle" if "dropper" in closure.lower() else "bottle"
    # [the owner's answer of 2026-09-27: a gloss or a liquid liner in the mascara's vial is a wand vial, never a
    # mascara; a gloss in the tube is a squeeze tube]
    from apps.pipeline.targets.container import VESSEL_WORDS, brief_text, product_in_form, product_words
    if " in a " in (product_in_form(form, brief_text(task)) or ""):
        return VESSEL_WORDS[form]
    if form == "compact":
        # [his goal of 2026-10-10, item 2: "The title says "— compact lid". A palette design must include the whole
        # palette: the lid AND the open tray"] a compact whose brief names its pans is drawn open too, and says so
        from apps.ire.palette_tray import read_tray
        shades = task.product.shade_names if task.product_id and isinstance(task.product.shade_names, list) else []
        if read_tray(brief_text(task), shades=shades) is not None:
            import re
            said = product_words(brief_text(task)).lower()
            return ("palette" if re.search(r"\bpalette\b", said) else "compact") + " lid and open tray"
    return _FORM_WORDS.get(form or "", target_words(task.design_target).lower())


def what_words(task, spec: dict | None = None) -> str:
    """What is being designed, in a designer's words — "compact lid", "carton", "palette"."""
    if task.design_target == "product_container":
        return _container_words(task, spec)
    if task.design_target == "packaging":
        return "carton"
    return target_words(task.design_target).lower()


#: the name a brief gives its product in its own words — "a new eau de parfum, 50 ml, called "Midnight Fig""
_CALLED = re.compile(r"\b(?:called|named)\s+[\"“”']([^\"“”'\n]{2,60})[\"“”']", re.I)
#: a brief that opens with the house's name and then the product's — "BBROSE Cocoa Fondant Matte Lipstick, 3.5 g …"
_HOUSE_THEN_NAME = re.compile(r"\s*[A-Z]{3,}\s+([A-Z][^,.;:!?\n]{2,58}?)\s*[,.;:!?\n]")
#: what ``named_in_brief`` reads when a design has no planner's reading yet — "" means "read it" (one query)
_UNREAD = None


def named_in_brief(task, planned=_UNREAD) -> str:
    """[his last goal before the pitch, 2026-10-16, Step 1 (3): "Design titles = the product name (e.g. "Midnight Fig —
    perfume"), never the brief's first sentence."] The product's name where no product record names it: the one the
    planner read from the brief (its stored brief, ``CreativeBrief.design_intent["brief"]``, the house's own name left
    to its mark — as the drawing prints it, ``targets.container.product_name_for``), else the name the brief gives it
    in its own words (``_CALLED``), else "". ``planned``: ``(product_name, brand)`` read in bulk by ``classify``."""
    if planned is _UNREAD:
        from apps.pipeline.models import CreativeBrief
        intent = CreativeBrief.objects.filter(task=task).values_list("design_intent", flat=True).first()
        brief = intent.get("brief") if isinstance(intent, dict) else None
        brief = brief if isinstance(brief, dict) else {}
        planned = (brief.get("product_name"), brief.get("brand"))
    named = " ".join(str((planned or (None, None))[0] or "").split())
    house = " ".join(str((planned or (None, None))[1] or "").split())
    if named and house and named.lower().startswith(house.lower() + " ") and named[len(house):].strip():
        named = named[len(house):].strip()
    if named and len(named) <= 60:                # a reading that is a sentence (design 47's) names no product
        return named
    found = _CALLED.search(str(task.task_text or "")) or _HOUSE_THEN_NAME.match(str(task.task_text or ""))
    return " ".join(found.group(1).split()) if found else ""


def _planned_names(ids) -> dict:
    """``{task id: (the product name the planner read, the house it read)}`` for the designs with a brief, in one read."""
    from apps.pipeline.models import CreativeBrief
    out = {}
    for task_id, intent in CreativeBrief.objects.filter(task_id__in=list(ids)).values_list("task_id", "design_intent"):
        brief = intent.get("brief") if isinstance(intent, dict) else None
        brief = brief if isinstance(brief, dict) else {}
        out[task_id] = (brief.get("product_name"), brief.get("brand"))
    return out


def title_of(task, spec: dict | None = None, planned=_UNREAD) -> str:
    """A design's name on every screen: the product and what is designed ("Focus Pressed Powder — compact lid"). With
    no product on record, the product's name its brief gives (``named_in_brief``); only a brief that names none has its
    first words stand for the product — the brief is all it has."""
    if (getattr(task, "options", None) or {}).get("authoring_backend") == "hybrid_assembly":
        return "Twelve-bottle stepped stand — provisional geometry"
    if (getattr(task, "options", None) or {}).get("authoring_backend") == "hybrid_bottle":
        name = ((spec or {}).get("design_spec") or {}).get("copy", {}).get("name", "Serum").replace("\n", " ")
        return name + " — serum artwork master"
    name = (task.product.name if task.product_id and task.product else
            named_in_brief(task, planned) or _first_line(task.task_text, 48))
    what = what_words(task, spec)
    if name and name.lower().endswith(what.lower()):          # "Velvet Bloom Serum Carton", never "… Carton — carton"
        return name
    return "%s — %s" % (name or "Design #%d" % task.pk, what)


def _executor_test(task) -> bool:
    """[his last goal before the pitch, 2026-10-16, Step 1 (4)] a design the executor started as a test: marked so on
    its own options (``TEST_RUN_OPTION``), or a pitch run of his made before ``PITCH_RUN_TESTS_BEFORE``."""
    options = task.options if isinstance(task.options, dict) else {}
    if options.get(TEST_RUN_OPTION):
        return True
    return bool(options.get(AUTOPILOT_OPTION)) and task.created_at is not None and task.created_at < PITCH_RUN_TESTS_BEFORE


def fold_of(task, test_projects=None) -> str:
    """Why a design is folded away, or "" — his fold by task, a planning probe by its project's own marker, or the
    executor's own test (``_executor_test``) — the test's other stages too: a carton made after a test's container is
    the same test (``test_projects``: the projects with a stage so marked, read once by ``classify``; read here when
    not given)."""
    if task.pk in OWNER_FOLD:
        return OWNER_FOLD[task.pk]
    if isinstance(task.options, dict) and task.options.get(PUBLICATION_ONLY_OPTION):
        return "publication record"
    meta = (task.project.metadata or {}) if task.project_id and task.project else {}
    if any(marker in meta for marker in PROBE_MARKERS):
        return "planning test"
    if _executor_test(task):
        return "test"
    if task.project_id:
        if test_projects is None:
            test_projects = _test_projects([task.project_id])
        if task.project_id in test_projects:
            return "test"
    return ""


def _test_projects(project_ids) -> set:
    """The projects one of whose stages the executor started as a test (``_executor_test``)."""
    from apps.pipeline.models import DesignTask
    ids = {pid for pid in project_ids if pid}
    if not ids:
        return set()
    return {t.project_id for t in DesignTask.objects.filter(project_id__in=ids).only("id", "project_id", "options",
                                                                                     "created_at")
            if _executor_test(t)}


def _stop_reason(task) -> str:
    """Why a design stopped, in words — the recorded error put into plain words where words are written for it."""
    from apps.dashboard.words import stop_words
    return stop_words(task)


def _same_design(a, b) -> bool:
    """Two tries of one design: the same thing designed from the same brief, for the same product where both name one.
    MEASURED 2026-09-25: one product record (Velvet Bloom Serum Carton) stands on nine unrelated carton briefs — a
    banana rice serum, a shampoo box, a honey lip gloss — so a product alone never makes two designs one."""
    if a.design_target != b.design_target:
        return False
    if a.product_id and b.product_id and a.product_id != b.product_id:
        return False
    return _first_line(a.task_text, 400) == _first_line(b.task_text, 400)


#: the line the reconstruction writes to a design's log each time it draws it (targets/container/__init__.py, the end
#: of reconstruct_container) — the one record of WHEN a container's drawing was made
DRAWN_LOG_PREFIX = "Container: reconstructed "


def _redrawn_since_rejection(task, spec: dict) -> bool:
    """A design rejected at review whose drawing was made again after the last rejection — so it waits for his look.
    Each rejection carries when it was decided (`decided_at`); the drawing's log line carries when it was made."""
    from django.utils.dateparse import parse_datetime

    from apps.pipeline.models import AgentLog
    decided = [parse_datetime(str((spec.get(k) or {}).get("decided_at") or "")) for k in spec
               if k.startswith("container_reconstruction_rejected")]
    decided = [d for d in decided if d is not None]
    if not decided:
        return False
    return AgentLog.objects.filter(task=task, action__startswith=DRAWN_LOG_PREFIX, timestamp__gt=max(decided)).exists()


def classify(tasks=None, *, now=None, fold_old=True) -> list[Card]:
    """Every design as a Card. ``tasks`` defaults to every DesignTask; the list keeps their order (newest first).
    [his last goal before the pitch, 2026-10-16, Step 1 (4)] with ``fold_old``, a design with no sign of life for
    ``LIVE_DAYS`` is folded into "Your tests" with the executor's — the board and its counts show only live work; the
    Designs page and Find, which list every design, read them unfolded (``fold_old=False``)."""
    from django.db.models import Max

    from apps.pipeline.models import AgentLog, DesignTask
    now = now or timezone.now()
    if tasks is None:
        tasks = DesignTask.objects.select_related("product", "project").order_by("-created_at", "-id")
    tasks = list(tasks)
    ids = [t.pk for t in tasks]
    last_log = dict(AgentLog.objects.filter(task_id__in=ids).values("task_id").annotate(last=Max("timestamp"))
                    .values_list("task_id", "last"))
    specs = {}
    from apps.pipeline.models import PackagingOutput
    for output in (PackagingOutput.objects.filter(task_id__in=ids).exclude(spec_sheet=None)
                   .order_by("task_id", "-pk").only("task_id", "spec_sheet")):
        specs.setdefault(output.task_id, output.spec_sheet or {})
    limit = datetime.timedelta(seconds=stall_seconds())
    live = datetime.timedelta(days=LIVE_DAYS)
    planned = _planned_names(t.pk for t in tasks if not t.product_id)
    test_projects = _test_projects([t.project_id for t in tasks])
    cards = []
    for t in tasks:
        spec = specs.get(t.pk)
        signs = [s for s in (t.updated_at, last_log.get(t.pk)) if s]
        last_sign = max(signs) if signs else t.created_at
        card = Card(task_id=t.pk, status=t.status, target=t.design_target, product_id=t.product_id, lane="describe", state=WAITING, next_words=status_words(t.status),
                    title=title_of(t, spec, planned.get(t.pk, (None, None))), what=what_words(t, spec),
                    product_name=(t.product.name if t.product_id and t.product else ""),
                    product_name_ar=((getattr(t.product, "name_ar", "") or "") if t.product_id and t.product else ""),
                    brief_start=_first_line(t.task_text, 140), created_at=t.created_at, updated_at=t.updated_at,
                    last_sign=last_sign, fold=fold_of(t, test_projects))
        if fold_old and not card.fold and now - last_sign > live:
            card.fold = "test"
        if t.status in _STEP:
            card.lane, card.state, card.next_words = _STEP[t.status]
        if t.status in ("queued", "running"):
            card.lane, card.state = _running_lane(t), WORKING
            card.next_words = {"describe": "Writing three directions", "concept": "Drawing three concepts",
                               "size": "Getting the size ready"}.get(card.lane, "Working on it")
        if t.status in MACHINE and now - last_sign > limit:
            card.state = ATTENTION
            card.reason = (("Sent on %s and never started — the queue did not pick it up" % _day(t.created_at))
                           if t.status == "queued" and t.pk not in last_log else
                           "Stopped moving on %s, while %s" % (_day(last_sign), card.next_words.lower()))
            card.next_words = "See why"
        if t.status in STOPPED:
            card.state, card.reason, card.next_words = ATTENTION, _stop_reason(t), "See why"
        if t.status == "container_stage_visually_rejected":
            card.lane = "review"
            if _redrawn_since_rejection(t, spec or {}):
                card.state, card.next_words = WAITING, "Look again — drawn again after you rejected it"
            else:
                card.state, card.reason, card.next_words = ATTENTION, "You rejected it at its review", "See why"
        if (t.options or {}).get("authoring_backend") == "hybrid_bottle":
            card.lane, card.state, card.next_words = "review", WAITING, "Review the artwork proposal"
        if (t.options or {}).get("authoring_backend") == "hybrid_assembly":
            card.lane, card.state, card.next_words = "review", WAITING, "Review the stand geometry and unresolved facts"
            if (spec or {}).get("preflight", {}).get("status") == "refused":
                card.state, card.next_words = ATTENTION, "Stand geometry refused — review the measurements"
        cards.append(card)
    _link_tries(cards, {t.pk: t for t in tasks})
    for card in cards:
        card.unfolded_state = card.state
        if card.fold:
            card.state = FOLDED
    return cards


def _running_lane(task) -> str:
    """Where a running design is: past its concept choice, drawing concepts, or still writing its directions."""
    if task.images.filter(is_approved=True).exists():
        return "size"
    from apps.pipeline.models import CreativeBrief
    brief = CreativeBrief.objects.filter(task=task).first()
    if task.images.exists() or (brief is not None and brief.selected_direction_id):
        return "concept"
    return "describe"


def _day(when) -> str:
    return timezone.localtime(when).strftime("%-d %b")


def _link_tries(cards: list[Card], tasks: dict) -> None:
    """A stopped try whose LATER try of the same design went on is marked "tried again" and listed under that try —
    its reason kept; the later try names it. Folded tries are neither."""
    live = [c for c in cards if not c.fold]
    for card in live:
        if card.state != ATTENTION or card.status not in STOPPED:
            continue
        later = [c for c in live if c.task_id != card.task_id and c.created_at > card.created_at
                 and c.status not in STOPPED and _same_design(tasks[c.task_id], tasks[card.task_id])]
        if later:
            nearest = min(later, key=lambda c: c.created_at)
            card.state, card.later_try = TRIED_AGAIN, nearest.task_id
            nearest.earlier_stops.append(card.task_id)


def counts(cards: list[Card] | None = None) -> dict:
    """The top bar's three counts, and the rest, from one classification."""
    cards = classify() if cards is None else cards
    tally = {s: 0 for s in STATE_WORDS}
    for c in cards:
        tally[c.state] = tally.get(c.state, 0) + 1
    return tally


def board(cards: list[Card] | None = None) -> dict:
    """The board: the Needs attention lane, the six step columns and the folded groups — every design in exactly one."""
    cards = classify() if cards is None else cards
    columns = {key: [] for key, _ in LANES}
    attention, tried, folded = [], [], {}
    for c in cards:
        if c.state == FOLDED:
            folded.setdefault(c.fold, []).append(c)
        elif c.state == ATTENTION:
            attention.append(c)
        elif c.state == TRIED_AGAIN:
            tried.append(c)
        else:
            columns[c.lane].append(c)
    return {"attention": attention, "tried_again": tried,
            "columns": [{"key": k, "words": w, "cards": columns[k]} for k, w in LANES],
            "folded": [{"key": k, "words": FOLD_GROUP_WORDS.get(k, k), "cards": v} for k, v in folded.items()],
            "counts": counts(cards), "total": len(cards)}


def _picture_url(name) -> str | None:
    """A stored file as a picture the page may show: under MEDIA_ROOT, outside the reference folders, on disk — linked
    through the /files/ door, which refuses a REFERENCE-tier file by the tier record whatever links it (§BH54(b))."""
    from pathlib import Path
    from urllib.parse import quote

    from apps.dashboard import history
    name = str(name or "")
    if not name:
        return None
    root = history.media_root()
    resolved = (root / name).resolve() if not Path(name).is_absolute() else Path(name).resolve()
    if not resolved.is_relative_to(root) or history.reference_folder(resolved, root) is not None:
        return None
    if resolved.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or not resolved.is_file():
        return None
    return "/files/" + quote(resolved.relative_to(root).as_posix())


def pictures(cards: list[Card]) -> dict:
    """One picture for each card, loaded in bulk: the drawn design where there is one (its preview), else the concept
    chosen, else the newest concept drawn — or none, and the page draws the state's own icon."""
    from apps.pipeline.models import GeneratedImage, PackagingOutput
    ids = [c.task_id for c in cards]
    drawn, chosen, newest = {}, {}, {}
    for task_id, preview in (PackagingOutput.objects.filter(task_id__in=ids).exclude(design_preview="")
                             .order_by("task_id", "-pk").values_list("task_id", "design_preview")):
        drawn.setdefault(task_id, preview)
    for task_id, image, approved in (GeneratedImage.objects.filter(task_id__in=ids).exclude(image_file="")
                                     .order_by("task_id", "-created_at").values_list("task_id", "image_file",
                                                                                      "is_approved")):
        newest.setdefault(task_id, image)
        if approved:
            chosen.setdefault(task_id, image)
    found = {}
    from apps.pipeline.serializers import PackagingOutputSerializer
    hybrid = {}
    hybrid_ids = [task_id for task_id, name in drawn.items() if name.startswith("dielines/hybrid/")]
    if hybrid_ids:
        for output in PackagingOutput.objects.filter(task_id__in=hybrid_ids, spec_sheet__backend__in=("hybrid_bottle", "hybrid_assembly")).order_by("task_id", "-pk"):
            if output.task_id not in hybrid:
                hybrid[output.task_id] = PackagingOutputSerializer(output).data['design_preview_url']
    for c in cards:
        if c.task_id in hybrid:
            if hybrid[c.task_id]:
                found[c.task_id] = hybrid[c.task_id]
            continue
        for name in (drawn.get(c.task_id), chosen.get(c.task_id), newest.get(c.task_id)):
            url = _picture_url(name)
            if url:
                found[c.task_id] = url
                break
    return found
