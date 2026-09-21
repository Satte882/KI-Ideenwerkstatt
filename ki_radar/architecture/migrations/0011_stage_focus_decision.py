from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_stage_focus_decisions(apps, schema_editor):
    StageFocusDecision = apps.get_model("architecture", "StageFocusDecision")
    ProcessAnalysis = apps.get_model("architecture", "ProcessAnalysis")
    UseCaseOrigin = apps.get_model("architecture", "UseCaseOrigin")

    value_stream_ids = set(
        ProcessAnalysis.objects.values_list("stage__value_stream_id", flat=True)
    ) | set(UseCaseOrigin.objects.values_list("stage__value_stream_id", flat=True))

    for value_stream_id in value_stream_ids:
        analysis = (
            ProcessAnalysis.objects.filter(stage__value_stream_id=value_stream_id)
            .select_related("stage")
            .order_by("created_at")
            .first()
        )
        origin = None
        if analysis is None:
            origin = (
                UseCaseOrigin.objects.filter(stage__value_stream_id=value_stream_id)
                .select_related("stage")
                .order_by("created_at")
                .first()
            )
        stage = analysis.stage if analysis is not None else origin.stage
        actor_id = analysis.analyzed_by_id if analysis is not None else None
        snapshot = {
            str(stage.pk): {
                "sequence": stage.sequence,
                "name": stage.name,
                "impact": "",
                "pain_intensity": "",
                "data_accessibility": "",
                "change_effort": "",
                "indicators": {
                    "pain_points": stage.pain_points,
                    "baseline_metrics": stage.baseline_metrics,
                },
            }
        }
        StageFocusDecision.objects.get_or_create(
            value_stream_id=value_stream_id,
            defaults={
                "selected_stage_id": stage.pk,
                "criteria_snapshot": snapshot,
                "rationale": "Fokusphase aus einem bestehenden Architekturpfad übernommen.",
                "is_short_path": True,
                "short_path_reason": (
                    "Bestandsübernahme: Prozessanalyse oder Use-Case-Ursprung war bereits dokumentiert."
                ),
                "selected_by_id": actor_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0010_solution_option_comparison"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StageFocusDecision",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("criteria_snapshot", models.JSONField(blank=True, default=dict, editable=False)),
                ("rationale", models.TextField(verbose_name="Begründung der Phasenauswahl")),
                (
                    "is_short_path",
                    models.BooleanField(default=False, verbose_name="Bewusster Kurzpfad"),
                ),
                (
                    "short_path_reason",
                    models.TextField(blank=True, verbose_name="Begründung des Kurzpfads"),
                ),
                (
                    "selected_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="stage_focus_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "selected_stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="focus_decisions",
                        to="architecture.valuestreamstage",
                        verbose_name="Fokusphase",
                    ),
                ),
                (
                    "value_stream",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stage_focus_decision",
                        to="architecture.valuestream",
                    ),
                ),
            ],
            options={
                "ordering": ["value_stream__business_unit__name", "value_stream__name"],
            },
        ),
        migrations.RunPython(backfill_stage_focus_decisions, migrations.RunPython.noop),
    ]
