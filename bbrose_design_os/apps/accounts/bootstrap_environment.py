"""Environment classification for the single-operator ceremony — DIP-1A-BOOTSTRAP-CORR-2.

`DEBUG=True` plus a loopback database address does **not** mean "local development". An
SSH-tunnelled or proxied production database answers on `127.0.0.1` exactly like a local
one, and `DEBUG` is a rendering setting, not a deployment classification. So the endpoint is
treated as *necessary and insufficient*: the environment must additionally declare itself
`LOCAL_DEVELOPMENT`, and the database name must appear in an explicit allow-list.

Every condition must hold. The function returns the evidence it used, so the resulting
signed event records what was actually observed rather than a bare verdict.
"""
from __future__ import annotations

import ipaddress

from django.conf import settings

from .bootstrap_registry import ENVIRONMENT_LOCAL_DEVELOPMENT

#: Markers that positively indicate a shared or production deployment. Presence of any one
#: refuses the ceremony regardless of everything else.
PRODUCTION_MARKER_SETTINGS = (
    "AWS_STORAGE_BUCKET_NAME", "SENTRY_DSN", "PRODUCTION", "IS_PRODUCTION",
)
SHARED_ENVIRONMENT_NAMES = ("PRODUCTION", "STAGING", "SHARED", "TEST", "CI", "DEMO")


class EnvironmentClassificationError(RuntimeError):
    """The environment is not a confirmed local development environment. Fails closed."""

    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _is_local_endpoint(host) -> bool:
    """A blank host means a UNIX domain socket — local by construction."""
    host = (host or "").strip()
    if not host:
        return True
    if host.startswith("/"):
        return True
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def classify_environment(*, require_flags=True):
    """Classify, or refuse. Returns `(classification, evidence)`; raises otherwise."""
    database = settings.DATABASES.get("default", {})
    host = database.get("HOST") or ""
    name = database.get("NAME") or ""
    environment = str(getattr(settings, "ENVIRONMENT", "") or "").strip().upper()
    allow_list = list(getattr(settings, "LOCAL_DEVELOPMENT_DATABASES", ()) or ())
    evidence = {
        "declared_environment": environment,
        "database_host_is_local_endpoint": _is_local_endpoint(host),
        "database_name_allow_listed": name in allow_list,
        "debug": bool(settings.DEBUG),
        "bootstrap_enabled": bool(getattr(settings, "BOOTSTRAP_ENABLED", False)),
        "bootstrap_single_operator_enabled": bool(
            getattr(settings, "BOOTSTRAP_SINGLE_OPERATOR_ENABLED", False)),
    }

    if require_flags:
        if not evidence["bootstrap_enabled"]:
            raise EnvironmentClassificationError("BOOTSTRAP_NOT_ENABLED")
        if not evidence["bootstrap_single_operator_enabled"]:
            raise EnvironmentClassificationError("SINGLE_OPERATOR_BOOTSTRAP_NOT_ENABLED")
    if not evidence["debug"]:
        raise EnvironmentClassificationError("DEBUG_IS_NOT_ENABLED")
    if environment != ENVIRONMENT_LOCAL_DEVELOPMENT:
        raise EnvironmentClassificationError(
            "ENVIRONMENT_NOT_DECLARED_LOCAL_DEVELOPMENT",
            f"declared {environment or '<unset>'!r}")
    if environment in SHARED_ENVIRONMENT_NAMES:      # defence in depth, unreachable above
        raise EnvironmentClassificationError("SHARED_ENVIRONMENT_MARKER_PRESENT")
    for marker in PRODUCTION_MARKER_SETTINGS:
        if getattr(settings, marker, None):
            raise EnvironmentClassificationError(
                "PRODUCTION_MARKER_PRESENT", f"setting {marker}")
    if not evidence["database_host_is_local_endpoint"]:
        raise EnvironmentClassificationError(
            "DATABASE_HOST_IS_NOT_A_LOCAL_ENDPOINT")
    if not evidence["database_name_allow_listed"]:
        # a tunnelled production database also answers on loopback — the name is the
        # discriminator, and it must be declared in advance, never guessed
        raise EnvironmentClassificationError(
            "DATABASE_NAME_NOT_IN_LOCAL_DEVELOPMENT_ALLOW_LIST")
    return ENVIRONMENT_LOCAL_DEVELOPMENT, evidence
