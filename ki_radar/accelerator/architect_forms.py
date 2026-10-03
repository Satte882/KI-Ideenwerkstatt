from __future__ import annotations

from django import forms

from ki_radar.accounts.models import BusinessUnit


class AutonomousDiscoveryStartForm(forms.Form):
    business_unit = forms.ModelChoiceField(
        label="Organisationseinheit der Untersuchung",
        queryset=BusinessUnit.objects.none(),
        empty_label="Bitte auswählen",
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={
            "required": "Bitte wählen Sie eine Organisationseinheit für die Untersuchung.",
            "invalid_choice": "Bitte wählen Sie eine verfügbare aktive Organisationseinheit.",
        },
    )
    problem_statement = forms.CharField(
        label="Geschäftsproblem oder Ziel",
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "class": "form-control",
                "placeholder": (
                    "Beispiel: Die Bearbeitung von Lieferantenangeboten dauert zu lange. "
                    "Angebote kommen per Mail und als Dokumente und werden manuell verglichen."
                ),
            }
        ),
    )
    business_context = forms.CharField(
        label="Zusätzlicher Geschäftskontext",
        max_length=8000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": (
                    "Optional: relevante Organisation, Ziele oder feste Randbedingungen."
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business_unit"].queryset = BusinessUnit.objects.filter(is_active=True)


class DiscoveryCorrectionForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    correction = forms.CharField(
        label="Korrektur oder Klärung",
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": "Nur die fachlich relevante Korrektur oder Antwort angeben.",
            }
        ),
    )


class DiscoveryConfirmForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    selected_stage_key = forms.ChoiceField(
        label="Fokusphase",
        choices=(),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, stage_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["selected_stage_key"].choices = tuple(stage_choices)
