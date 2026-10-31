"""Public carton-style registry (Milestone 12.1).

A thin, import-safe surface over the engine's ``_STYLE_CONFIG`` and the
schema's per-style ``_STRUCTURAL_RULES`` so the API and the dashboard can
present the available carton styles (and their dimension constraints)
without reaching into the geometry internals.

The geometry itself lives in ``engine.py`` — each style is a coordinate
recipe selected by ``_StyleConfig``. Straight tuck end is the only style
backed by a measured reference file; the others are flagged ``provisional``
and, per the AI dieline contract, must be human-confirmed at the dimension
gate before release.
"""
from __future__ import annotations

from apps.dielines.geometry.engine import _STYLE_CONFIG
from apps.dielines.models import TemplateType
from apps.dielines.validators.schema import _STRUCTURAL_RULES

_DISPLAY_NAMES = dict(TemplateType.choices)


def available_styles() -> list[dict]:
    """Metadata for every carton style, ordered production-ready first."""
    out: list[dict] = []
    for structure_type, cfg in _STYLE_CONFIG.items():
        rules = _STRUCTURAL_RULES.get(structure_type, {})
        out.append({
            "structure_type": structure_type,
            "display_name": _DISPLAY_NAMES.get(structure_type, structure_type),
            "provisional": cfg.provisional,
            "bottom_mode": cfg.bottom_mode,
            "constraints": {
                "height_gt_width": rules.get("h_gt_w", False),
                "height_gt_depth": rules.get("h_gt_d", False),
                "max_depth_over_width": rules.get("max_d_over_w"),
            },
        })
    # Production-ready styles first, then provisional.
    out.sort(key=lambda s: (s["provisional"], s["structure_type"]))
    return out


def is_supported(structure_type: str) -> bool:
    return structure_type in _STYLE_CONFIG
