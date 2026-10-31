"""Dry readiness check for the single-operator ceremony — DIP-1A-BOOTSTRAP-CORR-2.

Read-only, and it never touches a password: it reports whether every *inspectable*
precondition holds, leaving the account-control challenge as the one remaining step. It
writes nothing and grants nothing.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from . import bootstrap_registry as reg
from .bootstrap_environment import EnvironmentClassificationError, classify_environment
from .decision_chain import verify_chain
from .models import (
    BootstrapState, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)


def build_ceremony_preflight(*, username, role=None, expires_days=None):
    role = role or reg.ALLOWED_BOOTSTRAP_ROLES[0]
    blocking, lines = [], []

    try:
        classification, evidence = classify_environment()
        lines.append(f"environment            : {classification}")
    except EnvironmentClassificationError as exc:
        classification, evidence = "", {}
        blocking.append(exc.code)
        lines.append(f"environment            : REFUSED ({exc.code})")

    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if user is None:
        blocking.append("ACCOUNT_DOES_NOT_EXIST")
        lines.append(f"account                : {username!r} DOES NOT EXIST")
    else:
        lines.append(f"account                : {username!r} "
                     f"active={user.is_active} superuser={user.is_superuser}")
        if not user.is_active:
            blocking.append("ACCOUNT_INACTIVE")
        if not user.is_superuser:
            blocking.append("ACCOUNT_NOT_SUPERUSER")

    if role not in reg.ALLOWED_BOOTSTRAP_ROLES:
        blocking.append("ROLE_NOT_PERMITTED_IN_CEREMONY")
    lines.append(f"role                   : {role}")

    if expires_days is not None:
        lines.append(f"expiry                 : {expires_days} days "
                     f"(max {reg.MAX_EXPIRY_DAYS})")
        if expires_days <= 0 or expires_days > reg.MAX_EXPIRY_DAYS:
            blocking.append("EXPIRY_OUT_OF_BOUND")

    chain_ok = verify_chain().ok
    event_count = DecisionEvent.objects.count()
    lines.append(f"chain                  : verified={chain_ok} events={event_count}")
    if not chain_ok:
        blocking.append("DECISION_CHAIN_NOT_VERIFIED")
    if event_count:
        blocking.append("CHAIN_IS_NOT_AT_GENESIS")

    assignments = ReviewerRoleAssignment.objects.count()
    profiles = ReviewerProfile.objects.count()
    lines.append(f"reviewer state         : profiles={profiles} assignments={assignments}")
    if assignments:
        blocking.append("REVIEWER_ROLE_ASSIGNMENTS_ALREADY_EXIST")

    state = BootstrapState.objects.filter(pk=1).first()
    lines.append(f"bootstrap state        : closed={state.closed if state else '?'} "
                 f"break_glass={state.break_glass_count if state else '?'}")
    if state is None:
        blocking.append("NO_BOOTSTRAP_STATE")
    else:
        if state.closed:
            blocking.append("BOOTSTRAP_PERMANENTLY_CLOSED")
        if state.break_glass_count:
            blocking.append("BREAK_GLASS_COUNT_IS_NOT_ZERO")

    if DecisionEvent.objects.filter(
            action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).exists():
        blocking.append("CEREMONY_ALREADY_PERFORMED")

    from apps.intelligence.models import OperationalPermissionProjection
    permissions = OperationalPermissionProjection.objects.count()
    lines.append(f"operational permissions: {permissions}")
    if permissions:
        blocking.append("OPERATIONAL_PERMISSIONS_ALREADY_EXIST")

    lines.append("account control        : interactive password challenge REQUIRED "
                 "(not performed by this dry run)")
    return {
        "ready": not blocking,
        "blocking": sorted(set(blocking)),
        "lines": lines,
        "environment_classification": classification,
        "environment_evidence": evidence,
    }
