"""Startup policy check for the database transport (Phase 2A-6B §8).

The local GSS fork-safety workaround must never leak into a shared deployment, and a shared deployment must not leave
its database transport ambiguous (`check_database_transport_policy`, below). Same honesty rule as the single-operator
bootstrap ceremony (apps/accounts/checks.py): the environment must DECLARE itself. It is never inferred from DEBUG or
from a loopback database address — a tunnelled production database also answers on localhost.

[The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow".] This module also held the activation guard
of the standard vector packaging pipeline (2A-6A): `check_standard_pipeline_activation` with its migration arm, and
`check_production_output_intent`, both gated on the STANDARD_VECTOR_PACKAGING_PIPELINE flag. They left with the flag
and the structure-confirmation flow. Migration drift on a declared local machine is reported by apps/core/checks.py,
which never read the flag; the transport policy below never read it either.
"""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning, register

_LOCAL = "LOCAL_DEVELOPMENT"


# --- database transport policy (Phase 2A-6B §8) ------------------------------

TRANSPORT_POLICY_AMBIGUOUS = "dielines.dbtransport.E005"
TRANSPORT_GSS_WORKAROUND_LEAKED = "dielines.dbtransport.E006"
TRANSPORT_TLS_UNSET = "dielines.dbtransport.W002"

#: Environments that must state their database transport policy explicitly.
_SHARED_ENVIRONMENTS = ("PRODUCTION", "STAGING", "SHARED")


@register("dielines")
def check_database_transport_policy(app_configs, **kwargs):
    """The local GSS fork-safety workaround must never leak into a shared
    deployment, and a shared deployment must not leave transport ambiguous.

    Never logs or echoes credentials: only the policy values are inspected.
    """
    environment = str(getattr(settings, "ENVIRONMENT", "UNCLASSIFIED"))
    options = (settings.DATABASES.get("default", {}).get("OPTIONS") or {})
    gss = str(options.get("gssencmode", "") or "").strip()
    tls = str(options.get("sslmode", "") or "").strip()
    explicit_gss = str(getattr(settings, "DB_GSSENCMODE", "") or "").strip()

    if environment == _LOCAL:
        return []                      # the documented local workaround

    messages = []
    if environment in _SHARED_ENVIRONMENTS:
        if gss == "disable" and not explicit_gss:
            messages.append(Error(
                f"the local GSS fork-safety workaround (gssencmode=disable) is "
                f"active in {environment} without being configured there.",
                hint="Set DB_GSSENCMODE explicitly for this environment. The "
                     "macOS prefork workaround must never be inherited "
                     "silently by a shared deployment.",
                id=TRANSPORT_GSS_WORKAROUND_LEAKED))
        elif not gss:
            messages.append(Error(
                f"{environment} does not state a database GSS policy.",
                hint="Set DB_GSSENCMODE (e.g. 'prefer' with Kerberos, "
                     "'disable' without). An ambiguous transport policy is "
                     "refused rather than guessed.",
                id=TRANSPORT_POLICY_AMBIGUOUS))
        if not tls:
            messages.append(Warning(
                f"{environment} does not state a database TLS policy "
                "(DB_SSLMODE).",
                hint="TLS is independent of GSS: set DB_SSLMODE (e.g. "
                     "'require' or 'verify-full'). Disabling GSS encryption "
                     "says nothing about transport encryption.",
                id=TRANSPORT_TLS_UNSET))
    elif gss == "disable" and not explicit_gss:
        messages.append(Error(
            f"gssencmode=disable is active in an {environment} environment "
            "without being configured there.",
            hint="Declare ENVIRONMENT and set DB_GSSENCMODE explicitly.",
            id=TRANSPORT_GSS_WORKAROUND_LEAKED))
    return messages
