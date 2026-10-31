"""Design Target registry (Phase A, 2026-07-08).

``get_target(name)`` returns the strategy configuring the shared pipeline for
a Design Target. Only PACKAGING is active in Phase A; unknown/blank values
fall back to it (the entire existing corpus is packaging), so the refactor is
invisible. New targets register here without touching the pipeline.
"""
from __future__ import annotations

from apps.pipeline.targets.base import DesignTarget, TargetStrategy
from apps.pipeline.targets.container import ProductContainerTarget
from apps.pipeline.targets.packaging import PackagingTarget

_REGISTRY: dict[str, TargetStrategy] = {}


def register(strategy: TargetStrategy) -> None:
    _REGISTRY[strategy.name] = strategy


def get_target(name: str | None) -> TargetStrategy:
    """Strategy for ``name``; falls back to PACKAGING for unknown/blank."""
    return _REGISTRY.get(name or "") or _REGISTRY[DesignTarget.PACKAGING.value]


from .palette import PaletteTarget  # noqa: E402
from .artwork import (DisplayStandTarget, ExhibitionBoothTarget, MarketingMaterialTarget,  # noqa: E402
                      SocialMediaTarget)

register(PackagingTarget())
register(ProductContainerTarget())
register(PaletteTarget())
# §BH55 Phase 2 (2026-09-19): the first artwork target — declared on the SDK in targets/artwork.py
register(MarketingMaterialTarget())
register(SocialMediaTarget())
register(ExhibitionBoothTarget())
register(DisplayStandTarget())
# §BH55 Phase 2: the last card reading "Coming soon" — the packaging target, for a set
from .gift_set import GiftSetTarget  # noqa: E402

register(GiftSetTarget())

__all__ = ["DesignTarget", "TargetStrategy", "get_target", "register"]
