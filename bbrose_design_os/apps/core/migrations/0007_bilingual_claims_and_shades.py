"""§BH55(a) — what the owner's Phase 1 brief says the pack must carry, and the record could not hold.

Three fields, and nothing else: the house's four claims on the Brand (his words: "that run on every product of
ours"), and the Arabic product name and the shade names on the Product. No row is rewritten and no existing field
is touched; every default is empty, so the schema is the only thing that moves.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0006_designreference_anatomy")]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="claims",
            field=models.JSONField(
                blank=True, default=list,
                help_text="House claims printed on every pack; one row per claim, each carrying en and ar"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_ar",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="product",
            name="shade_names",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
