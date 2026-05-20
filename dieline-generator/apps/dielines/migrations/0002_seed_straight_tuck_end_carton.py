from django.db import migrations


def seed_template(apps, schema_editor):
    DielineTemplate = apps.get_model("dielines", "DielineTemplate")
    DielineTemplate.objects.get_or_create(
        template_type="straight_tuck_end_carton",
        defaults={
            "name": "Straight Tuck-End Cosmetic Carton",
            "description": (
                "Standard straight tuck-end carton for slim cosmetic products. "
                "Suitable for eyeliner, lip oil, mascara, lipstick, and similar products."
            ),
            "default_bleed_mm": "3.00",
            "default_safe_margin_mm": "4.00",
            "default_glue_tab_mm": "10.00",
        },
    )


def unseed_template(apps, schema_editor):
    DielineTemplate = apps.get_model("dielines", "DielineTemplate")
    DielineTemplate.objects.filter(template_type="straight_tuck_end_carton").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dielines", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_template, reverse_code=unseed_template),
    ]
