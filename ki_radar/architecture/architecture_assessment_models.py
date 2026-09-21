from __future__ import annotations

from django.conf import settings
from django.db import models

from ki_radar.core.models import TimeStampedModel

from .architecture_advisor import RULESET_VERSION


class SolutionArchitectureAssessment(TimeStampedModel):
    class Answer(models.TextChoices):
        YES = "yes", "Ja"
        NO = "no", "Nein"
        UNCLEAR = "unclear", "Unklar"

    class ArchitectureMode(models.TextChoices):
        NO_LLM_REQUIRED = "no_llm_required", "No LLM required"
        CONTROLLED_LLM = "controlled_llm", "Controlled LLM"
        LLM_WORKFLOW = "llm_workflow", "LLM Workflow"
        BOUNDED_AGENT = "bounded_agent", "Bounded Agent"
        ASSESSMENT_OPEN = "assessment_open", "Assessment open"

    solution_option = models.OneToOneField(
        "architecture.SolutionOption",
        on_delete=models.CASCADE,
        related_name="architecture_assessment",
    )
    simpler_solution_sufficient = models.CharField(max_length=10, choices=Answer.choices)
    semantic_reasoning_required = models.CharField(max_length=10, choices=Answer.choices)
    multiple_known_ai_steps_required = models.CharField(max_length=10, choices=Answer.choices)
    dynamic_orchestration_required = models.CharField(max_length=10, choices=Answer.choices)
    architecture_mode = models.CharField(
        max_length=30,
        choices=ArchitectureMode.choices,
        editable=False,
    )
    reason_codes = models.JSONField(default=list, editable=False)
    ruleset_version = models.CharField(
        max_length=64,
        default=RULESET_VERSION,
        editable=False,
    )
    version = models.PositiveIntegerField(default=1, editable=False)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="solution_architecture_assessments",
    )

    class Meta:
        app_label = "architecture"

    def __str__(self) -> str:
        return f"{self.solution_option}: {self.get_architecture_mode_display()}"
