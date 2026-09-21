from __future__ import annotations

from django import forms

from ki_radar.core.taxonomy import ScreeningLevel

from .models import EvidenceBasis, TimeToValue, ValueStreamStage
from .stage_focus import CRITERIA_KEYS, EVIDENCE_BASIS_KEY

FORM_CONTROL = "form-control"
FORM_SELECT = "form-select"
CRITERIA_LABELS = {
    "impact": "Impact",
    "pain_intensity": "Problemintensität",
    "improvement_potential": "Verbesserungspotenzial",
    "data_accessibility": "Datenlage",
    "change_effort": "Veränderungsaufwand",
    "time_to_value": "Time-to-Value",
}


class StageFocusForm(forms.Form):
    selected_stage = forms.ModelChoiceField(
        queryset=ValueStreamStage.objects.none(),
        label="Fokusphase",
        widget=forms.RadioSelect,
    )
    rationale = forms.CharField(
        label="Begründung der Fokusphase",
        widget=forms.Textarea(attrs={"rows": 4, "class": FORM_CONTROL}),
    )
    is_short_path = forms.BooleanField(
        required=False,
        label="Bewussten Kurzpfad verwenden",
        help_text=(
            "Nur verwenden, wenn eine Phase ohne Vollvergleich offensichtlich ist. "
            "Die Ausnahme bleibt nachvollziehbar dokumentiert."
        ),
    )
    short_path_reason = forms.CharField(
        required=False,
        label="Begründung des Kurzpfads",
        widget=forms.Textarea(attrs={"rows": 3, "class": FORM_CONTROL}),
    )

    def __init__(self, *args, value_stream, decision=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.value_stream = value_stream
        self.decision = decision
        self.stages = list(value_stream.stages.all())
        self.fields["selected_stage"].queryset = value_stream.stages.all()
        snapshot = decision.criteria_snapshot if decision else {}

        if decision and not self.is_bound:
            self.initial.update(
                {
                    "selected_stage": decision.selected_stage_id,
                    "rationale": decision.rationale,
                    "is_short_path": decision.is_short_path,
                    "short_path_reason": decision.short_path_reason,
                }
            )

        self.stage_rows = []
        ttv_choices = [
            ("", "Noch nicht bewertet"),
            (TimeToValue.UNKNOWN, TimeToValue.UNKNOWN.label),
            (TimeToValue.SHORT, TimeToValue.SHORT.label),
            (TimeToValue.MEDIUM, TimeToValue.MEDIUM.label),
            (TimeToValue.LONG, TimeToValue.LONG.label),
        ]
        evidence_choices = [("", "Noch nicht eingeordnet"), *EvidenceBasis.choices]
        for stage in self.stages:
            stage_key = stage.pk.hex
            saved = snapshot.get(str(stage.pk), {})
            row = {"stage": stage, "fields": []}
            for criterion in CRITERIA_KEYS:
                field_name = f"{criterion}_{stage_key}"
                choices = (
                    ttv_choices
                    if criterion == "time_to_value"
                    else [("", "Noch nicht bewertet"), *ScreeningLevel.choices]
                )
                self.fields[field_name] = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label=CRITERIA_LABELS[criterion],
                    widget=forms.Select(attrs={"class": FORM_SELECT}),
                    initial=saved.get(criterion, ""),
                )
                row["fields"].append(self[field_name])

            evidence_field = f"{EVIDENCE_BASIS_KEY}_{stage_key}"
            self.fields[evidence_field] = forms.ChoiceField(
                choices=evidence_choices,
                required=False,
                label="Evidenzbasis",
                help_text=(
                    "Hypothese ist in früher Discovery zulässig. Indiz oder Messwert nur wählen, "
                    "wenn die gespeicherten Indikatoren diese Einordnung tragen."
                ),
                widget=forms.Select(attrs={"class": FORM_SELECT}),
                initial=saved.get(EVIDENCE_BASIS_KEY, ""),
            )
            row["fields"].append(self[evidence_field])
            self.stage_rows.append(row)

    def clean(self):
        cleaned = super().clean()
        selected_stage = cleaned.get("selected_stage")
        if selected_stage and selected_stage.value_stream_id != self.value_stream.pk:
            self.add_error("selected_stage", "Die Fokusphase gehört nicht zu diesem Value Stream.")

        if cleaned.get("is_short_path"):
            if not str(cleaned.get("short_path_reason", "")).strip():
                self.add_error(
                    "short_path_reason",
                    "Der bewusste Kurzpfad muss konkret begründet werden.",
                )
            return cleaned

        for stage in self.stages:
            for criterion in (*CRITERIA_KEYS, EVIDENCE_BASIS_KEY):
                field_name = f"{criterion}_{stage.pk.hex}"
                if not cleaned.get(field_name):
                    self.add_error(
                        field_name,
                        "Für den vollständigen Vergleich ist eine Einordnung erforderlich.",
                    )
        return cleaned

    def criteria_snapshot(self) -> dict:
        snapshot = {}
        for stage in self.stages:
            stage_key = stage.pk.hex
            snapshot[str(stage.pk)] = {
                "sequence": stage.sequence,
                "name": stage.name,
                **{
                    criterion: self.cleaned_data.get(f"{criterion}_{stage_key}", "")
                    for criterion in CRITERIA_KEYS
                },
                EVIDENCE_BASIS_KEY: self.cleaned_data.get(f"{EVIDENCE_BASIS_KEY}_{stage_key}", ""),
                "indicators": {
                    "description": stage.description,
                    "pain_points": stage.pain_points,
                    "baseline_metrics": stage.baseline_metrics,
                    "actors": stage.actors,
                    "systems": stage.systems,
                    "documents": stage.documents,
                },
            }
        return snapshot
