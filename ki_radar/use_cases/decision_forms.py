from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ki_radar.accelerator.role_default_guard import validate_second_approver_suggestion
from ki_radar.accelerator.role_default_ui import attach_role_default
from ki_radar.accelerator.role_defaults import (
    SUGGESTION,
    resolve_condition_owner,
    resolve_second_approver,
)

from .models import ApprovalDecision, DecisionAssessment, UseCase
from .services import eligible_second_approvers

CONDITIONAL_APPROVAL_FIELDS = (
    "conditions",
    "condition_owner",
    "condition_due_date",
    "second_approval_assignee",
)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class DecisionAssessmentForm(forms.ModelForm):
    class Meta:
        model = DecisionAssessment
        fields = [
            "assessment_date",
            "business_value",
            "strategic_fit",
            "technical_feasibility",
            "data_readiness",
            "risk_complexity",
            "evidence_quality",
            "evidence_recency",
            "evidence_coverage",
            "independent_review",
            "assumptions_resolved",
            "evidence_url",
            "rationale",
            "governance_precheck_completed",
            "recommendation",
        ]
        widgets = {
            "assessment_date": DateInput(),
            "rationale": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "assessment_date": "Bewertungsdatum",
            "business_value": "Wirtschaftlicher Nutzen",
            "strategic_fit": "Strategischer Beitrag",
            "technical_feasibility": "Technische Machbarkeit",
            "data_readiness": "Datenverfügbarkeit und -qualität",
            "risk_complexity": "Risiko und Komplexität",
            "evidence_quality": "Qualität der Evidenz",
            "evidence_recency": "Aktualität der Evidenz",
            "evidence_coverage": "Abdeckung der Evidenz",
            "independent_review": "Unabhängige Prüfung",
            "assumptions_resolved": "Klärung offener Annahmen",
            "evidence_url": "Nachweislink",
            "rationale": "Bewertungsbegründung",
            "governance_precheck_completed": "Governance-Screening im Assessment dokumentiert",
            "recommendation": "Empfohlene Entscheidung",
        }
        help_texts = {
            "evidence_url": (
                "Bei einer unbestätigten Annahme optional. Ab einer fachlichen Einschätzung "
                "ist ein Link auf Analyse, Messung oder freigegebenen Nachweis erforderlich."
            ),
            "governance_precheck_completed": (
                "Dieses Screening identifiziert nur Governance-Themen. Es ersetzt keine formale "
                "Datenschutz-, Security- oder Rechtsprüfung und deren Nachweise."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected_quality = (
            self.data.get("evidence_quality")
            if self.is_bound
            else self.initial.get("evidence_quality", self.instance.evidence_quality)
        )
        evidence_required = bool(selected_quality) and str(selected_quality) != str(
            DecisionAssessment.EvidenceQuality.ASSUMPTION
        )
        self.fields["evidence_url"].required = evidence_required
        self.fields["evidence_url"].widget.attrs["data-evidence-url"] = "true"
        self.fields["evidence_url"].widget.attrs["aria-required"] = (
            "true" if evidence_required else "false"
        )
        self.fields["evidence_quality"].widget.attrs["data-evidence-quality"] = "true"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        for name in [
            "business_value",
            "strategic_fit",
            "technical_feasibility",
            "data_readiness",
            "risk_complexity",
            "evidence_quality",
            "evidence_recency",
            "evidence_coverage",
            "independent_review",
            "assumptions_resolved",
            "recommendation",
        ]:
            self.fields[name].widget.attrs["class"] = "form-select"
        self.fields["governance_precheck_completed"].widget.attrs["class"] = "form-check-input"


class ApprovalDecisionForm(forms.ModelForm):
    class Meta:
        model = ApprovalDecision
        fields = [
            "decision_status",
            "rationale",
            "governance_confirmed",
            "conditions",
            "condition_owner",
            "condition_due_date",
            "second_approval_assignee",
        ]
        widgets = {
            "rationale": forms.Textarea(attrs={"rows": 5}),
            "conditions": forms.Textarea(attrs={"rows": 4}),
            "condition_due_date": DateInput(),
        }
        labels = {
            "decision_status": "Entscheidung",
            "rationale": "Entscheidungsbegründung",
            "governance_confirmed": "Governance-Vorprüfung separat bestätigt",
            "conditions": "Auflagen",
            "condition_owner": "Verantwortliche Person für die Auflage",
            "condition_due_date": "Fälligkeit der Auflage",
            "second_approval_assignee": "Bevorzugte unabhängige Zweitprüfung",
        }
        help_texts = {
            "governance_confirmed": (
                "Diese Bestätigung dokumentiert die Prüfung der Governance-Grundlage. "
                "Sie ersetzt weder offene Fachprüfungen noch die erforderliche "
                "Personentrennung."
            ),
            "conditions": (
                "Beschreiben Sie jede Auflage so, dass Erfüllung und Nachweis eindeutig "
                "geprüft werden können."
            ),
            "condition_owner": (
                "Diese Person verantwortet die fristgerechte Erfüllung und den Nachweis "
                "der Auflage."
            ),
            "condition_due_date": (
                "Bis zu diesem Datum müssen die Auflage erfüllt und der Nachweis verfügbar sein."
            ),
            "second_approval_assignee": (
                "Die Zuweisung benennt die bevorzugte prüfende Person. Andere ebenfalls "
                "unabhängige und berechtigte Personen können die Aufgabe übernehmen."
            ),
        }

    def __init__(self, *args, actor=None, use_case=None, **kwargs):
        self.actor = actor
        self.use_case = use_case
        super().__init__(*args, **kwargs)
        self.fields["decision_status"].choices = [
            (UseCase.DecisionStatus.DEFERRED, UseCase.DecisionStatus.DEFERRED.label),
            (UseCase.DecisionStatus.APPROVED, UseCase.DecisionStatus.APPROVED.label),
            (
                UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
                UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS.label,
            ),
            (UseCase.DecisionStatus.NOT_PURSUED, UseCase.DecisionStatus.NOT_PURSUED.label),
        ]
        users = (
            get_user_model()
            .objects.filter(is_active=True, is_anonymized=False)
            .order_by("last_name", "first_name", "username")
        )
        self.fields["condition_owner"].queryset = users
        self.fields["second_approval_assignee"].queryset = (
            eligible_second_approvers(use_case=use_case, first_decider=actor)
            if use_case is not None and actor is not None
            else users.none()
        )
        attach_role_default(self.fields["condition_owner"], resolve_condition_owner())
        if use_case is not None and actor is not None:
            attach_role_default(
                self.fields["second_approval_assignee"],
                resolve_second_approver(use_case=use_case, first_decider=actor),
            )
        selected_status = (
            self.data.get("decision_status")
            if self.is_bound
            else self.initial.get("decision_status")
        )
        conditional_required = selected_status == UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS
        for field_name in CONDITIONAL_APPROVAL_FIELDS:
            field = self.fields[field_name]
            field.required = conditional_required
            field.widget.attrs["data-conditional-required"] = "true"
            field.widget.attrs["aria-required"] = "true" if conditional_required else "false"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["decision_status"].widget.attrs["class"] = "form-select"
        self.fields["condition_owner"].widget.attrs["class"] = "form-select"
        self.fields["second_approval_assignee"].widget.attrs["class"] = "form-select"
        self.fields["governance_confirmed"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision_status") == UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS:
            for field_name in CONDITIONAL_APPROVAL_FIELDS:
                if not cleaned.get(field_name):
                    self.add_error(
                        field_name,
                        "Dieses Feld ist für eine Freigabe mit Auflagen erforderlich.",
                    )
        else:
            cleaned["second_approval_assignee"] = None
            return cleaned

        assignee = cleaned.get("second_approval_assignee")
        resolution = getattr(self.fields["second_approval_assignee"], "role_default", None)
        if (
            assignee is not None
            and resolution is not None
            and resolution.state == SUGGESTION
            and resolution.user_id == assignee.pk
            and self.use_case is not None
            and self.actor is not None
        ):
            try:
                validate_second_approver_suggestion(
                    use_case=self.use_case,
                    first_decider=self.actor,
                    submitted_user_id=assignee.pk,
                )
            except ValidationError as exc:
                self.add_error("second_approval_assignee", exc)
        return cleaned


class SecondApprovalReviewForm(forms.Form):
    return_reason = forms.CharField(
        required=False,
        label="Begründung der Rückgabe",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )

    def clean(self):
        cleaned = super().clean()
        action = self.data.get("action", "")
        if action not in {"confirm", "return"}:
            raise forms.ValidationError("Unbekannte Aktion für die Zweitprüfung.")
        if action == "return" and not (cleaned.get("return_reason") or "").strip():
            self.add_error(
                "return_reason",
                "Für die Rückgabe ist eine konkrete Begründung erforderlich.",
            )
        cleaned["action"] = action
        return cleaned
