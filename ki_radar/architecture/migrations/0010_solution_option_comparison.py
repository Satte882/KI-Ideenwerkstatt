import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_option_evaluations_and_decisions(apps, schema_editor):
    SolutionOption = apps.get_model("architecture", "SolutionOption")
    SolutionSelectionDecision = apps.get_model("architecture", "SolutionSelectionDecision")
    for option in SolutionOption.objects.all().iterator():
        if not option.bottleneck_coverage:
            option.bottleneck_coverage = option.expected_value or option.description
        required = (
            option.description,
            option.expected_value,
            option.bottleneck_coverage,
            option.data_requirements,
            option.application_impact,
            option.integration_impact,
            option.risks,
            option.architecture_fit,
        )
        option.evaluation_status = (
            "assessed" if all(str(value).strip() for value in required) else "draft"
        )
        option.save(update_fields=["evaluation_status", "bottleneck_coverage"])

    preferred_options = SolutionOption.objects.filter(recommendation="preferred")
    for option in preferred_options.iterator():
        options = list(
            SolutionOption.objects.filter(process_analysis_id=option.process_analysis_id)
        )
        snapshot = [
            {
                "id": str(candidate.pk),
                "name": candidate.name,
                "option_type": candidate.option_type,
                "evaluation_status": candidate.evaluation_status,
                "description": candidate.description,
                "expected_value": candidate.expected_value,
                "bottleneck_coverage": candidate.bottleneck_coverage,
                "feasibility": candidate.feasibility,
                "data_requirements": candidate.data_requirements,
                "application_impact": candidate.application_impact,
                "integration_effort": candidate.integration_effort,
                "integration_impact": candidate.integration_impact,
                "technology_constraints": candidate.technology_constraints,
                "risks": candidate.risks,
                "architecture_fit": candidate.architecture_fit,
                "captured_via": "migration_backfill",
            }
            for candidate in options
        ]
        SolutionSelectionDecision.objects.create(
            process_analysis_id=option.process_analysis_id,
            selected_option_id=option.pk,
            rationale=(
                "Bestehende bevorzugte Option aus dem Altbestand übernommen; "
                "die ursprüngliche Auswahlbegründung war nicht gespeichert."
            ),
            comparison_snapshot=snapshot,
            decided_by_id=option.created_by_id,
            decided_at=option.updated_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0009_backfill_source_provenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="solutionoption",
            name="bottleneck_coverage",
            field=models.TextField(
                blank=True,
                verbose_name="Abdeckung von Bottleneck und Ursache",
            ),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="evaluation_status",
            field=models.CharField(
                choices=[
                    ("draft", "Noch nicht vollständig bewertet"),
                    ("assessed", "Bewertet"),
                ],
                default="draft",
                max_length=20,
                verbose_name="Bewertungsstatus",
            ),
        ),
        migrations.AddField(
            model_name="solutionoption",
            name="integration_effort",
            field=models.CharField(
                choices=[
                    ("low", "Niedrig"),
                    ("medium", "Mittel"),
                    ("high", "Hoch"),
                ],
                default="medium",
                max_length=10,
                verbose_name="Integrationsaufwand",
            ),
        ),
        migrations.CreateModel(
            name="SolutionSelectionDecision",
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
                ("rationale", models.TextField(verbose_name="Auswahlbegründung")),
                ("comparison_snapshot", models.JSONField(default=list, editable=False)),
                (
                    "decided_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                    ),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="solution_selection_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "process_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="solution_selection_decisions",
                        to="architecture.processanalysis",
                    ),
                ),
                (
                    "selected_option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="selection_decisions",
                        to="architecture.solutionoption",
                    ),
                ),
            ],
            options={"ordering": ["-decided_at", "-created_at"]},
        ),
        migrations.RunPython(
            backfill_option_evaluations_and_decisions,
            migrations.RunPython.noop,
        ),
    ]
