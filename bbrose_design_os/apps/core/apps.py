from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        # Startup migration-drift surface (ops.migration_guard). Importing it
        # here is what REGISTERS it — a checks module that nothing imports is a
        # guard wired to nothing, which is the §AA shape wearing a green suite.
        # Asserted rather than assumed, in
        # StartupMigrationDriftSurfaceTests::
        #     test_the_check_is_registered_by_a_BARE_django_setup
        # That pointer read ..._and_not_merely_defined until 2026-08-22 — the
        # test's FIRST name, renamed in the very commit that added this
        # comment. A comment naming a test that does not exist; found by an
        # independent audit, not by the suite, because nothing checks that a
        # code comment names a real test.
        from . import checks  # noqa: F401
