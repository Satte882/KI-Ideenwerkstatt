# Generated for Issue #98 discovery-retention hardening

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0017_autonomous_business_discovery"),
    ]

    operations = [
        migrations.AlterField(
            model_name="investigationsourcefolder",
            name="capture_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="discovery_source_folders",
                to="accelerator.capturesession",
            ),
        ),
        migrations.AlterField(
            model_name="investigationsourcesnapshot",
            name="folder",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="snapshots",
                to="accelerator.investigationsourcefolder",
            ),
        ),
        migrations.AlterField(
            model_name="investigationsourcesnapshot",
            name="capture_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="discovery_source_snapshots",
                to="accelerator.capturesession",
            ),
        ),
    ]
