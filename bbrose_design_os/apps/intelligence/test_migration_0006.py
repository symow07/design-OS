from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head

from apps.accounts.models import DecisionEvent

from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET,
    DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    CorpusItem,
    DesignAssetProfile,
    OperationalPermissionProjection,
    SourceArtifact,
)

LATEST = ("intelligence", "0006_design_asset_dataset_scope")
PRIOR = ("intelligence", "0005_governance_projections")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


def _source(suffix):
    return SourceArtifact.objects.create(
        source_identifier=f"migration-0006:{suffix}",
        source_location=f"logical:migration-0006:{suffix}",
        source_type=SourceArtifact.SourceType.FILE,
        sha256=suffix * 64,
        parser_identifier="migration-0006-test",
        parser_version="1.0",
        source_schema_version="migration_test/1.0",
    )


def _profile(external_key, dataset_identifier, suffix):
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key=external_key,
    )
    return DesignAssetProfile.objects.create(
        corpus_item=item,
        primary_source_artifact=_source(suffix),
        candidate_source_key=f"candidate-{suffix}",
        source_manifest_entry_key=f"manifest-{suffix}",
        dataset_identifier=dataset_identifier,
        candidate_asset_kind=DesignAssetProfile.CandidateKind.MOTIF,
        representation_state=DesignAssetProfile.Representation.VECTOR,
        technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
        extraction_state="WHOLE_SOURCE_ISOLATED",
    )


class DesignAssetDatasetScopeMigrationTest(TransactionTestCase):
    def setUp(self):
        _migrate(LATEST)

    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_before_expansion_and_reapply_are_bounded(self):
        _migrate(PRIOR)
        c2 = _profile(
            "asset:migration-0006:c2",
            DIP0C2_ASSET_CANDIDATE_DATASET,
            "1",
        )
        c2_profile_id = c2.pk
        c2_item_id = c2.corpus_item_id
        before_decisions = DecisionEvent.objects.count()
        before_allowed = OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED,
        ).count()

        _migrate(LATEST)
        preserved = DesignAssetProfile.objects.get(pk=c2_profile_id)
        assert preserved.corpus_item_id == c2_item_id
        assert preserved.dataset_identifier == DIP0C2_ASSET_CANDIDATE_DATASET

        # The approved rollback contract is exercised before an expansion row exists.
        _migrate(PRIOR)
        assert DesignAssetProfile.objects.filter(pk=c2_profile_id).exists()
        _migrate(LATEST)
        assert DesignAssetProfile.objects.filter(pk=c2_profile_id).exists()

        expansion = _profile(
            "asset:migration-0006:expansion",
            DIP1B_CURATED_ASSET_EXPANSION_DATASET,
            "2",
        )
        assert expansion.dataset_identifier == DIP1B_CURATED_ASSET_EXPANSION_DATASET

        with transaction.atomic():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE intelligence_designassetprofile "
                        "SET dataset_identifier=%s WHERE corpus_item_id=%s",
                        ["future-dataset/9.9", str(expansion.pk)],
                    )
            except IntegrityError:
                transaction.set_rollback(True)
            else:
                raise AssertionError("unknown design-asset dataset was accepted")

        assert DecisionEvent.objects.count() == before_decisions
        assert OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED,
        ).count() == before_allowed
