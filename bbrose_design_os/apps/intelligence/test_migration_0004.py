from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head

from apps.accounts.models import DecisionEvent

from .models import (
    CorpusItem, DesignAssetProfile, HumanAssertionProjection,
    IntelligenceProjectionGeneration, OperationalPermissionProjection,
    ProjectionPublicationState, ReviewCandidate, SourceArtifact,
)

LATEST = ("intelligence", "0004_human_assertion_projections")
PRIOR = ("intelligence", "0003_review_candidates")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


class HumanAssertionProjectionMigrationTest(TransactionTestCase):
    def setUp(self):
        _migrate(LATEST)

    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_reapply_preserves_inputs_and_seeds_nothing(self):
        source = SourceArtifact.objects.create(
            source_identifier="projection-migration-source",
            source_location="logical:projection-migration",
            source_type=SourceArtifact.SourceType.FILE, sha256="4" * 64,
            parser_identifier="test", parser_version="1", source_schema_version="1")
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.DESIGN_ASSET,
            external_key="asset:projection-migration")
        profile = DesignAssetProfile.objects.create(
            corpus_item=item, primary_source_artifact=source,
            candidate_source_key="projection-migration",
            source_manifest_entry_key="projection-migration",
            dataset_identifier="dip0c2_asset_candidate_pilot/1.0",
            candidate_asset_kind=DesignAssetProfile.CandidateKind.UNKNOWN,
            representation_state=DesignAssetProfile.Representation.UNKNOWN,
            technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
            extraction_state="MIGRATION_TEST", dimensions_media={})
        candidate = ReviewCandidate.objects.create(
            corpus_item=item, review_type=ReviewCandidate.ReviewType.DESIGN_ASSET,
            review_manifest_id="projection-migration/1.0",
            machine_confidence_summary={})

        _migrate(PRIOR)
        tables = set(connection.introspection.table_names())
        assert "intelligence_intelligenceprojectiongeneration" not in tables
        assert "intelligence_humanassertionprojection" not in tables
        assert "intelligence_projectionpublicationstate" not in tables
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert DesignAssetProfile.objects.filter(pk=profile.pk).exists()
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()

        _migrate(LATEST)
        tables = set(connection.introspection.table_names())
        assert "intelligence_intelligenceprojectiongeneration" in tables
        assert "intelligence_humanassertionprojection" in tables
        assert "intelligence_projectionpublicationstate" in tables
        assert IntelligenceProjectionGeneration.objects.count() == 0
        assert HumanAssertionProjection.objects.count() == 0
        assert ProjectionPublicationState.objects.count() == 0
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()
        assert DecisionEvent.objects.count() == 0
        assert not OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).exists()

        _migrate(PRIOR)
        _migrate(LATEST)
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert DesignAssetProfile.objects.filter(pk=profile.pk).exists()
        assert ReviewCandidate.objects.filter(pk=candidate.pk).exists()
        assert IntelligenceProjectionGeneration.objects.count() == 0
        assert HumanAssertionProjection.objects.count() == 0
        assert ProjectionPublicationState.objects.count() == 0
