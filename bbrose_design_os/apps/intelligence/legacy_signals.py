"""Read-only diagnostics for authority that remains outside the intelligence boundary."""
from __future__ import annotations

import dataclasses
import os

from django.conf import settings

LEGACY_SIGNAL_NON_AUTHORITATIVE = "LEGACY_SIGNAL_NON_AUTHORITATIVE"


@dataclasses.dataclass(frozen=True)
class LegacySignal:
    name: str
    classification: str
    observed_value: object
    reason_code: str = LEGACY_SIGNAL_NON_AUTHORITATIVE


def characterize_legacy_signals():
    from apps.core.models import (
        STATUS_CANONICAL, AestheticLanguage, ColorSystem, DesignReference, MaterialSystem)
    from apps.pipeline.models import GeneratedImage, PackagingOutput

    return (
        LegacySignal("active_design_references", "LEGACY_RETRIEVAL",
                     DesignReference.objects.filter(active=True).count()),
        LegacySignal("approved_generated_images", "LEGACY_AUTOMATIC_INPUT",
                     GeneratedImage.objects.filter(is_approved=True).count()),
        LegacySignal("canonical_color_systems", "LEGACY_AUTOMATIC_INPUT",
                     ColorSystem.objects.filter(status=STATUS_CANONICAL).count()),
        LegacySignal("canonical_aesthetic_languages", "LEGACY_AUTOMATIC_INPUT",
                     AestheticLanguage.objects.filter(status=STATUS_CANONICAL).count()),
        LegacySignal("approved_material_systems", "LEGACY_AUTOMATIC_INPUT",
                     MaterialSystem.objects.filter(status="approved").count()),
        LegacySignal("brand_logo_path_present", "LEGACY_AUTOMATIC_INPUT",
                     bool(settings.BRAND_LOGO_PATH
                          and os.path.exists(settings.BRAND_LOGO_PATH))),
        LegacySignal("final_approved_outputs", "LEGACY_PRODUCTION_AUTHORITY",
                     PackagingOutput.objects.filter(is_final_approved=True).count()),
    )
