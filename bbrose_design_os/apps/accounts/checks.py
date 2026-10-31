"""Startup policy checks for reviewer identity (DIP-1A-2).

The accounts models import `apps.accounts.authz_policy` as the single role/action policy
source and store assignments against it. If that source is unreachable or degenerate, role
resolution silently narrows to "nobody has any role" — which is safe (fail-closed) but
would be a baffling production symptom. This check surfaces the cause loudly at
`manage.py check` time instead of leaving it to be discovered when every reviewer suddenly
has no authority.

Since the policy now lives inside the deployable app package, an import failure would be a
genuine packaging fault (a corrupt or partial deploy), not a missing sibling tool.
"""
from __future__ import annotations

from django.core.checks import Error, register

POLICY_UNREACHABLE = "accounts.policy.E001"
POLICY_DEGENERATE = "accounts.policy.E002"


@register("accounts")
def check_authz_policy_source(app_configs, **kwargs):
    try:
        from . import authz_policy as authz
    except Exception as e:  # pragma: no cover - exercised via the degenerate-import test
        return [Error(
            f"cannot import the authorization policy source "
            f"apps.accounts.authz_policy: {e}",
            hint="The accounts app stores role assignments against "
                 "apps/accounts/authz_policy.py. If this import fails the deploy is "
                 "incomplete or corrupt — the module is part of the app package.",
            id=POLICY_UNREACHABLE)]

    roles = getattr(authz, "ROLES", None)
    if (not isinstance(roles, tuple) or not roles
            or not all(isinstance(r, str) and r for r in roles)):
        return [Error(
            f"authz.ROLES is not a non-empty tuple of role strings (got {roles!r}). "
            "Role resolution would fail closed for everyone.",
            hint="apps/accounts/authz_policy.py must define ROLES as a non-empty tuple "
                 "of distinct role-name strings.",
            id=POLICY_DEGENERATE)]

    return []


PROTECTED_ACTION_UNKNOWN = "accounts.policy.E003"


@register("accounts")
def check_protected_actions_are_known(app_configs, **kwargs):
    """Every action guarded by an endpoint must be a known DIP reviewer-policy action.

    This validates the DIP reviewer authorization surface ONLY. The legacy pipeline Group
    permissions in apps/pipeline/permissions.py are a separate system (Designer/Reviewer/
    Admin Django Groups) and are deliberately out of scope here.

    Endpoints register their single action at import time. To make sure the registry is
    populated before we inspect it, we nudge the URL configuration to load (which imports
    the view modules); if it cannot load we simply validate whatever is already registered
    rather than break the check framework.
    """
    from . import authz_policy as authz
    from .authorization import PROTECTED_ACTIONS

    try:  # populate the registry by importing the view modules the URLconf references
        from django.urls import get_resolver
        get_resolver().url_patterns
    except Exception:  # pragma: no cover - never let URL loading break the check
        pass

    unknown = sorted(a for a in PROTECTED_ACTIONS if a not in authz.ACTIONS)
    if unknown:
        return [Error(
            f"protected endpoint(s) declare unknown authorization action(s): {unknown}. "
            "Every guarded endpoint must map to exactly one canonical action in "
            "authz.ACTIONS.",
            hint="Use a constant from apps/accounts/authz_policy.py; do not invent an "
                 "action name or take it from the request.",
            id=PROTECTED_ACTION_UNKNOWN)]
    return []


# --- DIP-1A-BOOTSTRAP-CORR-2: single-operator ceremony gating --------------------
SINGLE_OPERATOR_OUTSIDE_LOCAL = "accounts.bootstrap.E010"
SINGLE_OPERATOR_WITHOUT_DEBUG = "accounts.bootstrap.E011"
SINGLE_OPERATOR_REMOTE_DATABASE = "accounts.bootstrap.E012"
SINGLE_OPERATOR_DATABASE_NOT_ALLOW_LISTED = "accounts.bootstrap.E013"


@register("accounts")
def check_single_operator_bootstrap_is_local_only(app_configs, **kwargs):
    """The single-operator ceremony is a local-development affordance. If its flag is on
    anywhere else, fail LOUDLY at startup rather than let a deployment discover it the way
    incidents are usually discovered.

    Deliberately a startup check as well as a runtime gate: a production config carrying
    this flag is a configuration defect even if the command is never run.
    """
    from django.conf import settings

    from .bootstrap_environment import _is_local_endpoint
    from .bootstrap_registry import ENVIRONMENT_LOCAL_DEVELOPMENT

    if not getattr(settings, "BOOTSTRAP_SINGLE_OPERATOR_ENABLED", False):
        return []

    errors = []
    environment = str(getattr(settings, "ENVIRONMENT", "") or "").strip().upper()
    hint = ("BOOTSTRAP_SINGLE_OPERATOR_ENABLED seeds a reviewer from ONE operator with no "
            "dual control. It is only ever appropriate on a developer's own machine; unset "
            "it everywhere else.")
    if environment != ENVIRONMENT_LOCAL_DEVELOPMENT:
        errors.append(Error(
            f"BOOTSTRAP_SINGLE_OPERATOR_ENABLED is set but ENVIRONMENT is "
            f"{environment or '<unset>'!r}, not {ENVIRONMENT_LOCAL_DEVELOPMENT!r}.",
            hint=hint, id=SINGLE_OPERATOR_OUTSIDE_LOCAL))
    if not settings.DEBUG:
        errors.append(Error(
            "BOOTSTRAP_SINGLE_OPERATOR_ENABLED is set with DEBUG=False, which is a "
            "deployment posture, not a development one.",
            hint=hint, id=SINGLE_OPERATOR_WITHOUT_DEBUG))

    database = settings.DATABASES.get("default", {})
    if not _is_local_endpoint(database.get("HOST")):
        errors.append(Error(
            "BOOTSTRAP_SINGLE_OPERATOR_ENABLED is set but the default database host is "
            "not a local endpoint.",
            hint=hint, id=SINGLE_OPERATOR_REMOTE_DATABASE))
    allow_list = list(getattr(settings, "LOCAL_DEVELOPMENT_DATABASES", ()) or ())
    if (database.get("NAME") or "") not in allow_list:
        errors.append(Error(
            f"BOOTSTRAP_SINGLE_OPERATOR_ENABLED is set but database "
            f"{database.get('NAME')!r} is not in LOCAL_DEVELOPMENT_DATABASES. A tunnelled "
            "production database also answers on loopback — the name is the discriminator.",
            hint=hint, id=SINGLE_OPERATOR_DATABASE_NOT_ALLOW_LISTED))
    return errors
