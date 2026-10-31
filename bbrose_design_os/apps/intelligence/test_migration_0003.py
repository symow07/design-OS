from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head

from apps.accounts.models import DecisionEvent

from .models import (
    CorpusItem, DesignAssetProfile, OperationalPermissionProjection, ReviewCandidate,
    SourceArtifact,
)

LATEST = ("intelligence", "0003_review_candidates")
PRIOR = ("intelligence", "0002_corpus_browser_foundation")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


class ReviewCandidateMigrationTest(TransactionTestCase):
    def setUp(self):
        # Earlier historical migration tests deliberately finish at their own target.
        # Establish this migration's forward state independently of test ordering.
        _migrate(LATEST)

    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_reapply_is_bounded_and_seeds_no_tasks(self):
        user = get_user_model().objects.create_user(username="keep-review-migration")
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.HISTORICAL_DESIGN,
            external_key="historical:keep-review-migration")
        source = SourceArtifact.objects.create(
            source_identifier="migration-source", source_location="logical:migration",
            source_type=SourceArtifact.SourceType.FILE, sha256="1" * 64,
            parser_identifier="test", parser_version="1", source_schema_version="1")
        asset_item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.DESIGN_ASSET,
            external_key="asset:dip0c2_asset_candidate_pilot/1.0:migration")
        profile = DesignAssetProfile.objects.create(
            corpus_item=asset_item, primary_source_artifact=source,
            candidate_source_key="migration", source_manifest_entry_key="migration",
            dataset_identifier="dip0c2_asset_candidate_pilot/1.0",
            candidate_asset_kind=DesignAssetProfile.CandidateKind.UNKNOWN,
            representation_state=DesignAssetProfile.Representation.UNKNOWN,
            technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
            extraction_state="MIGRATION_TEST", dimensions_media={})
        ReviewCandidate.objects.create(
            corpus_item=item, review_type=ReviewCandidate.ReviewType.HISTORICAL_MEMORY,
            review_manifest_id="test/1.0", machine_confidence_summary={})

        _migrate(PRIOR)
        assert "intelligence_reviewcandidate" not in connection.introspection.table_names()
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert DesignAssetProfile.objects.filter(pk=profile.pk).exists()
        assert SourceArtifact.objects.filter(pk=source.pk).exists()
        assert get_user_model().objects.filter(pk=user.pk).exists()

        _migrate(LATEST)
        assert "intelligence_reviewcandidate" in connection.introspection.table_names()
        assert ReviewCandidate.objects.count() == 0
        assert DecisionEvent.objects.count() == 0
        assert OperationalPermissionProjection.objects.count() == 0
        _migrate(PRIOR)
        _migrate(LATEST)
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert DesignAssetProfile.objects.filter(pk=profile.pk).exists()
        assert ReviewCandidate.objects.count() == 0
