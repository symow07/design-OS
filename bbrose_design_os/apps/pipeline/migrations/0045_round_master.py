from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pipeline', '0044_creative_round')]
    operations = [migrations.CreateModel(name='RoundMaster', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('state', models.CharField(db_index=True, default='queued', max_length=16)),
        ('current_step', models.CharField(default='panels', max_length=24)),
        ('steps', models.JSONField(default=dict)), ('inputs', models.JSONField(default=dict)),
        ('publication', models.JSONField(default=dict)), ('error', models.TextField(blank=True)),
        ('budget_usd', models.DecimalField(decimal_places=2, default=15, max_digits=6)),
        ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
        ('round', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='master_build', to='pipeline.round')),
    ])]
