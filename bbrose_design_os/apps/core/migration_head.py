"""The test database at the head of every app's migrations — restored, and checked.

The clean-up of 2026-10-04 (his "tests never leave the test database at an old migration"): six migration tests
restored only their own app's migration under test (intelligence 0001-0006 to their own "latest", accounts 0006 to
nothing at all, pipeline 0016 left at 0016 with the dashboard tables that depend on a later pipeline migration
dropped), so every later test in the run that needed a newer schema met an old one. A migration test now hands
its cleanup to ``restore_head()``; conftest.py checks ``at_head()`` after every database-resetting test.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def _executor():
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    return executor


def at_head():
    """True when no migration of any app is left to apply."""
    executor = _executor()
    return not executor.migration_plan(executor.loader.graph.leaf_nodes())


def restore_head():
    """Migrate every app to its latest migration, then refuse if anything is still left."""
    executor = _executor()
    executor.migrate(executor.loader.graph.leaf_nodes())
    if not at_head():
        raise AssertionError("the test database is not at the head of its migrations after restoring it")
