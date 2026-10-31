import logging
import random
import time
from functools import wraps

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline failures."""
    pass


class AgentParseError(PipelineError):
    """Claude returned unparseable JSON."""
    pass


class ImageDownloadError(PipelineError):
    """Downloading a generated image to local storage failed after retries."""
    pass


class BillingLimitError(PipelineError):
    """The PROVIDER account refused for billing reasons (hard limit /
    exhausted quota) — distinct from this app's cost ledger. Retrying more
    variations is pointless; fail fast with an actionable message."""
    pass


_BILLING_MARKERS = (
    "billing hard limit", "insufficient_quota", "billing_not_active",
    "exceeded your current quota",
)


def is_billing_error(exc) -> bool:
    """Provider-side billing/quota refusal (2026-07-04)."""
    return any(m in str(exc).lower() for m in _BILLING_MARKERS)


# --- Transient-error classification (Milestone 8.5 / audit C7) ---------------
# Retry ONLY: rate limits (429), overloaded (529), 5xx, timeouts, connection
# errors. Never retry 400/401/403/404 — those fail fast.

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504, 529}


def _sdk_exceptions(module_name, names):
    """Collect SDK exception classes defensively — attribute names differ
    across anthropic/openai SDK versions, so anything missing is skipped."""
    try:
        module = __import__(module_name)
    except ImportError:
        return ()
    found = (getattr(module, name, None) for name in names)
    return tuple(cls for cls in found if isinstance(cls, type))


def _transient_exception_classes():
    names = (
        "APIConnectionError", "APITimeoutError", "RateLimitError",
        "InternalServerError", "OverloadedError",
    )
    classes = _sdk_exceptions("anthropic", names) + _sdk_exceptions("openai", names)
    try:
        import requests
        classes += (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    except ImportError:
        pass
    return classes + (ConnectionError, TimeoutError)


_TRANSIENT_CLASSES = _transient_exception_classes()


def _status_code(exc):
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _retry_after_seconds(exc):
    """Retry-After header (seconds) when the SDK exposes the response."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    try:
        value = headers.get("retry-after") or headers.get("Retry-After")
    except Exception:  # noqa: BLE001 — mock/odd header containers
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_transient(exc):
    """True for errors worth retrying (429/529/5xx/timeout/connection)."""
    status = _status_code(exc)
    if status is not None:
        return status in _RETRYABLE_STATUSES or status >= 500
    return isinstance(exc, _TRANSIENT_CLASSES)


def retry_transient(max_attempts=5, base_delay=1.0, max_total_wait=60.0):
    """Retry decorator for external API calls (Claude, OpenAI, downloads).

    - Retries ONLY transient errors (see is_transient); anything else — 400,
      401, 403, 404, parse errors — re-raises immediately with a clear log.
    - Exponential backoff with jitter; honors Retry-After when present.
    - At most ``max_attempts`` attempts and ``max_total_wait`` seconds of
      cumulative sleep.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            waited = 0.0
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 — classified below
                    if not is_transient(e):
                        logger.error(
                            f'{fn.__name__} failed with non-retryable error '
                            f'(no retry): {e}'
                        )
                        raise
                    if attempt >= max_attempts:
                        logger.error(
                            f'{fn.__name__} failed after {attempt} attempts: {e}'
                        )
                        raise
                    delay = _retry_after_seconds(e)
                    if delay is None:
                        delay = base_delay * (2 ** (attempt - 1)) * (1 + random.random() * 0.25)
                    if waited + delay > max_total_wait:
                        logger.error(
                            f'{fn.__name__}: retry wait budget ({max_total_wait}s) '
                            f'exhausted: {e}'
                        )
                        raise
                    logger.warning(
                        f'{fn.__name__} attempt {attempt} hit transient error: {e}. '
                        f'Retrying in {delay:.1f}s.'
                    )
                    time.sleep(delay)
                    waited += delay
        return wrapper
    return decorator
