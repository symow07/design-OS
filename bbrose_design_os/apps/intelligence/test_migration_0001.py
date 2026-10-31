from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.migration_head import restore_head

from apps.core.models import Brand

LATEST = ("intelligence", "0001_source_foundation")
ZERO = ("intelligence", None)


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])


class IntelligenceFoundationMigrationTest(TransactionTestCase):
    def tearDown(self):
        restore_head()   # every app at its latest, checked (the clean-up of 2026-10-04)

    def test_forward_rollback_reapply_preserves_accounts_and_legacy_data(self):
        User = get_user_model()
        user = User.objects.create_user(username="keep-intelligence", password="x")
        brand = Brand.objects.create(name="keep-brand", master_brief="keep")

        _migrate(ZERO)
        tables = set(connection.introspection.table_names())
        assert not any(name.startswith("intelligence_") for name in tables)
        assert User.objects.filter(pk=user.pk).exists()
        assert Brand.objects.filter(pk=brand.pk).exists()

        _migrate(LATEST)
        tables = set(connection.introspection.table_names())
        assert "intelligence_corpusitem" in tables
        assert "intelligence_operationalpermissionprojection" in tables
        from .models import CorpusItem, OperationalPermissionProjection
        assert CorpusItem.objects.count() == 0
        assert OperationalPermissionProjection.objects.count() == 0

        _migrate(ZERO)
        _migrate(LATEST)
        assert User.objects.filter(pk=user.pk).exists()
        assert Brand.objects.filter(pk=brand.pk).exists()
        assert OperationalPermissionProjection.objects.count() == 0
