import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PipelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pipeline"

    def ready(self):
        # Milestone 12.4: connect status-change → notification signals.
        from apps.pipeline import signals  # noqa: F401

        # Startup warning (Milestone 8.5): surface missing credentials for the
        # configured backends immediately, not mid-pipeline.
        from django.conf import settings

        if not settings.ANTHROPIC_API_KEY:
            logger.warning(
                "ANTHROPIC_API_KEY is not set — Claude stages "
                "(%s / %s: directions, prompts, QA vision, dimension "
                "estimates) will fail or degrade.",
                settings.CLAUDE_MODEL_HEAVY, settings.CLAUDE_MODEL_FAST,
            )
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is not set — image generation (%s) will fail.",
                settings.IMAGE_MODEL,
            )

        # Cost-ledger drift guard (hardening 2026-07-04): a configured Claude
        # model missing from CLAUDE_PRICES is billed at the opus-class fallback
        # (deliberate over-estimate) — surface it so someone adds the price.
        for name in (settings.CLAUDE_MODEL_HEAVY, settings.CLAUDE_MODEL_FAST):
            if name not in settings.CLAUDE_PRICES:
                logger.warning(
                    "Claude model %r is not in settings.CLAUDE_PRICES — the "
                    "cost ledger will bill it at the opus-class fallback rate "
                    "(over-estimate). Add its real price to CLAUDE_PRICES.",
                    name,
                )
