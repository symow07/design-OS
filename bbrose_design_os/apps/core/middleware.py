"""Request-ID propagation + logging helpers (Milestone 14.1).

Every request gets a short id (honouring an inbound ``X-Request-ID`` from a
proxy, else generated). It is stashed in a ContextVar so log records — from the
view, the ORM, or a signal on the same thread — can be correlated, and echoed
back on the response header. The JSON formatter is used in production so logs
are machine-parseable; dev uses the verbose text formatter.
"""
from __future__ import annotations

import contextvars
import datetime as _dt
import json
import logging
import uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-",
)


def get_request_id() -> str:
    return _request_id.get()


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = _request_id.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


#: The policy this application would enforce if it could, and the exact
#: reason it cannot. Every directive is `'self'` because the served surface
#: genuinely has no external origin: across the 20 templates Django loads
#: (`templates/`; `APP_DIRS` contributes none) there are ZERO external URLs,
#: ZERO external font links and ZERO `data:` URIs. Measured 2026-08-22.
#:
#: `blob:` is in `img-src` because it was MEASURED to be needed, not assumed:
#: `static/js/staged_references.js:54` calls `URL.createObjectURL(f)` to
#: preview staged reference images. `'unsafe-eval'` is absent because it was
#: measured NOT to be needed — no `eval(` or `new Function` in any of the 12
#: static JS files.
#:
#: `frame-ancestors 'none'` is the CSP spelling of `X_FRAME_OPTIONS = "DENY"`
#: at config/settings.py:529. They agree deliberately; if one is ever changed
#: the other is the place to look.
CSP_POLICY = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
))


class ContentSecurityPolicyMiddleware:
    """Emits `Content-Security-Policy-REPORT-ONLY`. Never enforcing.

    REPORT-ONLY IS A REFUSAL, NOT AN OVERSIGHT, AND THE REFUSAL IS THE
    LOAD-BEARING PART OF THIS CLASS (§AY0(e)). Enforcing ``CSP_POLICY``
    today would break the dashboard. The measured reason, 2026-08-22, in
    the 20 templates Django actually loads:

        2    inline ``<script>`` blocks   (library/index.html:92,
                                           dashboard/index.html:26)
        3    inline event handlers        (library/index.html:149,160;
                                           dashboard/_task_list.html:14)
        7    ``<style>`` blocks
        101  inline ``style="…"`` attributes

    [The clean-up of 2026-10-04: the three templates named above — the old library and dashboard pages and
    the task-list partial — left with the old dashboard, so these counts are the 2026-08-22 measurement and
    not today's; they are re-measured before this policy is ever enforced.]

    Script is nearly clean — the dashboard already loads all 12 of its JS
    files through ``{% static %}``, so ``script-src 'self'`` is 2 blocks and
    3 handlers away from true. Style is the real distance: an inline style
    ATTRIBUTE cannot carry a nonce at all, so those 101 cannot be
    whitelisted, only removed. That is the stated remainder, and it is why
    this is a measurement of a gap rather than a claim of protection.

    `'unsafe-inline'` IS DELIBERATELY ABSENT, AND THAT IS THE WHOLE POINT.
    Adding it would make the policy enforceable this afternoon and worthless
    forever: a CSP permitting inline script is a header that stops nothing
    while reading, to anyone auditing the response or grepping for
    "Content-Security-Policy", exactly like hardening. It would convert an
    honest absence into a false positive. An over-strict Report-Only policy
    costs one console report; a permissive enforcing one costs the truth.

    There is also NO ``report-uri``/``report-to``. Violations surface in the
    browser console, not on the server. Collecting them needs an
    unauthenticated POST endpoint, which is a log-flooding surface and a
    separate decision with its own risk — not something to attach to a
    header change. Recorded as remainder, not built.

    Deliberately NOT settings-configurable. A ``CSP_REPORT_ONLY`` env flag
    would let the policy be flipped to enforcing without touching the test
    that pins it, which is precisely the review moment worth keeping: the
    101 inline styles and this class must change in the same edit.
    """

    #: Scoped to documents. A CSP governs how a DOCUMENT loads
    #: subresources; a JSON API reply or a PDF download has no document for
    #: the directives to apply to, so tagging them is noise in every
    #: response rather than protection in any.
    HTML = "text/html"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.get("Content-Type", "").startswith(self.HTML):
            return response
        # An upstream proxy that already set one wins; never stack two.
        if "Content-Security-Policy-Report-Only" not in response:
            response["Content-Security-Policy-Report-Only"] = CSP_POLICY
        return response


class RequestIDLogFilter(logging.Filter):
    """Injects ``request_id`` onto every record so formatters can print it."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Minimal dependency-free JSON log formatter for production."""

    def format(self, record):
        payload = {
            "ts": _dt.datetime.fromtimestamp(
                record.created, tz=_dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)
