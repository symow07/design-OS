from django.db import migrations, models


class Migration(migrations.Migration):
    """[His goal for the pitch, 2026-10-15, A (1)] the written trend brief on a design's trend board."""

    dependencies = [
        ("pipeline", "0042_designtask_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="trendboard",
            name="brief",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
