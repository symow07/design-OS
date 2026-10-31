"""Final DIP-1A migration reconciliation, accounts zero -> latest (DIP-1A-5C).

A committed PostgreSQL migration test (runs in CI): migrate accounts from ZERO forward to
the latest migration, preserving existing auth users; roll back to zero and re-apply;
confirm the migrations seed exactly one valid genesis chain head, zero real DecisionEvents,
and a valid BootstrapState, and alter no existing auth table destructively.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .decision_chain import verify_chain

User = get_user_model()
LATEST = ("accounts", "0005_bootstrapstate")
ZERO = ("accounts", None)   # unapply all accounts migrations


def _migrate(target):
    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate([target])


def _tables():
    return set(connection.introspection.table_names())


class FinalMigrationReconciliationTest(TransactionTestCase):

    def tearDown(self):
        from django.core.management import call_command
        # DIP-1C-5C-CORR-3: migrate EVERY app, not just accounts. Rolling accounts back to
        # zero unapplies every migration that depends on it — the whole intelligence app —
        # and restoring only `accounts` left those tables missing for the rest of the
        # session. Normal django_db tests never noticed; the first intelligence
        # TransactionTestCase did.
        call_command("migrate", verbosity=0)               # leave the FULL schema at latest

    def test_zero_to_latest_forward_rollback_reapply(self):
        from .models import BootstrapState, DecisionChainHead, DecisionEvent

        keep = User.objects.create_user(username="keep-final", password="x")

        # --- accounts -> ZERO: every accounts table gone, auth_user intact --------------
        _migrate(ZERO)
        tables = _tables()
        for t in ("accounts_reviewerprofile", "accounts_reviewerroleassignment",
                  "accounts_authorizationaudit", "accounts_decisionevent",
                  "accounts_decisionchainhead", "accounts_bootstrapstate"):
            assert t not in tables, t
        assert "auth_user" in tables
        assert User.objects.filter(username="keep-final").exists()   # auth data preserved

        # --- ZERO -> LATEST: tables + valid genesis + bootstrap seeded ------------------
        _migrate(LATEST)
        tables = _tables()
        for t in ("accounts_reviewerprofile", "accounts_reviewerroleassignment",
                  "accounts_authorizationaudit", "accounts_decisionevent",
                  "accounts_decisionchainhead", "accounts_bootstrapstate"):
            assert t in tables, t

        head = DecisionChainHead.objects.get(pk=1)
        assert head.is_genesis and DecisionEvent.objects.count() == 0   # zero real events
        assert verify_chain().ok
        bs = BootstrapState.objects.get(pk=1)
        assert bs.closed is False and bs.break_glass_count == 0
        assert User.objects.filter(pk=keep.pk).exists()   # auth data still preserved

        # --- rollback to zero then re-apply: idempotent, still valid --------------------
        _migrate(ZERO)
        assert "accounts_decisionevent" not in _tables()
        assert User.objects.filter(pk=keep.pk).exists()
        _migrate(LATEST)
        assert DecisionChainHead.objects.get(pk=1).is_genesis
        assert DecisionEvent.objects.count() == 0
        assert BootstrapState.objects.filter(pk=1).exists()
