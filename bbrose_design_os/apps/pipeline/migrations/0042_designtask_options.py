# [His goal of 2026-10-13, (11) and (2)] the executor's per-design options

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pipeline', '0041_designtask_sku'),
    ]

    operations = [
        migrations.AddField(
            model_name='designtask',
            name='options',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
