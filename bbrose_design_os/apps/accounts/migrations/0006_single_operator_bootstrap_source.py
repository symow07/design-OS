"""DIP-1A-BOOTSTRAP-CORR-2: register the BOOTSTRAP_SINGLE_OPERATOR grant source.

`sqlmigrate` for this migration is a **no-op** — `choices` is enforced by Django validation,
not by a database constraint, so no DDL runs. Nothing in auth, sessions, existing
DecisionEvents or existing role history is altered; forward, rollback and re-application are
all inert at the SQL level.

`BootstrapState.closed_at` and `closed_by_event` (FK, PROTECT) already exist from
0005_bootstrapstate, so the closure anchor needs no schema change.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_bootstrapstate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reviewerroleassignment',
            name='grant_source',
            field=models.CharField(choices=[('BOOTSTRAP', 'Bootstrap (pre-ledger)'), ('BOOTSTRAP_SINGLE_OPERATOR', 'Bootstrap (single-operator local ceremony)'), ('MIGRATION', 'Migration'), ('TEST_FIXTURE', 'Test fixture'), ('AUTHORIZED_SERVICE', 'Authorized service')], max_length=32),
        ),
    ]
