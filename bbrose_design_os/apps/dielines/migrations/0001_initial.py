import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0002_product_campaign"),
    ]

    operations = [
        migrations.CreateModel(
            name="DielineTemplate",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                (
                    "template_type",
                    models.CharField(
                        choices=[("straight_tuck_end_carton", "Straight Tuck-End Carton")],
                        max_length=60,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "default_bleed_mm",
                    models.DecimalField(decimal_places=2, default=3.0, max_digits=5),
                ),
                (
                    "default_safe_margin_mm",
                    models.DecimalField(decimal_places=2, default=4.0, max_digits=5),
                ),
                (
                    "default_glue_tab_mm",
                    models.DecimalField(decimal_places=2, default=10.0, max_digits=5),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="DielineJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dieline_jobs",
                        to="core.product",
                    ),
                ),
                (
                    "template_type",
                    models.CharField(
                        choices=[("straight_tuck_end_carton", "Straight Tuck-End Carton")],
                        max_length=60,
                    ),
                ),
                (
                    "scenario",
                    models.CharField(
                        choices=[("A", "A"), ("B", "B")],
                        max_length=1,
                    ),
                ),
                ("input_json", models.JSONField()),
                ("extraction_result", models.JSONField(blank=True, null=True)),
                (
                    "validation_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("valid", "Valid"),
                            ("invalid", "Invalid"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("warnings", models.JSONField(default=list)),
                ("svg_output_path", models.CharField(blank=True, max_length=500)),
                ("pdf_output_path", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
