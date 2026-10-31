"""[His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "TOP-TIER DIELINES".]
Every carton a design draws is now the reverse tuck end (ECMA A20.20.03.01) — the layout 0002's straight tuck row was
drawn as — so its template row is seeded beside it, its glue flap proposed at 12 mm (apps/dielines/docs/TRADE_RULES.md
G2: Klearfold 12.7, Box Blanks 12; the straight tuck's 10 mm sits at the trade's narrow end)."""
from django.db import migrations


def seed_template(apps, schema_editor):
    DielineTemplate = apps.get_model("dielines", "DielineTemplate")
    DielineTemplate.objects.get_or_create(
        template_type="reverse_tuck_end_carton",
        defaults={
            "name": "Reverse Tuck-End Cosmetic Carton",
            "description": (
                "Reverse tuck-end carton (ECMA A20.20.03.01): the top tuck on the back, the bottom tuck on the front. "
                "For slim cosmetic products — lip gloss, lip oil, mascara, eyeliner, lipstick, serums."
            ),
            "default_bleed_mm": "3.00",
            "default_safe_margin_mm": "4.00",
            "default_glue_tab_mm": "12.00",
        },
    )


def unseed_template(apps, schema_editor):
    DielineTemplate = apps.get_model("dielines", "DielineTemplate")
    DielineTemplate.objects.filter(template_type="reverse_tuck_end_carton").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dielines", "0008_alter_dielinejob_template_type_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_template, reverse_code=unseed_template),
    ]
