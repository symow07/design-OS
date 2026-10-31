from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head
from django.utils import timezone

from apps.accounts.models import DecisionEvent

from .models import (
    _PROJECTION_WRITE_TOKEN,
    CorpusItem,
    GovernanceDecisionProjection,
    GovernanceProjectionGeneration,
    GovernanceProjectionPublicationState,
    IntelligenceProjectionGeneration,
    OperationalPermissionProjection,
    ProjectionPublicationState,
    ReviewCandidate,
    SourceArtifact,
)

LATEST = ("intelligence", "0005_governance_projections")
PRIOR = ("intelligence", "0004_human_assertion_projections")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


class GovernanceProjectionMigrationTest(TransactionTestCase):
    def setUp(self):
        _migrate(LATEST)

    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_reapply_preserves_existing_intelligence_and_seeds_nothing(
            self):
        source = SourceArtifact.objects.create(
            source_identifier="governance-migration-source",
            source_location="logical:governance-migration",
            source_type=SourceArtifact.SourceType.FILE, sha256="5" * 64,
            parser_identifier="test", parser_version="1", source_schema_version="1")
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.BRAND_ASSET,
            external_key="brand:governance-migration")
        candidate = ReviewCandidate.objects.create(
            corpus_item=item, review_type=ReviewCandidate.ReviewType.BRAND_IDENTITY,
            review_manifest_id="governance-migration/1.0",
            machine_confidence_summary={})
        generation = IntelligenceProjectionGeneration.objects.create(
            projector_identifier="migration.preserved", projector_version="1",
            projection_schema_version="human_assertion_projection/1.0",
            evaluation_timestamp=timezone.now())
        now = timezone.now()
        IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).update(
            status=IntelligenceProjectionGeneration.Status.PUBLISHED,
            completed_at=now, published_at=now)
        generation.refresh_from_db()
        publication = ProjectionPublicationState(
            id=1, current_generation=generation, published_chain_head_hash="",
            published_terminal_sequence=0, projector_identifier="migration.preserved",
            projector_version="1",
            projection_schema_version="human_assertion_projection/1.0",
            published_at=now)
        publication.save(
            _projection_write_token=_PROJECTION_WRITE_TOKEN, force_insert=True)

        _migrate(PRIOR)
        tables = set(connection.introspection.table_names())
        assert "intelligence_governanceprojectiongeneration" not in tables
        assert "intelligence_governancedecisionprojection" not in tables
        assert "intelligence_governanceprojectionpublicationstate" not in tables
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()
        assert SourceArtifact.objects.filter(pk=source.pk).exists()
        assert IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).exists()
        assert ProjectionPublicationState.objects.filter(pk=1).exists()

        _migrate(LATEST)
        tables = set(connection.introspection.table_names())
        assert "intelligence_governanceprojectiongeneration" in tables
        assert "intelligence_governancedecisionprojection" in tables
        assert "intelligence_governanceprojectionpublicationstate" in tables
        assert GovernanceProjectionGeneration.objects.count() == 0
        assert GovernanceDecisionProjection.objects.count() == 0
        assert GovernanceProjectionPublicationState.objects.count() == 0
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()
        assert IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).exists()
        assert ProjectionPublicationState.objects.filter(pk=1).exists()
        assert DecisionEvent.objects.count() == 0
        assert not OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).exists()

        _migrate(PRIOR)
        _migrate(LATEST)
        assert GovernanceProjectionGeneration.objects.count() == 0
        assert GovernanceDecisionProjection.objects.count() == 0
        assert GovernanceProjectionPublicationState.objects.count() == 0
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()
        assert IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).exists()
        assert ProjectionPublicationState.objects.filter(pk=1).exists()
