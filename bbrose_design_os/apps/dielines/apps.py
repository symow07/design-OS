from django.apps import AppConfig


class DielinesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dielines"

    def ready(self):
        # Startup policy check for the database transport (Phase 2A-6B §8):
        # the local GSS workaround never leaks into a shared deployment. (The
        # standard pipeline's activation guard left with it, 2026-10-04.)
        from . import checks  # noqa: F401
