from apps.pipeline.services.spend_reservation import paid_operation
import base64
import json
import logging
import mimetypes
import re

import anthropic
from django.conf import settings

from apps.pipeline.services.pipeline_errors import retry_transient

logger = logging.getLogger("apps.pipeline")

# Pass `or None` so an empty .env key falls through to the ANTHROPIC_API_KEY
# env var (and otherwise fails at request time with a clear auth error) rather
# than silently sending an empty credential. The client is created lazily so
# importing this module (e.g. during test collection) has no network side
# effects.
_client = None


def _get_client():
    # [his goal of 2026-10-13, (2)] a design holding its spending at $0 never reaches the writing service — [his goal for
    # the pitch, B (6)] save where its drawing's fidelity needs the answer (``cost_ledger.fidelity_call``)
    from apps.pipeline.services.cost_ledger import before_paid_call
    before_paid_call("a written answer")
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY or None,
            timeout=settings.CLAUDE_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client

# Model names are settings-driven (Milestone 8.5): settings.CLAUDE_MODEL_HEAVY
# for judgement-heavy work (vision QA — the default here), and callers pass
# model=settings.CLAUDE_MODEL_FAST for the cheaper text agents (Creative
# Director, Prompt Engineer, dimension estimation).


@retry_transient()
def call_claude(system_prompt, content, tools=None, max_tokens=4096, model=None,
                operation=""):
    """
    Base Claude API call used by all agents.

    `content` may be either a plain string (the common case) or a list of
    Anthropic content blocks — e.g. a mix of {"type": "text", ...} and
    {"type": "image", ...} blocks for multimodal (vision) calls. It is passed
    straight through as the user message content.

    The system prompt is sent as a cached block — it is the stable prefix
    shared across repeated agent calls, so caching it cuts cost/latency on
    every call after the first within the 5-minute window.
    """
    kwargs = {
        "model": model or settings.CLAUDE_MODEL_HEAVY,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": content}],
    }
    if tools:
        kwargs["tools"] = tools

    import time as _time
    from datetime import datetime, timezone as _tz
    _start = _time.monotonic()
    _start_iso = datetime.now(_tz.utc).isoformat()
    from apps.pipeline.services.cost_ledger import fidelity_call
    with fidelity_call(operation):
        response = paid_operation(_get_client().messages.create, provider='anthropic', operation=operation, **kwargs)
    _latency_ms = int((_time.monotonic() - _start) * 1000)

    # Cost ledger (Milestone 12.2): record against the task ARIA bound in the
    # context. Recording must never break a pipeline that otherwise succeeded,
    # except for a deliberate BudgetExceededError which callers must surface.
    # 2B-3V §8: attach per-call observability (latency, request/op id, hash).
    from apps.pipeline.services.cost_ledger import (
        BudgetExceededError, provider_operation_id, provider_request_id,
        record_claude)
    metadata = {
        "provider_request_id": provider_request_id(response),
        "provider_operation_id": provider_operation_id(response),
        "start_ts": _start_iso,
        "end_ts": datetime.now(_tz.utc).isoformat(),
        "latency_ms": _latency_ms,
        "retry_number": 0,
        "prompt_hash": _prompt_hash(system_prompt, content),
    }
    try:
        record_claude(response, kwargs["model"], operation=operation,
                      metadata=metadata)
    except BudgetExceededError:
        raise
    except Exception:  # pragma: no cover - ledger must not mask a good result
        logger.exception("cost ledger: failed to record Claude call")
    return response


def _prompt_hash(system_prompt, content) -> str:
    """Stable sha256 over the system prompt + user content (§8)."""
    import hashlib
    import json
    blob = json.dumps({"system": system_prompt, "content": content},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def image_block_from_file(path):
    """Build an Anthropic image content block from a local image file.

    Reads the bytes, base64-encodes them, and infers the media type from the
    extension (defaulting to image/png). Returns a dict ready to drop into the
    `content` list passed to call_claude().
    """
    media_type, _ = mimetypes.guess_type(path)
    if media_type not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        media_type = "image/png"
    with open(path, "rb") as fh:
        data = base64.standard_b64encode(fh.read()).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
    }


def extract_text(response):
    """Extract plain text from Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def loads_tolerant(text):
    """Parse a JSON object from raw model text, tolerantly.

    Handles the common ways models wrap JSON — ```json fences, leading prose,
    trailing commentary — and falls back to the outermost {...} span. Raises
    ValueError (not a bare JSONDecodeError) so callers can surface a clear
    message and degrade gracefully.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty model response")

    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"could not parse JSON from model response: {text[:200]}")


def extract_json(response):
    """Parse a JSON object from a Claude response object, tolerantly."""
    return loads_tolerant(extract_text(response))


if __name__ == "__main__":
    response = call_claude(
        system_prompt="You are a helpful assistant.",
        content="Say hello in one sentence.",
    )
    print(extract_text(response))
