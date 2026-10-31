from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pipeline', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='packagingoutput',
            name='spec_pdf',
            field=models.FileField(blank=True, upload_to='spec_sheets/'),
        ),
    ]
