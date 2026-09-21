from django import forms
from django.utils import timezone

from .models import GovernanceAssessment, GovernanceReview


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class GovernanceAssessmentForm(forms.ModelForm):
    class Meta:
        model = GovernanceAssessment
        fields = [
            "assessment_date",
            "basis_version",
            "personal_data",
            "employee_data",
            "automated_person_assessment",
            "influences_person_decisions",
            "biometric_data",
            "safety_critical",
            "regulated_product",
            "health_safety_rights_impact",
            "external_ai_or_cloud",
            "generated_external_content",
            "human_oversight_planned",
            "privacy_review_required",
            "privacy_review_rationale",
            "security_review_required",
            "security_review_rationale",
            "legal_review_required",
            "legal_review_rationale",
            "result",
            "rationale",
            "evidence_url",
            "next_assessment_date",
        ]
        widgets = {
            "assessment_date": DateInput(),
            "next_assessment_date": DateInput(),
            "privacy_review_rationale": forms.Textarea(attrs={"rows": 2}),
            "security_review_rationale": forms.Textarea(attrs={"rows": 2}),
            "legal_review_rationale": forms.Textarea(attrs={"rows": 2}),
            "rationale": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "assessment_date": "Screening-Datum",
            "basis_version": "Prüfgrundlage / Version",
            "personal_data": "Personenbezogene Daten",
            "employee_data": "Beschäftigtendaten",
            "automated_person_assessment": "Automatisierte Personenbewertung",
            "influences_person_decisions": "Beeinflusst Entscheidungen über Personen",
            "biometric_data": "Biometrische Daten",
            "safety_critical": "Sicherheitskritischer Einsatz",
            "regulated_product": "Reguliertes Produkt",
            "health_safety_rights_impact": "Auswirkung auf Gesundheit, Sicherheit oder Rechte",
            "external_ai_or_cloud": "Externe KI oder Cloud",
            "generated_external_content": "Extern veröffentlichte generierte Inhalte",
            "human_oversight_planned": "Menschliche Aufsicht geplant",
            "privacy_review_required": "Datenschutzprüfung erforderlich",
            "privacy_review_rationale": "Begründung Datenschutz-Prüfbedarf",
            "security_review_required": "Security-Prüfung erforderlich",
            "security_review_rationale": "Begründung Security-Prüfbedarf",
            "legal_review_required": "Rechtsprüfung erforderlich",
            "legal_review_rationale": "Begründung Rechts-Prüfbedarf",
            "result": "Screening-Ergebnis",
            "rationale": "Übergreifende Screening-Begründung",
            "evidence_url": "Screening-Nachweislink",
            "next_assessment_date": "Nächstes Screening",
        }
        help_texts = {
            "privacy_review_rationale": "Optionaler Hinweis zum Datenschutz-Prüfbedarf.",
            "security_review_rationale": "Optionaler Hinweis zum Security-Prüfbedarf.",
            "legal_review_rationale": "Optionaler Hinweis zum Rechts-Prüfbedarf.",
            "rationale": "Empfohlen für Nachvollziehbarkeit; blockiert das Screening nicht.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assessment_date"].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control",
            )


class GovernanceReviewForm(forms.ModelForm):
    class Meta:
        model = GovernanceReview
        fields = [
            "reviewed_at",
            "responsible_role",
            "result",
            "rationale",
            "risks",
            "measures",
            "conditions",
            "evidence_url",
        ]
        widgets = {
            "reviewed_at": DateInput(),
            "rationale": forms.Textarea(attrs={"rows": 4}),
            "risks": forms.Textarea(attrs={"rows": 3}),
            "measures": forms.Textarea(attrs={"rows": 3}),
            "conditions": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "reviewed_at": "Prüfdatum",
            "responsible_role": "Verantwortliche Fachrolle",
            "result": "Prüfergebnis",
            "rationale": "Begründung und wesentliche Feststellungen",
            "risks": "Festgestellte Risiken",
            "measures": "Maßnahmen",
            "conditions": "Auflagen",
            "evidence_url": "Nachweislink",
        }
        help_texts = {
            "evidence_url": "Empfohlen als Nachweisreferenz; blockiert den Abschluss nicht.",
            "rationale": "Empfohlen für Nachvollziehbarkeit; blockiert den Abschluss nicht.",
            "conditions": "Bei 'Bestanden mit Auflagen' verpflichtend.",
            "risks": "Bei 'Nicht bestanden' als Readiness-Hinweis nachziehbar.",
            "measures": "Bei 'Nicht bestanden' als Readiness-Hinweis nachziehbar.",
        }

    def __init__(self, *args, responsible_role="", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reviewed_at"].initial = timezone.localdate()
        self.fields["responsible_role"].required = True
        self.fields["responsible_role"].initial = responsible_role
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
