from __future__ import annotations

from django import forms

from .catalogs import CaptureSection


class CaptureStartForm(forms.Form):
    working_title = forms.CharField(
        max_length=200,
        label="Arbeitsbezeichnung",
        help_text="Eine kurze Bezeichnung, damit Sie parallele Entwürfe unterscheiden können.",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )


class CaptureSectionForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    active_entry_seconds = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.HiddenInput(attrs={"data-active-entry-seconds": ""}),
    )

    def __init__(self, *args, section: CaptureSection, initial_answers=None, revision=0, **kwargs):
        self.capture_section = section
        initial = dict(kwargs.pop("initial", {}) or {})
        initial["revision"] = revision
        initial["active_entry_seconds"] = 0
        for question in section.questions:
            initial[question.key] = (initial_answers or {}).get(question.key, "")
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

        for question in section.questions:
            if question.input_type == "textarea":
                widget = forms.Textarea(
                    attrs={
                        "class": "form-control",
                        "rows": question.rows,
                        "data-capture-question": question.key,
                    }
                )
            else:
                widget = forms.TextInput(
                    attrs={
                        "class": "form-control",
                        "autocomplete": "off",
                        "data-capture-question": question.key,
                    }
                )
            field = forms.CharField(
                required=False,
                max_length=question.max_length,
                label=question.label,
                help_text=question.help_text,
                widget=widget,
            )
            field.capture_required = question.required
            self.fields[question.key] = field

    @property
    def answer_fields(self):
        technical_fields = {"revision", "active_entry_seconds"}
        return [self[name] for name in self.fields if name not in technical_fields]

    def cleaned_answer_updates(self) -> dict[str, str]:
        return {
            question.key: self.cleaned_data.get(question.key, "")
            for question in self.capture_section.questions
        }
