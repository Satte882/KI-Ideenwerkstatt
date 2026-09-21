from django import template
from django.core.exceptions import ObjectDoesNotExist

from ki_radar.architecture.architecture_advisor import explain_architecture
from ki_radar.architecture.architecture_assessment_forms import (
    SolutionArchitectureAssessmentForm,
)

register = template.Library()


@register.inclusion_tag("architecture/includes/architecture_advisor_panel.html")
def architecture_advisor_panel(option):
    if option is None:
        return {}

    try:
        assessment = option.architecture_assessment
    except ObjectDoesNotExist:
        assessment = None

    form = SolutionArchitectureAssessmentForm(instance=assessment)
    explanation = None
    if assessment is not None:
        explanation = explain_architecture(
            assessment.architecture_mode,
            assessment.reason_codes,
        )

    return {
        "option": option,
        "architecture_assessment": assessment,
        "architecture_assessment_form": form,
        "architecture_explanation": explanation,
    }
