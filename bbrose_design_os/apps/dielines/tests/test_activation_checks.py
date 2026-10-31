"""The database transport policy, checked at startup (Phase 2A-6B §8).

[The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow".] This file also pinned the standard
pipeline's activation guard (Phase 2A-6A §2: refused outside a DECLARED local-development environment, on a
non-allow-listed or remote database, with DEBUG off, or with migrations outstanding) and its committed default. The
guard left with its flag and the structure-confirmation flow; the transport policy never read the flag, and stays.
"""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from apps.dielines.checks import (
    TRANSPORT_GSS_WORKAROUND_LEAKED,
    TRANSPORT_POLICY_AMBIGUOUS,
    TRANSPORT_TLS_UNSET,
)


def _ids(messages):
    return {m.id for m in messages}


class DatabaseTransportPolicyTests(SimpleTestCase):
    """§8 — the local GSS fork-safety workaround must never leak into a
    shared deployment, and TLS is configured independently of GSS."""

    def _check(self):
        from apps.dielines.checks import check_database_transport_policy
        return check_database_transport_policy(None)

    @override_settings(ENVIRONMENT="LOCAL_DEVELOPMENT", DB_GSSENCMODE="disable",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "bbrose_db",
                           "OPTIONS": {"gssencmode": "disable"}}})
    def test_local_explicit_disable_is_accepted(self):
        assert self._check() == []

    @override_settings(ENVIRONMENT="PRODUCTION", DB_GSSENCMODE="",
                       DB_SSLMODE="require",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "prod",
                           "OPTIONS": {"gssencmode": "disable",
                                       "sslmode": "require"}}})
    def test_leaked_local_workaround_is_refused_in_production(self):
        ids = _ids(self._check())
        assert TRANSPORT_GSS_WORKAROUND_LEAKED in ids

    @override_settings(ENVIRONMENT="PRODUCTION", DB_GSSENCMODE="",
                       DB_SSLMODE="",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "prod", "OPTIONS": {}}})
    def test_production_without_an_explicit_policy_is_refused(self):
        ids = _ids(self._check())
        assert TRANSPORT_POLICY_AMBIGUOUS in ids
        assert TRANSPORT_TLS_UNSET in ids          # TLS reported separately

    @override_settings(ENVIRONMENT="PRODUCTION", DB_GSSENCMODE="prefer",
                       DB_SSLMODE="verify-full",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "prod",
                           "OPTIONS": {"gssencmode": "prefer",
                                       "sslmode": "verify-full"}}})
    def test_production_secure_configuration_passes(self):
        assert self._check() == []

    @override_settings(ENVIRONMENT="PRODUCTION", DB_GSSENCMODE="disable",
                       DB_SSLMODE="require",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "prod",
                           "OPTIONS": {"gssencmode": "disable",
                                       "sslmode": "require"}}})
    def test_tls_is_independent_of_gss(self):
        """Disabling GSS encryption deliberately (with TLS on) is allowed —
        the two settings must not be conflated."""
        assert self._check() == []

    @override_settings(ENVIRONMENT="PRODUCTION", DB_GSSENCMODE="prefer",
                       DB_SSLMODE="verify-full",
                       DATABASES={"default": {
                           "ENGINE": "django.db.backends.postgresql",
                           "NAME": "prod", "USER": "svc_user",
                           "PASSWORD": "s3cr3t-do-not-log",
                           "OPTIONS": {"gssencmode": "prefer",
                                       "sslmode": "verify-full"}}})
    def test_no_credentials_appear_in_check_output(self):
        blob = " ".join(f"{m.msg} {m.hint}" for m in self._check())
        assert "s3cr3t-do-not-log" not in blob
        assert "svc_user" not in blob

    def test_committed_default_leaves_gss_unset(self):
        """The repository default must NOT ship the workaround; it is applied
        only when ENVIRONMENT declares LOCAL_DEVELOPMENT."""
        import pathlib
        import re
        source = pathlib.Path("config/settings.py").read_text(encoding="utf-8")
        match = re.search(r'DB_GSSENCMODE\s*=\s*env\(\s*"DB_GSSENCMODE"\s*,\s*'
                          r'default="(.*?)"\)', source)
        assert match is not None
        assert match.group(1) == ""
