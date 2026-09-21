from django import forms

from ki_radar.accounts.models import BusinessUnit

from .idea_models import IdeaCandidate

FORM_CONTROL = "form-control"
FORM_SELECT = "form-select"


class IdeaCandidateForm(forms.ModelForm):
    class Meta:
        model = IdeaCandidate
        fields = ["title", "description", "business_unit", "source_note"]
        labels = {
            "title": "Kurztitel",
            "description": "Problem / Idee",
            "business_unit": "Organisationseinheit",
            "source_note": "Quelle / ursprünglicher Einreicher",
        }
        help_texts = {
            "description": "Beschreiben Sie Problem, Beobachtung oder Idee in wenigen Sätzen.",
            "business_unit": "Optional. Kann bei einer noch unscharfen Idee offen bleiben.",
            "source_note": (
                "Optional, z. B. Teams, Workshop, Miro oder Name des ursprünglichen Einreichers."
            ),
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "source_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business_unit"].queryset = BusinessUnit.objects.filter(is_active=True)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", FORM_CONTROL)
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = FORM_SELECT

    def clean_title(self):
        return self.cleaned_data["title"].strip()

    def clean_description(self):
        return self.cleaned_data["description"].strip()


class IdeaTriageForm(forms.ModelForm):
    class Meta:
        model = IdeaCandidate
        fields = ["impact", "confidence", "ease"]
        labels = {
            "impact": "Impact",
            "confidence": "Confidence",
            "ease": "Validierbarkeit",
        }
        help_texts = {
            "impact": (
                "1 = kleiner lokaler Effekt · 5 = erheblicher wirtschaftlicher/strategischer Effekt"
            ),
            "confidence": "1 = Annahme · 5 = gut belegte Ausgangslage. Nur Triage-Confidence.",
            "ease": "1 = schwer zu prüfen · 5 = sehr schnell und günstig validierbar",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
            field.widget.attrs["class"] = FORM_SELECT


class IdeaDismissForm(forms.Form):
    decision_note = forms.CharField(
        label="Begründung",
        min_length=3,
        widget=forms.Textarea(attrs={"rows": 4, "class": FORM_CONTROL}),
        help_text="Warum wird die Idee aktuell nicht weiterverfolgt?",
    )
