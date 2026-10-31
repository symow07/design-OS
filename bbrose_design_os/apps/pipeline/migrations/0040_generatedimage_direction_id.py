# [his final goal, 2026-10-05, B4] the planned direction each concept picture was drawn for

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pipeline', '0039_sticker_reference'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='direction_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
