import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CaptureSession",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                    "capture_type",
                    models.CharField(
                        choices=[
                            ("value_stream", "Value Stream"),
                            ("use_case", "Use Case"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("working_title", models.CharField(blank=True, max_length=200)),
                ("catalog_version", models.CharField(max_length=20)),
                ("schema_version", models.CharField(max_length=20)),
                ("answers", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Entwurf"),
                            ("completed", "Abgeschlossen"),
                            ("discarded", "Verworfen"),
                            ("expired", "Abgelaufen"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("revision", models.PositiveIntegerField(default=0)),
                ("answered_required_count", models.PositiveSmallIntegerField(default=0)),
                ("required_question_count", models.PositiveSmallIntegerField(default=0)),
                ("active_entry_seconds", models.PositiveIntegerField(default=0)),
                ("save_count", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("discarded_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="capture_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(
                        fields=["owner", "status", "capture_type"],
                        name="capture_owner_status_type_idx",
                    ),
                    models.Index(
                        fields=["owner", "-updated_at"],
                        name="capture_owner_updated_idx",
                    ),
                    models.Index(
                        fields=["status", "expires_at"],
                        name="capture_status_expires_idx",
                    ),
                ],
            },
        ),
    ]
