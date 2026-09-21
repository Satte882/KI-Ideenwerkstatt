from django import forms

from .architecture_assessment_models import SolutionArchitectureAssessment


class SolutionArchitectureAssessmentForm(forms.ModelForm):
    class Meta:
        model = SolutionArchitectureAssessment
        fields = [
            "simpler_solution_sufficient",
            "semantic_reasoning_required",
            "multiple_known_ai_steps_required",
            "dynamic_orchestration_required",
        ]
        widgets = {
            "simpler_solution_sufficient": forms.RadioSelect(attrs={"class": "form-check-input"}),
            "semantic_reasoning_required": forms.RadioSelect(attrs={"class": "form-check-input"}),
            "multiple_known_ai_steps_required": forms.RadioSelect(
                attrs={"class": "form-check-input"}
            ),
            "dynamic_orchestration_required": forms.RadioSelect(
                attrs={"class": "form-check-input"}
            ),
        }
        labels = {
            "simpler_solution_sufficient": "Einfachere Lösung ausreichend?",
            "semantic_reasoning_required": "Semantisches Reasoning erforderlich?",
            "multiple_known_ai_steps_required": "Mehrere bekannte KI-Schritte erforderlich?",
            "dynamic_orchestration_required": "Dynamische Orchestrierung erforderlich?",
        }
