from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dielines", "0002_seed_straight_tuck_end_carton"),
    ]

    operations = [
        migrations.AddField(
            model_name="dielinejob",
            name="ai_output_path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
