"""Committed migration-executor test for accounts 0003 (DIP-1A-5 pre-correction).

Runs in CI (part of the normal suite). Verifies forward 0002->0003, that existing auth
users / reviewer profiles / role assignments / authorization audits survive, that the
genesis head exists and verifies with zero real events, that rollback 0003->0002 drops
ONLY the two decision-chain tables, and that re-apply succeeds.

The test re-applies 0003 at the end, so it leaves the schema fully migrated. It is a
TransactionTestCase (migrations run real DDL, which cannot happen inside the atomic block a
normal django_db test uses). Its post-test flush truncates the migration-seeded genesis
head, but no test that sorts after this one depends on it.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from .decision_chain import verify_chain
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    DecisionChainHead,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

User = get_user_model()
AT_0002 = ("accounts", "0002_authorizationaudit")
AT_0003 = ("accounts", "0003_decisionevent_decisionchainhead")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


def _tables():
    return set(connection.introspection.table_names())


class Migration0003Test(TransactionTestCase):

    def tearDown(self):
        # This test leaves accounts migrated at 0003; roll the schema forward so later
        # tests see a complete schema.
        #
        # DIP-1C-5C-CORR-3: migrate EVERY app, not just accounts. Rolling accounts back
        # unapplies every migration that depends on it — the whole intelligence app —
        # and re-applying only `accounts` left those tables missing for the rest of the
        # session. Normal django_db tests never noticed; the first intelligence
        # TransactionTestCase did.
        from django.core.management import call_command
        call_command("migrate", verbosity=0)

    def test_forward_rollback_reapply_preserves_data(self):
        # Establish a known 0003 state deterministically (an earlier TransactionTestCase
        # may have flushed the migration-seeded genesis head), then seed identity data.
        _migrate(AT_0003)
        u = User.objects.create_user(username="keep-mig", password="x")
        prof = ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
        g = User.objects.create_user(username="keep-mig-g", password="x")
        assign = ReviewerRoleAssignment(
            user=u, role="DESIGN_REVIEWER", granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=30),
            grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g, grant_reason="t")
        assign.save()
        assert "accounts_decisionevent" in _tables()

        # --- rollback 0003 -> 0002: drops ONLY the two decision-chain tables ---------
        _migrate(AT_0002)
        tables = _tables()
        assert "accounts_decisionevent" not in tables
        assert "accounts_decisionchainhead" not in tables
        # identity + auth data untouched by the rollback
        assert User.objects.filter(username="keep-mig").exists()
        assert ReviewerProfile.objects.filter(pk=prof.pk).exists()
        assert ReviewerRoleAssignment.objects.filter(pk=assign.pk).exists()
        assert "auth_user" in tables and "accounts_authorizationaudit" in tables

        # --- forward 0002 -> 0003: re-creates tables + re-seeds a valid genesis -------
        _migrate(AT_0003)
        assert "accounts_decisionevent" in _tables()
        head = DecisionChainHead.objects.get(pk=1)
        assert head.is_genesis and DecisionEvent.objects.count() == 0   # zero real events
        assert verify_chain().ok
        # identity data still present after the full round trip
        assert User.objects.filter(username="keep-mig").exists()
        assert ReviewerRoleAssignment.objects.filter(pk=assign.pk).exists()
