import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0014_solutionoptionretirement"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolutionArchitectureAssessment",
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
                (
                    "simpler_solution_sufficient",
                    models.CharField(
                        choices=[("yes", "Ja"), ("no", "Nein"), ("unclear", "Unklar")],
                        max_length=10,
                    ),
                ),
                (
                    "semantic_reasoning_required",
                    models.CharField(
                        choices=[("yes", "Ja"), ("no", "Nein"), ("unclear", "Unklar")],
                        max_length=10,
                    ),
                ),
                (
                    "multiple_known_ai_steps_required",
                    models.CharField(
                        choices=[("yes", "Ja"), ("no", "Nein"), ("unclear", "Unklar")],
                        max_length=10,
                    ),
                ),
                (
                    "dynamic_orchestration_required",
                    models.CharField(
                        choices=[("yes", "Ja"), ("no", "Nein"), ("unclear", "Unklar")],
                        max_length=10,
                    ),
                ),
                (
                    "architecture_mode",
                    models.CharField(
                        choices=[
                            ("no_llm_required", "No LLM required"),
                            ("controlled_llm", "Controlled LLM"),
                            ("llm_workflow", "LLM Workflow"),
                            ("bounded_agent", "Bounded Agent"),
                            ("assessment_open", "Assessment open"),
                        ],
                        editable=False,
                        max_length=30,
                    ),
                ),
                ("reason_codes", models.JSONField(default=list, editable=False)),
                (
                    "ruleset_version",
                    models.CharField(
                        default="architecture-advisor-v1",
                        editable=False,
                        max_length=64,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1, editable=False)),
                (
                    "assessed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="solution_architecture_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "solution_option",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="architecture_assessment",
                        to="architecture.solutionoption",
                    ),
                ),
            ],
        ),
    ]
