from django.contrib import admin

from .models import (
    AestheticLanguage,
    Brand,
    Campaign,
    ColorSystem,
    MaterialSystem,
    PackagingStructure,
    Product,
)

admin.site.register(Brand)
admin.site.register(ColorSystem)
admin.site.register(MaterialSystem)
admin.site.register(AestheticLanguage)
admin.site.register(PackagingStructure)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "name", "brand", "category", "year", "status")
    list_filter = ("category", "status", "year", "brand")
    search_fields = ("product_id", "name", "notes")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "status", "start_date", "end_date")
    list_filter = ("status", "brand")
    search_fields = ("name", "direction", "aesthetic_notes")
