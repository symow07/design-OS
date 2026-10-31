from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head

from apps.core.models import Brand

from .models import CorpusItem, OperationalPermissionProjection, SourceArtifact

LATEST = ("intelligence", "0002_corpus_browser_foundation")
FOUNDATION = ("intelligence", "0001_source_foundation")


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


class IntelligenceBrowserMigrationTest(TransactionTestCase):
    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_reapply_preserves_foundation_accounts_and_legacy(self):
        user = get_user_model().objects.create_user(username="keep-browser-migration")
        brand = Brand.objects.create(name="keep-browser-brand", master_brief="keep")
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="keep:item")
        source = SourceArtifact.objects.create(
            source_identifier="keep-source", source_location="logical:keep",
            source_type=SourceArtifact.SourceType.FILE, sha256="1" * 64,
            parser_identifier="test", parser_version="1", source_schema_version="1")

        _migrate(FOUNDATION)
        tables = set(connection.introspection.table_names())
        assert "intelligence_designassetprofile" not in tables
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert SourceArtifact.objects.filter(pk=source.pk).exists()
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert Brand.objects.filter(pk=brand.pk).exists()

        _migrate(LATEST)
        tables = set(connection.introspection.table_names())
        assert "intelligence_designassetprofile" in tables
        assert "intelligence_sourcelocationobservation" in tables
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert OperationalPermissionProjection.objects.count() == 0

        _migrate(FOUNDATION)
        _migrate(LATEST)
        assert CorpusItem.objects.filter(pk=item.pk).exists()
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert Brand.objects.filter(pk=brand.pk).exists()
        assert OperationalPermissionProjection.objects.count() == 0
