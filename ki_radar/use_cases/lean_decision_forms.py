# ruff: noqa: I001
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance

from .decision_forms import (
    ApprovalDecisionForm as LegacyApprovalDecisionForm,
    DecisionAssessmentForm as LegacyDecisionAssessmentForm,
    SecondApprovalReviewForm as LegacySecondApprovalReviewForm,
)
from .models import UseCase


class DecisionAssessmentForm(LegacyDecisionAssessmentForm):
    """Assessment evidence links are advisory, not a form-level workflow gate."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["evidence_url"].required = False
        self.fields["evidence_url"].widget.attrs["aria-required"] = "false"
        self.fields["evidence_url"].help_text = (
            "Nachweislink empfohlen. Eine Bewertung kann auch ohne Link gespeichert "
            "und später ergänzt werden."
        )

    def _post_clean(self):
        # Form fields already validate their data types. Skip DecisionAssessment.clean(), whose
        # former evidence-link hard gate is intentionally Advisory in #403.
        try:
            self.instance = construct_instance(
                self,
                self.instance,
                self._meta.fields,
                self._meta.exclude,
            )
        except ValidationError as exc:
            self._update_errors(exc)
        if self._validate_unique:
            self.validate_unique()


class ApprovalDecisionForm(LegacyApprovalDecisionForm):
    """Keep semantic approval guards, drop scheduling/documentation-only hard gates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["condition_due_date"].required = False
        self.fields["condition_due_date"].widget.attrs["aria-required"] = "false"

    def clean(self):
        cleaned = forms.ModelForm.clean(self)
        if cleaned.get("decision_status") == UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS:
            for field_name in ("conditions", "condition_owner", "second_approval_assignee"):
                if not cleaned.get(field_name):
                    self.add_error(
                        field_name,
                        "Dieses Feld ist für eine Freigabe mit Auflagen erforderlich.",
                    )
        else:
            cleaned["second_approval_assignee"] = None
        return cleaned


class SecondApprovalReviewForm(LegacySecondApprovalReviewForm):
    """A return reason is Readiness, not a prerequisite for returning a proposal."""

    def clean(self):
        cleaned = forms.Form.clean(self)
        action = self.data.get("action", "")
        if action not in {"confirm", "return"}:
            raise forms.ValidationError("Unbekannte Aktion für die Zweitprüfung.")
        cleaned["action"] = action
        return cleaned
