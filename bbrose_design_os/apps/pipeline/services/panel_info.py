"""Info-panel (regulatory back face) data assembly (2026-07-06).

One place builds the dict that the components .ai and the on-screen preview
render: defaults come from the Product + Brand records, and the reviewer can
edit everything at the dimension gate (the UI sends an override that merges
on top). Keys are stable — the exporters and the dimension-gate form share
them.
"""
from __future__ import annotations

PANEL_INFO_KEYS = (
    "product_name", "description", "ingredients", "how_to_use", "warnings",
    "net_weight", "item_no", "barcode_ean", "qr_url", "regulatory_text",
)

# Sane per-field caps so a UI override can't balloon the spec JSON.
_MAX_LEN = {"barcode_ean": 13, "item_no": 40, "net_weight": 60,
            "product_name": 120, "qr_url": 300}
_DEFAULT_MAX = 2000


def build_panel_info(task) -> dict:
    """Defaults from the Product + Brand records (all optional)."""
    product = getattr(task, "product", None)
    brand = getattr(task, "brand", None)
    info = {
        # Title: the PRODUCT name only — never the raw task text (an early
        # version printed 'A RETAIL CARTON FOR A...' on the panel).
        "product_name": getattr(product, "name", "") if product else "",
        "description": getattr(product, "description", "") if product else "",
        "ingredients": getattr(product, "ingredients", "") if product else "",
        "how_to_use": getattr(product, "how_to_use", "") if product else "",
        "warnings": getattr(product, "warnings_text", "") if product else "",
        "net_weight": getattr(product, "net_weight", "") if product else "",
        "item_no": getattr(product, "item_no", "") if product else "",
        "barcode_ean": getattr(product, "barcode_ean", "") if product else "",
        "qr_url": ((getattr(product, "qr_url", "") if product else "")
                   or getattr(brand, "website", "")),
        "regulatory_text": getattr(brand, "regulatory_text", ""),
    }
    # §BH55 Phase 2: the target speaks for its own panel — a gift set's content is the set's, not one piece's
    from apps.pipeline.targets import get_target
    return get_target(getattr(task, "design_target", None)).panel_defaults(task, info)


def merge_panel_info(task, override: dict | None) -> dict:
    """Defaults merged with a sanitized UI override (unknown keys dropped)."""
    info = build_panel_info(task)
    for key, value in (override or {}).items():
        if key not in PANEL_INFO_KEYS or not isinstance(value, str):
            continue
        info[key] = value.strip()[: _MAX_LEN.get(key, _DEFAULT_MAX)]
    return info
