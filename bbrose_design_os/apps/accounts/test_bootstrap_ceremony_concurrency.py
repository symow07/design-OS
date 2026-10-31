"""Concurrent single-operator ceremonies must serialise — DIP-1A-BOOTSTRAP-CORR-2.

A `TransactionTestCase` (real commits, real threads, separate PostgreSQL connections) so
the `select_for_update` locks are genuinely exercised. Two cases matter and they lock on
different rows: two ceremonies against the SAME account serialise on the user row, and two
against DIFFERENT accounts serialise on the chain head. Exactly one may win either way, and
bootstrap must close exactly once.
"""
from __future__ import annotations

import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings

from . import authz_policy as authz
from . import bootstrap_registry as reg
from .bootstrap_ceremony import perform_single_operator_ceremony
from .decision_chain import verify_chain
from .models import (
    _CHAIN_WRITE_TOKEN, CHAIN_HEAD_SCHEMA, BootstrapState, DecisionChainHead,
    DecisionEvent, ReviewerRoleAssignment,
)
from .security import signing

User = get_user_model()
KEY = "8" * 32


@override_settings(
    BOOTSTRAP_ENABLED=True, BOOTSTRAP_SINGLE_OPERATOR_ENABLED=True, DEBUG=True,
    ENVIRONMENT="LOCAL_DEVELOPMENT",
    DECISION_EVENT_HMAC_KEYS={"ceremony-concurrency": KEY},
    DECISION_EVENT_ACTIVE_KEY_ID="ceremony-concurrency")
class ConcurrentCeremonyTests(TransactionTestCase):
    def setUp(self):
        signing.reset_registry()
        # TransactionTestCase flushes between tests, wiping the migration-seeded singletons
        if not DecisionChainHead.objects.filter(pk=1).exists():
            DecisionChainHead(
                id=1, chain_id="global", terminal_sequence_number=0,
                terminal_event_hash=None, event_count=0,
                schema_version=CHAIN_HEAD_SCHEMA, signing_key_id="", head_signature=""
            ).save(_chain_write_token=_CHAIN_WRITE_TOKEN)
        BootstrapState.objects.get_or_create(pk=1, defaults={"closed": False})
        self.settings_patch = override_settings(
            LOCAL_DEVELOPMENT_DATABASES=[connection.settings_dict["NAME"]])
        self.settings_patch.enable()
        self.addCleanup(self.settings_patch.disable)
        self.addCleanup(signing.reset_registry)

    def _operator(self, name):
        return User.objects.create_user(
            username=name, password="x", is_superuser=True, is_staff=True)

    def _run_two(self, first_user, second_user):
        barrier = threading.Barrier(2)
        outcomes: list = []

        def worker(user):
            try:
                barrier.wait(timeout=10)
                result = perform_single_operator_ceremony(
                    authenticated_user=user, role=authz.DESIGN_REVIEWER,
                    expires_days=14, reason="concurrency test",
                    account_control_basis=reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE)
                outcomes.append(("ok", result.status))
            except Exception as exc:                     # noqa: BLE001 - recorded, asserted
                outcomes.append(("error", type(exc).__name__))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(user,))
                   for user in (first_user, second_user)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive(), "ceremony thread deadlocked")
        return outcomes

    def _assert_exactly_one_ceremony(self):
        events = DecisionEvent.objects.filter(
            action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE)
        self.assertEqual(events.count(), 1, "more than one ceremony committed")
        self.assertEqual(DecisionEvent.objects.count(), 1, "the chain forked")
        self.assertEqual(ReviewerRoleAssignment.objects.count(), 1)
        state = BootstrapState.objects.get(pk=1)
        self.assertTrue(state.closed)
        self.assertEqual(state.closed_by_event_id, events.first().pk)
        self.assertEqual(state.break_glass_count, 0)
        self.assertTrue(verify_chain().ok)

    def test_two_ceremonies_against_the_same_account(self):
        operator = self._operator("same-target")
        outcomes = self._run_two(operator, operator)
        # the loser either fails closed or reconciles as ALREADY_COMPLETED — never a
        # second event
        statuses = [status for kind, status in outcomes if kind == "ok"]
        self.assertIn("PERFORMED", statuses)
        self.assertEqual(len(outcomes), 2)
        self._assert_exactly_one_ceremony()

    def test_two_ceremonies_against_different_accounts(self):
        first = self._operator("target-one")
        second = self._operator("target-two")
        outcomes = self._run_two(first, second)
        performed = [s for kind, s in outcomes if kind == "ok" and s == "PERFORMED"]
        self.assertEqual(len(performed), 1, "both ceremonies committed")
        self.assertEqual(len(outcomes), 2)
        self._assert_exactly_one_ceremony()
