from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import (
    AestheticLanguage,
    Brand,
    ColorSystem,
    MaterialSystem,
    PackagingStructure,
)

MASTER_BRIEF = (
    "BBROSE is a feminine luxury beauty brand with a soft premium aesthetic. "
    "The palette centers on blush pink, nude, and warm cream tones. Visual "
    "direction is editorial beauty: luxury cosmetic packaging with a glossy + "
    "matte material contrast and rose gold details. Branding is soft and "
    "cinematic, elegant but modern, minimal but not empty — a premium "
    "beauty-store aesthetic."
)

POSITIONING = (
    "Premium feminine beauty positioned between mass-prestige and true luxury: "
    "editorial, intimate, and tactile. BBROSE feels like a high-end beauty "
    "store — warm, soft, and considered."
)

WHAT_WE_ARE_NOT = (
    "Not clinical, not cold, not minimalist-to-the-point-of-empty, not loud or "
    "neon, not gender-neutral-tech, not budget mass-market."
)


class Command(BaseCommand):
    help = "Seed the database with BBROSE's initial brand data (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        brand, created = Brand.objects.get_or_create(
            name="BBROSE",
            defaults={
                "master_brief": MASTER_BRIEF,
                "positioning": POSITIONING,
                "what_we_are_not": WHAT_WE_ARE_NOT,
            },
        )
        if not created:
            brand.master_brief = MASTER_BRIEF
            brand.positioning = POSITIONING
            brand.what_we_are_not = WHAT_WE_ARE_NOT
            brand.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Brand {'created' if created else 'updated'}: {brand.name}"
            )
        )

        self._seed_color_systems(brand)
        self._seed_aesthetic_language(brand)
        self._seed_material_systems(brand)
        self._seed_packaging_structures(brand)

        self.stdout.write(self.style.SUCCESS("BBROSE seed complete."))

    def _upsert(self, model, lookup, defaults, label):
        obj, created = model.objects.update_or_create(
            defaults=defaults, **lookup
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  {model.__name__} {label}: "
                f"{'created' if created else 'updated'}"
            )
        )
        return obj

    def _seed_color_systems(self, brand):
        self._upsert(
            ColorSystem,
            {"brand": brand, "system_id": "CS-001"},
            {
                "name": "Blush Core",
                "palette": [
                    {
                        "role": "Primary",
                        "name": "Blush",
                        "hex": "#F2C4CE",
                        "pantone": "698 C",
                        "usage": "Main surfaces, hero cartons",
                    },
                    {
                        "role": "Secondary",
                        "name": "Pale Petal",
                        "hex": "#F7DDE3",
                        "pantone": "698 lighter",
                        "usage": "Interior, secondary panels",
                    },
                    {
                        "role": "Accent",
                        "name": "Deep Rose",
                        "hex": "#8B3A52",
                        "pantone": "209 C",
                        "usage": "Typography, fine detail lines",
                    },
                    {
                        "role": "Metallic",
                        "name": "Rose Gold",
                        "hex": "Metallic 10122 C",
                        "usage": "Caps, closures, foil detail",
                    },
                    {
                        "role": "Ground",
                        "name": "Warm Cream",
                        "hex": "#FAF3EC",
                        "pantone": "9182 C",
                        "usage": "Base packaging, backgrounds",
                    },
                    {
                        # §BH39(a) (2026-09-08): the warm gold ground of the
                        # owner's own designs, NAMED by the owner's sentence.
                        # hex = the measured value (24 historical design files,
                        # archive/work/bh38_colours_materials_proposal/design_roles.json); no Pantone held.
                        "role": "Ground",
                        "name": "Warm Gold",
                        "hex": "#CBA87D",
                        "pantone": "",
                        "usage": "Warm gold ground panels, gold fields behind type",
                        "provenance": "§BH39(a) · measured 2026-09-07 by structure from 24 historical design files · docs/brand_gov/colour_roles_1_0.json",
                    },
                ],
                "image_generation_context": (
                    "blush pink nude palette, warm cream surface, rose gold "
                    "metallic accents, soft feminine luxury, warm light, "
                    "#F2C4CE primary"
                ),
                "status": "canonical",
            },
            "CS-001 Blush Core",
        )

        self._upsert(
            ColorSystem,
            {"brand": brand, "system_id": "CS-002"},
            {
                "name": "Nude Warm",
                "palette": [
                    {
                        "role": "Primary",
                        "name": "Warm Nude",
                        "hex": "#E8C9B3",
                        "pantone": "475 C",
                        "usage": "Main surfaces, warm hero packaging",
                    },
                    {
                        "role": "Secondary",
                        "name": "Soft Sand",
                        "hex": "#F0DECB",
                        "pantone": "7506 C",
                        "usage": "Secondary panels, interiors",
                    },
                    {
                        "role": "Accent",
                        "name": "Cocoa Rose",
                        "hex": "#7A4A42",
                        "pantone": "4975 C",
                        "usage": "Typography, fine detail lines",
                    },
                    {
                        "role": "Metallic",
                        "name": "Rose Gold",
                        "hex": "Metallic 10122 C",
                        "usage": "Caps, closures, foil detail",
                    },
                    {
                        "role": "Ground",
                        "name": "Warm Cream",
                        "hex": "#FAF3EC",
                        "pantone": "9182 C",
                        "usage": "Base packaging, backgrounds",
                    },
                    {
                        # §BH39(a) (2026-09-08): the warm gold ground of the
                        # owner's own designs, NAMED by the owner's sentence.
                        # hex = the measured value (24 historical design files,
                        # archive/work/bh38_colours_materials_proposal/design_roles.json); no Pantone held.
                        "role": "Ground",
                        "name": "Warm Gold",
                        "hex": "#CBA87D",
                        "pantone": "",
                        "usage": "Warm gold ground panels, gold fields behind type",
                        "provenance": "§BH39(a) · measured 2026-09-07 by structure from 24 historical design files · docs/brand_gov/colour_roles_1_0.json",
                    },
                ],
                "image_generation_context": (
                    "warm nude and sand palette, soft cream ground, rose gold "
                    "metallic detail, intimate feminine luxury, warm diffused "
                    "light, #E8C9B3 primary"
                ),
                "status": "canonical",
            },
            "CS-002 Nude Warm",
        )

    def _seed_aesthetic_language(self, brand):
        self._upsert(
            AestheticLanguage,
            {"brand": brand, "aesthetic_id": "AL-001"},
            {
                "name": "Soft Luxury",
                "core_description": (
                    "Soft, warm, editorial feminine luxury. Diffused light, "
                    "tactile silk and cream surfaces, rose gold metallic "
                    "detail, shallow depth of field. Premium beauty-store feel "
                    "— elegant, modern, intimate, never clinical or cold."
                ),
                "prompt_seed_product": (
                    "soft luxury beauty product photography, warm diffused "
                    "lighting, blush pink and warm cream palette, silk surface "
                    "texture, rose gold metallic detail, shallow depth of "
                    "field, editorial beauty aesthetic, magazine quality, "
                    "feminine premium cosmetics, warm ambient light"
                ),
                "prompt_seed_campaign": (
                    "luxury beauty campaign, soft cinematic light, warm skin "
                    "tones, blush pink editorial beauty, intimate close-up, "
                    "silk and soft textures, high fashion beauty photography "
                    "aesthetic, feminine and editorial, premium cosmetic brand "
                    "campaign visual"
                ),
                "what_breaks_this": [
                    "hard shadows",
                    "cool/blue tones",
                    "white background",
                    "commercial feel",
                    "flat lighting",
                ],
                "status": "canonical",
            },
            "AL-001 Soft Luxury",
        )

    def _seed_material_systems(self, brand):
        self._upsert(
            MaterialSystem,
            {"brand": brand, "material_id": "ML-001"},
            {
                "name": "Glossy Acrylic",
                "properties": {
                    "finish": "high-gloss",
                    "reflectivity": "mirror",
                    "substrate": "acrylic",
                    "tactile": "smooth",
                },
                "finish_combinations": [
                    "gloss body + matte cap",
                    "gloss body + rose gold foil",
                ],
                "prompt_descriptors": (
                    "glossy acrylic packaging, mirror finish, high-gloss "
                    "surface, luxury cosmetic packaging, reflective premium "
                    "finish"
                ),
                "categories_used_in": ["CO"],
                "status": "approved",
            },
            "ML-001 Glossy Acrylic",
        )

    def _seed_packaging_structures(self, brand):
        self._upsert(
            PackagingStructure,
            {"brand": brand, "structure_id": "PKG-STR-001"},
            {
                "name": "Lip Oil Roller",
                "structure_type": "cylindrical tube",
                "dimensions": {
                    "diameter": "11mm",
                    "height": "82mm",
                    "units": "mm",
                },
                "printable_surface": {
                    "width": "34.6mm",
                    "height": "82mm",
                    "aspect_ratio": "9:21",
                },
                "surface_zones": {
                    "logo_zone": "upper 30% — clear, no texture",
                    "texture_zone": "lower 60% — primary graphic surface",
                    "accent_line": "80% height horizontal band",
                },
                "status": "active",
            },
            "PKG-STR-001 Lip Oil Roller",
        )
