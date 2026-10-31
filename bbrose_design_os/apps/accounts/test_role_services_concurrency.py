"""Concurrent protected role operations serialise without deadlock (DIP-1A-5A).

The documented lock order is: target rows (assignment/profile) -> chain head -> bootstrap
state. A concurrent grant and revoke touching the same target's rows must both commit,
produce distinct chain events, and leave a valid signed chain — no fork, no deadlock. A
lock-order test that doesn't actually contend proves nothing, so both threads meet at a
barrier before entering their service call.
"""
from __future__ import annotations

import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from . import authz_policy as authz
from . import role_services as RS
from .decision_chain import verify_chain
from .models import (
    _CHAIN_WRITE_TOKEN,
    CHAIN_HEAD_SCHEMA,
    GRANT_AUTHORIZED_SERVICE,
    BootstrapState,
    DecisionChainHead,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

User = get_user_model()
DAY = timezone.timedelta(days=1)


class ConcurrentRoleOpsTests(TransactionTestCase):
    def setUp(self):
        # re-seed the migration singletons a prior TransactionTestCase may have flushed
        if not DecisionChainHead.objects.filter(pk=1).exists():
            DecisionChainHead(id=1, chain_id="global", terminal_sequence_number=0,
                              terminal_event_hash=None, event_count=0,
                              schema_version=CHAIN_HEAD_SCHEMA, signing_key_id="",
                              head_signature="").save(_chain_write_token=_CHAIN_WRITE_TOKEN)
        BootstrapState.objects.get_or_create(pk=1, defaults={"closed": False})

    def _actor(self, name):
        u = User.objects.create_user(username=name, password="x")
        ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
        g = User.objects.create_user(username=f"{name}-g", password="x")
        ReviewerRoleAssignment(
            user=u, role=authz.BRAND_ADMIN, granted_at=timezone.now(),
            expires_at=timezone.now() + 30 * DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
            granted_by=g, grant_reason="seed").save()
        return u

    def test_concurrent_grant_and_revoke_do_not_deadlock_or_fork(self):
        a1 = self._actor("granter")
        a2 = self._actor("revoker")
        t = User.objects.create_user(username="tgt", password="x")
        ReviewerProfile.objects.create(user=t, reviewer_enabled=True)
        g = User.objects.create_user(username="tgt-g", password="x")
        existing = ReviewerRoleAssignment(
            user=t, role=authz.DESIGN_REVIEWER, granted_at=timezone.now(),
            expires_at=timezone.now() + 30 * DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
            granted_by=g, grant_reason="to be revoked")
        existing.save()

        barrier = threading.Barrier(2)
        errors: list = []

        def grant():
            try:
                barrier.wait()
                RS.grant_reviewer_role(actor=a1, target_user=t,
                                       role=authz.LEGAL_REVIEWER,
                                       expires_at=timezone.now() + 30 * DAY,
                                       reason="concurrent grant")
            except Exception as e:  # noqa: BLE001
                errors.append(("grant", e))
            finally:
                connection.close()

        def revoke():
            try:
                barrier.wait()
                RS.revoke_reviewer_role(actor=a2, assignment=existing,
                                        reason="concurrent revoke")
            except Exception as e:  # noqa: BLE001
                errors.append(("revoke", e))
            finally:
                connection.close()

        threads = [threading.Thread(target=grant), threading.Thread(target=revoke)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=20)

        assert errors == [], errors                       # no deadlock, both succeeded
        assert DecisionEvent.objects.count() == 2         # one grant + one revoke event
        seqs = sorted(DecisionEvent.objects.values_list("sequence_number", flat=True))
        assert seqs == [1, 2]                             # serialised, no fork
        existing.refresh_from_db()
        assert existing.revoked_at is not None
        assert ReviewerRoleAssignment.objects.filter(
            user=t, role=authz.LEGAL_REVIEWER, revoked_at__isnull=True).exists()
        assert verify_chain().ok, verify_chain().problems
