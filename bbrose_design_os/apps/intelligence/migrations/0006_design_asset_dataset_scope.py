from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0005_governance_projections"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="designassetprofile",
            name="intel_asset_c2_dataset_only",
        ),
        migrations.AddConstraint(
            model_name="designassetprofile",
            constraint=models.CheckConstraint(
                check=models.Q(dataset_identifier__in=(
                    "dip0c2_asset_candidate_pilot/1.0",
                    "dip1b_curated_asset_expansion/1.0",
                )),
                name="intel_asset_dataset_supported",
            ),
        ),
    ]
