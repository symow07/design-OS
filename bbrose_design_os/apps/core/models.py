from django.db import models

# Shared status value for canonical brand-knowledge records (Milestone 11.2 /
# audit H9). The dashboard brand panel and the pipeline brand context BOTH
# filter on this constant so the value can never drift again (the old bug was
# the dashboard filtering status="active" while seeds/pipeline used
# "canonical", rendering the palette panel empty).
STATUS_CANONICAL = "canonical"


class Brand(models.Model):
    name = models.CharField(max_length=200)
    master_brief = models.TextField()  # BBROSE master brand brief
    positioning = models.TextField(blank=True)
    what_we_are_not = models.TextField(blank=True)
    # Info-panel constants (2026-07-06): compliance text printed on every
    # carton back panel — supplier / importer / distributor blocks, exactly
    # as on existing production files. website feeds the default QR code.
    website = models.URLField(blank=True)
    regulatory_text = models.TextField(
        blank=True,
        help_text="Supplier / importer / distributor block printed on every info panel",
    )
    #: §BH55(a): "the four claims that run on every product of ours: cruelty-free, 100% vegan, dermatologist
    #: tested, long-wear". The BRAND's, by his own words, so they sit here beside the regulatory block rather
    #: than being retyped on every product. One row per claim, BOTH languages in the row — he wrote "the pack is
    #: bilingual and Arabic is not an afterthought", and two parallel lists are how an afterthought is stored.
    #: [{"en": "Cruelty-free", "ar": "...", "ar_source": "EXECUTOR_UNCONFIRMED"}, ...]
    claims = models.JSONField(
        default=list, blank=True,
        help_text="House claims printed on every pack; one row per claim, each carrying en and ar",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ColorSystem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='color_systems')
    name = models.CharField(max_length=200)  # e.g. "Blush Core"
    system_id = models.CharField(max_length=20)  # e.g. "CS-001"
    palette = models.JSONField()  # list of {role, name, hex, pantone, usage}
    material_pairings_approved = models.JSONField(default=list)
    material_pairings_rejected = models.JSONField(default=list)
    image_generation_context = models.TextField()  # prompt seed for this palette
    status = models.CharField(max_length=50, default=STATUS_CANONICAL)


class MaterialSystem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='material_systems')
    name = models.CharField(max_length=200)
    material_id = models.CharField(max_length=20)  # e.g. "ML-001"
    properties = models.JSONField()
    finish_combinations = models.JSONField(default=list)
    prompt_descriptors = models.TextField()
    categories_used_in = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='approved')


class AestheticLanguage(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='aesthetic_language')
    name = models.CharField(max_length=200)
    aesthetic_id = models.CharField(max_length=20)  # e.g. "AL-001"
    core_description = models.TextField()
    prompt_seed_product = models.TextField()  # for product photography
    prompt_seed_campaign = models.TextField()  # for campaign visuals
    what_breaks_this = models.JSONField(default=list)
    status = models.CharField(max_length=50, default=STATUS_CANONICAL)


class PackagingStructure(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='packaging_structures')
    name = models.CharField(max_length=200)
    structure_id = models.CharField(max_length=20)  # e.g. "PKG-STR-001"
    structure_type = models.CharField(max_length=100)  # tube, carton, bottle, etc.
    dimensions = models.JSONField()  # {diameter, height, units}
    printable_surface = models.JSONField()  # {width, height, aspect_ratio}
    surface_zones = models.JSONField()  # {logo_zone, texture_zone, accent_zone}
    pacdora_template_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=50, default='active')


PRODUCT_CATEGORIES = [
    ('SK', 'Skincare'),
    ('HC', 'Hair Care'),
    ('CO', 'Cosmetics'),
]

PRODUCT_STATUS = [
    ('active', 'Active'),
    ('in_development', 'In Development'),
    ('archived', 'Archived'),
    ('rejected', 'Rejected'),
]


#: §BH55(a) — the state an Arabic string carries until he confirms it. A translation nobody confirmed can reach a
#: printed pack in a market he named, so it is marked rather than assumed, exactly as a machine-written caption is.
AR_UNCONFIRMED = "EXECUTOR_UNCONFIRMED"


def bilingual(rows, lang):
    """The `lang` side of a list of bilingual rows, skipping rows that do not carry it.

    A row missing its Arabic is a row, not a shorter list: it is skipped visibly here and counted by
    `unconfirmed_arabic` below, rather than silently shifting every later shade by one.
    """
    return [r[lang] for r in (rows or []) if isinstance(r, dict) and r.get(lang)]


def unconfirmed_arabic(rows):
    """The rows whose Arabic is the executor's and has not been confirmed — named, never counted silently."""
    return [r.get("en") or "" for r in (rows or [])
            if isinstance(r, dict) and r.get("ar") and r.get("ar_source") == AR_UNCONFIRMED]


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    product_id = models.CharField(max_length=50, unique=True)  # from Excel e.g. "BBR-CO-042"
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=2, choices=PRODUCT_CATEGORIES)
    year = models.IntegerField()  # 2025 or 2026
    status = models.CharField(max_length=50, choices=PRODUCT_STATUS, default='active')
    color_system = models.ForeignKey(ColorSystem, null=True, blank=True, on_delete=models.SET_NULL)
    packaging_structure = models.ForeignKey(PackagingStructure, null=True, blank=True, on_delete=models.SET_NULL)
    material = models.ForeignKey(MaterialSystem, null=True, blank=True, on_delete=models.SET_NULL)
    dimensions = models.CharField(max_length=200, blank=True)
    # Structured manufacture dimensions (mm) consumed by the dieline generator.
    # When all three are set (> 0), DielineAgent runs Scenario A (exact DB dims,
    # no AI estimation). Left null, it falls back to Scenario B (AI estimate).
    width_mm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    depth_mm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_mm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    #: §BH55(a): "the product name in English and Arabic — our market is Jordan, Syria, Palestine, Lebanon and
    #: Tunisia, so the pack is bilingual and Arabic is not an afterthought." `name` above is the English.
    name_ar = models.CharField(max_length=200, blank=True)
    #: §BH55(a): "shade names for the four pans" — one row per shade, in the order they are laid out, each
    #: carrying both languages for the same reason the claims do.
    #: [{"en": "First Light", "ar": "...", "ar_source": "EXECUTOR_UNCONFIRMED"}, ...]
    shade_names = models.JSONField(default=list, blank=True)
    product_type = models.CharField(max_length=100, blank=True)  # e.g. "carton", "eyeliner"
    finish_notes = models.TextField(blank=True)
    product_image = models.ImageField(upload_to='products/', blank=True)  # the PNG from Excel
    packaging_image = models.ImageField(upload_to='packaging/', blank=True)
    notes = models.TextField(blank=True)
    # --- Info panel / regulatory data (2026-07-06) --------------------------
    # Printed on the carton's back face in the components .ai: description,
    # ingredients, usage, warnings + the machine-readables (EAN-13 barcode,
    # QR). Mirrors the structure of existing BBROSE production files.
    description = models.TextField(
        blank=True, help_text="Consumer-facing description for the info panel")
    ingredients = models.TextField(
        blank=True, help_text="INCI ingredients list (printed after 'INGREDIENTS:')")
    how_to_use = models.TextField(blank=True)
    warnings_text = models.TextField(
        blank=True, help_text="Printed after 'WARNINGS:'")
    net_weight = models.CharField(
        max_length=60, blank=True, help_text="e.g. '5 g X 12 PCS' or '30 ml e 1 fl. oz.'")
    item_no = models.CharField(
        max_length=40, blank=True, help_text="e.g. 'EP2508-E'")
    barcode_ean = models.CharField(
        max_length=13, blank=True,
        help_text="EAN-13 digits (12-13), e.g. 5061030633786 — rendered as a vector barcode")
    qr_url = models.URLField(
        blank=True, help_text="QR target; falls back to the brand website")
    created_at = models.DateTimeField(auto_now_add=True)


class DesignReference(models.Model):
    """One imported reference design (2026-07-06).

    Rasterized from the production .ai library by ``import_design_references``
    and tagged ONCE by vision so the Creative Director can pick the most
    RELEVANT references for each task's product — with 90+ files, 'newest N'
    stopped being meaningful. Tags are editable in admin.
    """
    name = models.CharField(max_length=200, unique=True)   # source stem
    image_path = models.CharField(max_length=300)          # MEDIA_ROOT-relative PNG
    source_file = models.CharField(max_length=300, blank=True)
    category = models.CharField(                           # SK/HC/CO or ''
        max_length=2, choices=PRODUCT_CATEGORIES, blank=True)
    product_type = models.CharField(max_length=120, blank=True)  # e.g. "eyeshadow palette"
    tags = models.JSONField(default=list)                  # motifs/finishes/palette words
    summary = models.TextField(blank=True)
    # Deep anatomy (2026-07-07): structured part-by-part study of the file —
    # layout grid, typography, motif inventory, palette hexes, finishes,
    # back-panel conventions. Filled by import_design_references --deep.
    anatomy = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.product_type or 'untagged'})"


class Campaign(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=200)
    direction = models.TextField()
    aesthetic_notes = models.TextField(blank=True)
    status = models.CharField(max_length=50, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
