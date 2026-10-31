from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        # Registers the decision-event signing system check (DIP-1A-1).
        from .security import checks  # noqa: F401
        # Registers the authorization-policy-source check (DIP-1A-2).
        from . import checks as _policy_checks  # noqa: F401
