"""Cost ledger & budget controls (Milestone 12.2).

Every external AI call writes one ApiCallRecord with its computed USD cost.
[§BH71 PART 2: and every Tavily search — ``record_search``.]
The Claude service has no task in scope (it is a low-level helper shared by
agents that don't all carry a task), so the current task is supplied through a
ContextVar that ARIA sets for the duration of a pipeline run. The image
producer, which does hold ``self.task``, passes it explicitly.

Budget guards:
  * per-task  — check_task_budget() raises BudgetExceededError once a task's
    accumulated spend crosses settings.MAX_COST_PER_TASK; ARIA's crash-safe
    wrapper turns that into a failed task with a clear message.
  * per-day   — daily_budget_exceeded() blocks new task creation (429) once the
    rolling 24h spend reaches settings.MAX_COST_PER_DAY.
Set either limit to 0 to disable it.
"""
from __future__ import annotations

import contextlib
import contextvars
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.pipeline.services.pipeline_errors import PipelineError

logger = logging.getLogger("apps.pipeline")

#: 2B-3V §8 — the honest sentinel when a provider returns no request id.
PROVIDER_REQUEST_ID_NOT_RETURNED = "PROVIDER_REQUEST_ID_NOT_RETURNED"


def provider_request_id(response) -> str:
    """The provider's request id, or the honest sentinel — never invented."""
    val = getattr(response, "_request_id", None)
    return val if isinstance(val, str) and val else PROVIDER_REQUEST_ID_NOT_RETURNED


def provider_operation_id(response) -> str:
    """The provider's response/operation id (Claude message id, OpenAI response
    id) when present, else empty."""
    val = getattr(response, "id", None)
    return val if isinstance(val, str) and val else ""

_current_task: contextvars.ContextVar = contextvars.ContextVar(
    "cost_ledger_current_task", default=None,
)


class BudgetExceededError(PipelineError):
    """Raised when a task's spend crosses the per-task budget cap."""


@contextlib.contextmanager
def task_cost_context(task):
    """Bind ``task`` as the current cost-ledger task for the enclosed block."""
    token = _current_task.set(task)
    try:
        yield
    finally:
        _current_task.reset(token)


def _resolve_task(task):
    return task if task is not None else _current_task.get()


def _quantize(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))


def claude_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_price, out_price = settings.CLAUDE_PRICES.get(
        model, settings.CLAUDE_PRICE_DEFAULT,
    )
    cost = (input_tokens / 1000.0) * in_price + (output_tokens / 1000.0) * out_price
    return _quantize(cost)


def record_claude(response, model: str, operation: str = "", task=None,
                  metadata=None):
    """Record one Claude call from its response.usage. No-op if no task is in
    scope (e.g. standalone scripts or token-count probes). Returns the record
    or None. ``metadata`` carries §8 observability (latency, request/op id)."""
    from apps.pipeline.models import ApiCallRecord

    task = _resolve_task(task)
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cost = claude_cost_usd(model, input_tokens, output_tokens)
    if task is None:
        return None
    record = ApiCallRecord.objects.create(
        task=task, provider="anthropic", model=model, operation=operation,
        input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost,
        metadata=dict(metadata or {}),
    )
    return record


def record_image(model: str, operation: str = "image_generation",
                 image_count: int = 1, task=None, metadata=None):
    """Record one image-generation call (flat per-image price). ``metadata``
    carries §8 observability (latency, request id, prompt hash, ref ids)."""
    from apps.pipeline.models import ApiCallRecord

    task = _resolve_task(task)
    cost = _quantize(image_count * settings.IMAGE_PRICE_PER_IMAGE)
    if task is None:
        return None
    record = ApiCallRecord.objects.create(
        task=task, provider="openai", model=model, operation=operation,
        image_count=image_count, cost_usd=cost, metadata=dict(metadata or {}),
    )
    return record


#: §BH71 PART 2 — Tavily's documented credits per search depth (https://docs.tavily.com/documentation/api-credits),
#: read only when a response carries no usage, and then said on the row
TAVILY_DOCUMENTED_CREDITS = {"basic": 1, "fast": 1, "ultra-fast": 1, "advanced": 2}


def tavily_credits(depth: str, usage) -> tuple:
    """§BH71 PART 2 — ``(credits, where the number came from)`` for one Tavily search: the response's own
    ``usage.credits`` (the connector asks for it), else Tavily's documented price for the depth — said on the
    ledger row, never silent. An unknown depth raises: a price is never guessed."""
    if isinstance(usage, dict):
        credits = usage.get("credits")
        if isinstance(credits, (int, float)) and not isinstance(credits, bool):
            return credits, "the response's own usage"
    return (TAVILY_DOCUMENTED_CREDITS[depth],
            "Tavily's documented price for a %s search: the response carried no usage" % depth)


def record_search(*, query: str, depth: str, usage, operation: str, task=None, metadata=None):
    """§BH71 PART 2 — one ledger row per Tavily search: provider ``tavily``, model ``search:<depth>``, cost =
    credits × ``TAVILY_USD_PER_CREDIT``, the query and where its credits came from in the metadata; then the
    design's cap, as every other call. No task in scope → no row, as for ``record_claude`` and
    ``record_image``."""
    from apps.pipeline.models import ApiCallRecord

    task = _resolve_task(task)
    credits, credits_from = tavily_credits(depth, usage)
    cost = _quantize(credits * settings.TAVILY_USD_PER_CREDIT)
    if task is None:
        return None
    row_metadata = {}
    if metadata is not None:
        row_metadata.update(metadata)
    row_metadata.update({"query": query, "credits": credits, "credits_from": credits_from})
    record = ApiCallRecord.objects.create(
        task=task, provider="tavily", model="search:%s" % depth, operation=operation, cost_usd=cost,
        metadata=row_metadata,
    )
    return record


#: [his goal of 2026-10-13, (2): "let me continue 125 ... at $0"] a design whose spending is held: every paid call is
#: refused before it is made, as a spending cap is — said where it was asked for
SPEND_HELD_WORDS = "this design's spending is held at $0 — nothing paid is made for it"


def spend_held(exc) -> bool:
    """[His goal of 2026-10-13, (2).] Whether a refusal is this design's spending held at $0 (not a cap reached)."""
    return str(exc).startswith(SPEND_HELD_WORDS)


#: [his goal for the pitch, 2026-10-15, B (6): "NEVER DEGRADE TO SAVE MONEY: no "$0" path may drop or simplify parts
#: (125 lost its roses that way). Pay for what fidelity needs."] the paid calls a drawing's fidelity needs — its map's
#: reads, its motifs' and its lid's flat redraws, its tray's and its carton layout's pictures, the designer's eye: never
#: refused by a spending held at $0 (the design's caps still stop them, as they stop every call)
#: [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] and the label's missing pieces,
#: written for the product's type (``label_copy.OPERATION``): a $0 hold never leaves a label nearly empty
FIDELITY_OPERATIONS = ("container_design_map_parts", "carton_layout_parts", "designers_eye", "label_copy_writing")


from contextvars import ContextVar as _ContextVar
from contextlib import contextmanager as _contextmanager

_fidelity = _ContextVar("bbrose_fidelity_call", default=False)


@_contextmanager
def fidelity_call(operation: str = ""):
    """The paid call made inside it is one its drawing's fidelity needs where ``operation`` is (FIDELITY_OPERATIONS)."""
    token = _fidelity.set(operation in FIDELITY_OPERATIONS)
    try:
        yield
    finally:
        _fidelity.reset(token)


def before_paid_call(operation: str = "", *, fidelity: bool = False) -> None:
    """[His goal of 2026-10-13, (2).] Called before every paid call — a written answer, a picture, a web search: refused
    (``BudgetExceededError``, which every caller already says in words) where the design being made holds its spending
    at $0 (``DesignTask.options["spend_held"]``); nothing otherwise. [His goal for the pitch, B (6)] a call its drawing's
    fidelity needs (``fidelity``, ``FIDELITY_OPERATIONS``) is never held: it is paid for."""
    if fidelity or operation in FIDELITY_OPERATIONS or _fidelity.get():
        return
    task = _current_task.get()
    options = task.options if task is not None and hasattr(task, "options") else None
    if isinstance(options, dict) and options.get("spend_held"):
        raise BudgetExceededError("%s%s" % (SPEND_HELD_WORDS, (" (%s)" % operation) if operation else ""))


def task_cost_usd(task) -> Decimal:
    from apps.pipeline.models import ApiCallRecord

    total = ApiCallRecord.objects.filter(task=task).aggregate(
        s=Sum("cost_usd"))["s"]
    return total or Decimal("0")


def day_cost_usd() -> Decimal:
    """Rolling 24h spend across all tasks."""
    from apps.pipeline.models import ApiCallRecord

    since = timezone.now() - timezone.timedelta(hours=24)
    total = ApiCallRecord.objects.filter(created_at__gte=since).aggregate(
        s=Sum("cost_usd"))["s"]
    return total or Decimal("0")


def check_task_budget(task) -> None:
    cap = settings.MAX_COST_PER_TASK
    if not cap:
        return
    spent = task_cost_usd(task)
    if spent > Decimal(str(cap)):
        raise BudgetExceededError(
            f"task budget exceeded: ${spent:.2f} spent, cap is ${cap:.2f}"
        )


def daily_budget_exceeded() -> bool:
    """Rescue calendar-day/campaign accounting; historical pre-rescue rows are separate."""
    from .spend_reservation import totals
    current = totals()
    return (current['today_usd_accounted'] >= current['day_cap_usd']
            or current['total_usd_accounted'] >= current['total_cap_usd'])
