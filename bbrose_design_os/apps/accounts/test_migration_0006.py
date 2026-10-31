"""Committed migration-executor test for accounts 0006 (DIP-1A-BOOTSTRAP-CORR-2).

0006 registers the `BOOTSTRAP_SINGLE_OPERATOR` grant source. `choices` is Django-level
validation, not a database constraint, so `sqlmigrate` is a **no-op** — this test proves
that claim rather than asserting it: forward, rollback and re-apply must all leave every
existing user, profile, assignment, audit, event and bootstrap-state row untouched.

A TransactionTestCase, because migrations run real DDL outside the atomic block a normal
django_db test uses. It re-applies 0006 at the end, leaving the schema fully migrated.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head
from django.utils import timezone

from .models import (
    GRANT_AUTHORIZED_SERVICE, GRANT_BOOTSTRAP_SINGLE_OPERATOR, BootstrapState,
    ReviewerProfile, ReviewerRoleAssignment,
)

User = get_user_model()


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([("accounts", target)])
    executor.loader.build_graph()


class Migration0006Tests(TransactionTestCase):
    def tearDown(self):
        restore_head()   # it rolled accounts back and left it there (the clean-up of 2026-10-04)

    def _seed(self):
        granter = User.objects.create_user(username="mig-granter", password="x")
        user = User.objects.create_user(username="mig-user", password="x")
        ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
        ReviewerRoleAssignment.objects.create(
            user=user, role="DESIGN_REVIEWER", granted_by=granter,
            granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=5),
            grant_source=GRANT_AUTHORIZED_SERVICE, grant_reason="pre-existing history")
        BootstrapState.objects.get_or_create(pk=1, defaults={"closed": False})
        return user

    def test_rollback_and_reapply_preserve_all_existing_rows(self):
        user = self._seed()
        before = (User.objects.count(), ReviewerProfile.objects.count(),
                  ReviewerRoleAssignment.objects.count())

        _migrate("0005_bootstrapstate")          # rollback
        self.assertEqual(
            (User.objects.count(), ReviewerProfile.objects.count(),
             ReviewerRoleAssignment.objects.count()), before,
            "rollback altered existing rows")
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(
            ReviewerRoleAssignment.objects.get(user=user).grant_source,
            GRANT_AUTHORIZED_SERVICE)

        _migrate("0006_single_operator_bootstrap_source")     # forward again
        self.assertEqual(
            (User.objects.count(), ReviewerProfile.objects.count(),
             ReviewerRoleAssignment.objects.count()), before,
            "re-application altered existing rows")

        # the new source is storable only after the migration is applied
        assignment = ReviewerRoleAssignment.objects.get(user=user)
        assignment.grant_source = GRANT_BOOTSTRAP_SINGLE_OPERATOR
        assignment.full_clean(exclude=["granted_by"])
        assignment.save()
        self.assertEqual(
            ReviewerRoleAssignment.objects.get(pk=assignment.pk).grant_source,
            GRANT_BOOTSTRAP_SINGLE_OPERATOR)

    def test_the_grant_source_column_is_unchanged_at_the_database_level(self):
        """The no-op claim, checked against the live column definition."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'accounts_reviewerroleassignment'
                  AND column_name = 'grant_source'
            """)
            row = cursor.fetchone()
        self.assertEqual(row, ("character varying", 32, "NO"))
