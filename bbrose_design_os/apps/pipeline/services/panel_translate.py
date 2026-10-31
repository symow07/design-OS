"""Back-panel label translation EN -> ES + AR (2026-07-07).

The factory back panels (e.g. EP2508) carry every consumer-facing field in
three languages inside a sticker frame. The user types English only; ONE
fast Claude call produces the Spanish and Arabic blocks at the dimension
gate. The result rides inside panel_info["translations"] and is persisted
in the spec sheet, so exports and re-exports never re-call.

Failure of any kind degrades to {} — the sticker then renders English-only.
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Fields that carry consumer copy. Codes/numbers (EAN, item no, net weight)
# and the supplier block (already multi-lingual on the source files) stay as
# typed.
TRANSLATABLE_KEYS = (
    "product_name", "description", "ingredients", "how_to_use", "warnings",
)

_MAX_LEN = 1200   # per translated value, mirrors panel_info sanitization caps

_TRANSLATE_SYSTEM = """You are a professional cosmetics-label translator.
You translate English packaging copy into label-register Spanish and Modern
Standard Arabic for a printed back panel.

Rules:
- INCI ingredient names (MICA, TALC, CI 77491, TOCOPHERYL ACETATE, ...) are
  international nomenclature — copy them UNCHANGED; translate only the
  connective words around them.
- Keep the register concise and factual, exactly like a printed label.
- Preserve numbers, units and trademarks as written.

Respond ONLY with valid JSON of this exact shape (include only the keys you
were given):
{
  "es": {"product_name": "...", "description": "...", ...},
  "ar": {"product_name": "...", "description": "...", ...}
}"""


def translate_panel_info(panel_info: dict, task=None, log=None) -> dict:
    """One Claude call -> {"es": {...}, "ar": {...}}. {} on any failure."""
    log = log or (lambda msg, data=None, level="info": None)

    if not settings.PANEL_TRANSLATE_ENABLED or not settings.ANTHROPIC_API_KEY:
        return {}
    source = {
        k: panel_info.get(k, "").strip()
        for k in TRANSLATABLE_KEYS if (panel_info.get(k) or "").strip()
    }
    if not source:
        return {}

    try:
        import json

        from apps.pipeline.services.claude_service import call_claude, extract_json

        response = call_claude(
            _TRANSLATE_SYSTEM,
            "Translate these label fields:\n" + json.dumps(source, ensure_ascii=False),
            max_tokens=2500,
            model=settings.CLAUDE_MODEL_FAST,
            operation="panel_translation",
        )
        data = extract_json(response)
        result = {}
        for lang in ("es", "ar"):
            block = data.get(lang)
            if not isinstance(block, dict):
                continue
            clean = {
                k: str(v).strip()[:_MAX_LEN]
                for k, v in block.items()
                if k in TRANSLATABLE_KEYS and isinstance(v, str) and v.strip()
            }
            # INCI is Latin-only international nomenclature; the factory
            # reference never repeats it in the Arabic block.
            if lang == "ar":
                clean.pop("ingredients", None)
            if clean:
                result[lang] = clean
        if result:
            log(
                "ARIA: label copy translated for the sticker "
                f"({' + '.join(sorted(result))}, {len(source)} field(s))"
            )
        return result
    except Exception as exc:  # noqa: BLE001 — advisory; sticker degrades to EN
        if isinstance(exc, _RescueBudgetError):
            raise
        logger.warning("panel translation failed: %s", exc)
        log("ARIA: label translation failed — sticker renders English only",
            level="warning")
        return {}
