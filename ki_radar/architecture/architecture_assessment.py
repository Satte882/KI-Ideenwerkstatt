from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .architecture_advisor import RULESET_VERSION, classify_architecture
from .architecture_assessment_models import SolutionArchitectureAssessment
from .models import SolutionOption
from .permissions import can_edit_value_stream

ANSWER_FIELD_NAMES = (
    "simpler_solution_sufficient",
    "semantic_reasoning_required",
    "multiple_known_ai_steps_required",
    "dynamic_orchestration_required",
)


@transaction.atomic
def save_solution_architecture_assessment(
    *,
    solution_option: SolutionOption,
    answers: dict[str, str],
    actor,
) -> SolutionArchitectureAssessment:
    option = SolutionOption.objects.select_related("process_analysis__stage__value_stream").get(
        pk=solution_option.pk
    )
    if not can_edit_value_stream(actor, option.process_analysis.stage.value_stream):
        raise ValidationError("Für diese Architektur-Einschätzung fehlt die Berechtigung.")

    normalized_answers = {field: answers.get(field) for field in ANSWER_FIELD_NAMES}
    result = classify_architecture(**normalized_answers)

    assessment = SolutionArchitectureAssessment.objects.filter(solution_option=option).first()
    if assessment is None:
        return SolutionArchitectureAssessment.objects.create(
            solution_option=option,
            **normalized_answers,
            architecture_mode=result.mode,
            reason_codes=list(result.reason_codes),
            ruleset_version=RULESET_VERSION,
            version=1,
            assessed_by=actor,
        )

    for field_name, value in normalized_answers.items():
        setattr(assessment, field_name, value)
    assessment.architecture_mode = result.mode
    assessment.reason_codes = list(result.reason_codes)
    assessment.ruleset_version = RULESET_VERSION
    assessment.version += 1
    assessment.assessed_by = actor
    assessment.save(
        update_fields=[
            *ANSWER_FIELD_NAMES,
            "architecture_mode",
            "reason_codes",
            "ruleset_version",
            "version",
            "assessed_by",
            "updated_at",
        ]
    )
    return assessment
