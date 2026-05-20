from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=200)
    master_brief = models.TextField()  # BBROSE master brand brief
    positioning = models.TextField(blank=True)
    what_we_are_not = models.TextField(blank=True)
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
    status = models.CharField(max_length=50, default='canonical')


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
    status = models.CharField(max_length=50, default='canonical')


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
    product_type = models.CharField(max_length=100, blank=True)  # e.g. "carton", "eyeliner"
    finish_notes = models.TextField(blank=True)
    product_image = models.ImageField(upload_to='products/', blank=True)  # the PNG from Excel
    packaging_image = models.ImageField(upload_to='packaging/', blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Campaign(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=200)
    direction = models.TextField()
    aesthetic_notes = models.TextField(blank=True)
    status = models.CharField(max_length=50, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
