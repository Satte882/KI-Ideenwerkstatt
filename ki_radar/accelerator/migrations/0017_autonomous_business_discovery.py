# Generated for Issue #98 autonomous business discovery

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accelerator", "0016_investigation_activity_execution"),
    ]

    operations = [
        migrations.AddField(
            model_name="capturesession",
            name="mode",
            field=models.CharField(
                choices=[("guided", "Geführt"), ("autonomous", "Autonom")],
                db_index=True,
                default="guided",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="captureanalysis",
            name="result_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="captureanalysis",
            name="verification_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="captureanalysis",
            name="status",
            field=models.CharField(
                choices=[
                    ("running", "Läuft"),
                    ("success", "Erfolgreich"),
                    ("waiting_human", "Klärung erforderlich"),
                    ("failed", "Fehlgeschlagen"),
                ],
                db_index=True,
                default="running",
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="captureanalysis",
            name="analysis_status_finished_valid",
        ),
        migrations.AddConstraint(
            model_name="captureanalysis",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(status="running", finished_at__isnull=True)
                    | models.Q(
                        status__in=["success", "waiting_human", "failed"],
                        finished_at__isnull=False,
                    )
                ),
                name="analysis_status_finished_valid",
            ),
        ),
        migrations.AlterField(
            model_name="investigationsourcefolder",
            name="process_analysis",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="investigation_source_folders",
                to="architecture.processanalysis",
            ),
        ),
        migrations.AddField(
            model_name="investigationsourcefolder",
            name="capture_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="discovery_source_folders",
                to="accelerator.capturesession",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationsourcefolder",
            constraint=models.UniqueConstraint(
                fields=("capture_session", "root_path"),
                name="uniq_investigation_folder_capture_path",
            ),
        ),
        migrations.AddConstraint(
            model_name="investigationsourcefolder",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(process_analysis__isnull=False, capture_session__isnull=True)
                    | models.Q(process_analysis__isnull=True, capture_session__isnull=False)
                ),
                name="investigation_folder_owner_valid",
            ),
        ),
        migrations.AlterField(
            model_name="investigationsourcesnapshot",
            name="process_analysis",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="investigation_source_snapshots",
                to="architecture.processanalysis",
            ),
        ),
        migrations.AddField(
            model_name="investigationsourcesnapshot",
            name="capture_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="discovery_source_snapshots",
                to="accelerator.capturesession",
            ),
        ),
        migrations.AlterField(
            model_name="investigationsourcesnapshot",
            name="process_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="investigationsourcesnapshot",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(process_analysis__isnull=False, capture_session__isnull=True)
                    | models.Q(process_analysis__isnull=True, capture_session__isnull=False)
                ),
                name="investigation_snapshot_owner_valid",
            ),
        ),
    ]
