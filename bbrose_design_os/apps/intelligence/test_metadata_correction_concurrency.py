"""Two concurrent corrections of the same event must not both become effective —
DIP-1C-5C-CORR-3.

A `TransactionTestCase` with real threads and separate connections, so the row lock on the
supersession target is genuinely exercised. UI disabling is not a solution: the guard has to
hold when two POSTs arrive at once.
"""
from __future__ import annotations

import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    _CHAIN_WRITE_TOKEN, CHAIN_HEAD_SCHEMA, DecisionChainHead, DecisionEvent,
    GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from apps.accounts.decision_chain import verify_chain
from .metadata_history import EFFECTIVE, resolve_effective_assertion_from_verified_history
from .models import CorpusItem, EvidenceReference, SourceArtifact, DesignAssetProfile
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .semantic_metadata_service import (
    REVIEW_SCOPE_ID, correct_human_semantic_metadata, record_human_semantic_metadata,
)

User = get_user_model()
KEY = "4" * 32


@override_settings(DECISION_EVENT_HMAC_KEYS={"corr3-conc": KEY},
                   DECISION_EVENT_ACTIVE_KEY_ID="corr3-conc")
class _MetadataConcurrencyBase(TransactionTestCase):
    """Shared fixture: a scoped item with SOURCE_FILE + page-unit evidence and one
    recorded metadata event. Subclasses add the conflict they need."""

    __test__ = False

    def setUp(self):
        signing.reset_registry()
        if not DecisionChainHead.objects.filter(pk=1).exists():
            DecisionChainHead(
                id=1, chain_id="global", terminal_sequence_number=0,
                terminal_event_hash=None, event_count=0,
                schema_version=CHAIN_HEAD_SCHEMA, signing_key_id="", head_signature=""
            ).save(_chain_write_token=_CHAIN_WRITE_TOKEN)
        self.addCleanup(signing.reset_registry)
        self.reviewer = self._reviewer()
        self.item, self.source_ref, self.unit = self._item()
        self.original = record_human_semantic_metadata(
            user=self.reviewer, payload=self._payload([str(self.unit.pk)]))

    def _reviewer(self):
        granter = User.objects.create_user(username="conc-granter")
        user = User.objects.create_user(username="conc-reviewer")
        ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
        ReviewerRoleAssignment.objects.create(
            user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
            granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
            grant_source=GRANT_TEST_FIXTURE, grant_reason="concurrency test")
        return user

    def _item(self):
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:conc-0001")
        source = SourceArtifact.objects.create(
            source_identifier="src-conc", source_location="logical:conc",
            source_type=SourceArtifact.SourceType.FILE, sha256="a" * 64,
            parser_identifier="test", parser_version="1", source_schema_version="1")
        source_ref = EvidenceReference.objects.create(
            corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
            locator={"path": "bounded/conc.ai"},
            locator_schema_version="source_file/1.0", evidence_hash="b" * 64)
        unit = EvidenceReference.objects.create(
            corpus_item=item, source_artifact=source, evidence_kind="FILE_PAGE_UNIT",
            locator={"page": 0, "unit_key": "conc-p0-u06"},
            locator_schema_version="file_page/1.0", evidence_hash="c" * 64)
        DesignAssetProfile.objects.create(
            corpus_item=item, primary_source_artifact=source,
            candidate_source_key=item.pk.hex[:16],
            source_manifest_entry_key=f"test:{item.pk}",
            dataset_identifier=DIP0C2_ASSET_CANDIDATE_DATASET,
            candidate_asset_kind=DesignAssetProfile.CandidateKind.UNKNOWN,
            representation_state=DesignAssetProfile.Representation.UNKNOWN,
            technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
            extraction_state="TEST_FIXTURE", dimensions_media={})
        return item, source_ref, unit

    def _payload(self, evidence_ids, supersedes=None):
        payload = {
            "corpus_item_uuid": str(self.item.pk),
            "bundle": {"design_styles": ["MINIMAL"]},
            "evidence_reference_ids": evidence_ids,
            "review_scope_id": REVIEW_SCOPE_ID,
        }
        if supersedes:
            payload["supersedes_event_id"] = supersedes
        return payload

    def _noop(self):
        pass


@override_settings(DECISION_EVENT_HMAC_KEYS={"corr3-conc": KEY},
                   DECISION_EVENT_ACTIVE_KEY_ID="corr3-conc")
class ConcurrentCorrectionTests(_MetadataConcurrencyBase):
    __test__ = True

    def test_two_corrections_of_the_same_event_produce_one_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            try:
                barrier.wait(timeout=10)
                correct_human_semantic_metadata(
                    user=self.reviewer,
                    payload=self._payload([str(self.source_ref.pk)],
                                          supersedes=self.original.event_id))
                outcomes.append("ok")
            except Exception as exc:                       # noqa: BLE001 — asserted below
                outcomes.append(type(exc).__name__)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive(), "correction thread deadlocked")

        self.assertEqual(outcomes.count("ok"), 1, f"both corrections committed: {outcomes}")
        corrections = DecisionEvent.objects.filter(
            action=authz.CORRECT_HUMAN_SEMANTIC_METADATA)
        self.assertEqual(corrections.count(), 1)
        self.assertEqual(DecisionEvent.objects.count(), 2, "the chain forked")
        resolved = resolve_effective_assertion_from_verified_history(self.item)
        self.assertEqual(resolved.state, EFFECTIVE, resolved.reason)
        self.assertEqual(resolved.event.event_id, corrections.first().event_id)


@override_settings(DECISION_EVENT_HMAC_KEYS={"corr4-conc": "5" * 32},
                   DECISION_EVENT_ACTIVE_KEY_ID="corr4-conc")
class ConcurrentConflictResolutionTests(_MetadataConcurrencyBase):
    __test__ = True

    """Two resolutions of the same active set: one winner, no duplicate resolution."""

    def setUp(self):
        super().setUp()
        from unittest import mock

        from .metadata_history import NONE, EffectiveAssertion
        from .semantic_metadata_service import record_human_semantic_metadata
        with mock.patch(
                "apps.intelligence.metadata_history."
                "resolve_effective_assertion_from_verified_history",
                lambda item: EffectiveAssertion(NONE, "NO_METADATA_EVENT")):
            self.duplicate = record_human_semantic_metadata(
                user=self.reviewer, payload=self._payload([str(self.unit.pk)]))

    def test_two_resolutions_of_the_same_active_set_produce_one_winner(self):
        from .metadata_history import (
            EFFECTIVE, resolve_effective_assertion_from_verified_history,
        )
        from .semantic_metadata_service import (
            REVIEW_SCOPE_ID, resolve_human_semantic_metadata_conflict,
        )
        active = resolve_effective_assertion_from_verified_history(self.item)
        self.assertEqual(active.reason, "MULTIPLE_ACTIVE_METADATA_EVENTS")
        event_ids = list(active.active_event_ids)

        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            try:
                barrier.wait(timeout=10)
                resolve_human_semantic_metadata_conflict(
                    user=self.reviewer,
                    payload={
                        "corpus_item_uuid": str(self.item.pk),
                        "bundle": {"design_styles": ["MINIMAL"]},
                        "evidence_reference_ids": [str(self.source_ref.pk)],
                        "review_scope_id": REVIEW_SCOPE_ID,
                        "resolved_event_ids": event_ids,
                        "resolution_reason":
                            "DUPLICATE_ACTIVE_EVENTS_FROM_STALE_APPLICATION_PROCESS",
                        "incident_type": "STALE_SERVER_DUPLICATE_RECORD_RECOVERY",
                        "reviewer_explanation": "concurrent resolution test",
                    })
                outcomes.append("ok")
            except Exception as exc:                       # noqa: BLE001 — asserted below
                outcomes.append(type(exc).__name__)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive(), "resolution thread deadlocked")

        self.assertEqual(outcomes.count("ok"), 1, f"both resolutions committed: {outcomes}")
        resolutions = DecisionEvent.objects.filter(
            action=authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT)
        self.assertEqual(resolutions.count(), 1)
        self.assertTrue(verify_chain().ok)
        resolved = resolve_effective_assertion_from_verified_history(self.item)
        self.assertEqual(resolved.state, EFFECTIVE, resolved.reason)
        self.assertEqual(resolved.event.event_id, resolutions.first().event_id)
