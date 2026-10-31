"""§BH55 Phase 3 — a nudge for every step that waits on a person.

The kinds a Notification may carry were the three gates, a failure and a finish; they are every waiting step now, and
the column holds the longest of their names (39 characters). Nothing is rewritten: the rows already stored keep their
own kinds, which are all still in the list.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("pipeline", "0031_palette_material_artifact")]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
                choices=[
                    ("awaiting_direction_selection", "Awaiting a direction"),
                    ("awaiting_gate1_generation_configuration", "Awaiting the concept set-up"),
                    ("awaiting_gate_1", "Awaiting Gate 1"),
                    ("awaiting_dimensions", "Awaiting Dimensions"),
                    ("awaiting_container_profile", "Awaiting the container shape"),
                    ("awaiting_structure_confirmation", "Awaiting the structure"),
                    ("awaiting_design_intent_confirmation", "Awaiting the design intent"),
                    ("awaiting_gate_2", "Awaiting Gate 2"),
                    ("failed", "Task Failed"),
                    ("completed", "Task Completed"),
                ],
                max_length=50,
            ),
        ),
    ]
