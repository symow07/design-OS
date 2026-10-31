"""Concurrent appends must serialise on the chain head — no fork (DIP-1A-4).

A TransactionTestCase (real commits, real threads, separate PostgreSQL connections) so the
`select_for_update` lock is genuinely exercised. A barrier makes both threads enter the
append together; the riskiest case is the FIRST append on the empty chain, where both
threads race for sequence 1.
"""
from __future__ import annotations

import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from . import authz_policy as authz
from .authorization import authorize_actor
from .decision_chain import append_decision, verify_chain
from .models import (
    _CHAIN_WRITE_TOKEN,
    CHAIN_HEAD_SCHEMA,
    DecisionChainHead,
    DecisionEvent,
    GRANT_AUTHORIZED_SERVICE,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

User = get_user_model()
ACTION = authz.CONFIRM_DESIGN_QUALITY
ROLE = authz.DESIGN_REVIEWER


class ConcurrentAppendTests(TransactionTestCase):
    def setUp(self):
        # TransactionTestCase flushes the DB between tests, wiping the migration-seeded
        # genesis head; re-seed it explicitly (via the write capability the service uses).
        if not DecisionChainHead.objects.filter(pk=1).exists():
            DecisionChainHead(
                id=1, chain_id="global", terminal_sequence_number=0,
                terminal_event_hash=None, event_count=0,
                schema_version=CHAIN_HEAD_SCHEMA, signing_key_id="", head_signature=""
            ).save(_chain_write_token=_CHAIN_WRITE_TOKEN)

    def _make_reviewer(self, name):
        u = User.objects.create_user(username=name, password="x")
        ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
        g = User.objects.create_user(username=f"{name}-g", password="x")
        ReviewerRoleAssignment(
            user=u, role=ROLE, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=30),
            grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g, grant_reason="t").save()
        return u

    def _run_two(self, worker):
        barrier = threading.Barrier(2)
        errors: list = []

        def wrapped(idx):
            try:
                worker(idx, barrier)
            except Exception as e:  # noqa: BLE001 - surfaced to the assertions below
                errors.append(e)
            finally:
                connection.close()          # each thread has its own connection

        threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        return errors

    def test_first_appends_do_not_fork_the_empty_chain(self):
        u0 = self._make_reviewer("cc0")
        u1 = self._make_reviewer("cc1")
        users = [u0, u1]

        def worker(idx, barrier):
            user = users[idx]
            authorize_actor(user, ACTION)   # sanity: this actor is authorized
            barrier.wait()                  # both enter append together -> real contention
            append_decision(user=user, action=ACTION, payload={"who": idx})

        errors = self._run_two(worker)
        assert errors == [], errors
        seqs = sorted(DecisionEvent.objects.values_list("sequence_number", flat=True))
        assert seqs == [1, 2], seqs                 # distinct, monotonic, no fork
        head = DecisionChainHead.objects.get(pk=1)
        assert head.event_count == 2
        assert verify_chain().ok, verify_chain().problems

    def test_concurrent_identical_retries_create_one_event(self):
        u = self._make_reviewer("cc-same")

        def worker(idx, barrier):
            authorize_actor(u, ACTION)
            barrier.wait()
            append_decision(user=u, action=ACTION, payload={"n": 1},
                            event_id="shared-evt")

        errors = self._run_two(worker)
        assert errors == [], errors
        assert DecisionEvent.objects.filter(event_id="shared-evt").count() == 1
        assert verify_chain().ok
