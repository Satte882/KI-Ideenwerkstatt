from django import forms

from .solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES

LANE_LABELS = {
    "organizational": "Organisatorische Änderung",
    "rule_automation": "Regelbasierte Automatisierung",
    "assistant": "KI-/Assistenzlösung",
}

FIELD_LABELS = {
    "name": "Name",
    "description": "Lösungsbeschreibung",
    "expected_value": "Erwarteter Beitrag",
    "bottleneck_coverage": "Bottleneck-Abdeckung",
    "data_requirements": "Datenanforderungen",
    "application_impact": "Anwendungsauswirkung",
    "integration_impact": "Integrationen",
    "technology_constraints": "Technologieleitplanken",
    "risks": "Risiken",
    "architecture_fit": "Passung zu Zielbild und Leitplanken",
}

SOURCE_LABELS = {
    "process.name": "Prozessname",
    "process.scope_start": "Scope-Start",
    "process.scope_end": "Scope-Ende",
    "process.trigger": "Auslöser",
    "process.outcome": "Ergebnis",
    "process.current_flow": "Ist-Ablauf",
    "process.roles": "Rollen",
    "process.systems": "Systeme",
    "process.data_objects": "Datenobjekte",
    "process.business_rules": "Geschäftsregeln",
    "process.handoffs": "Übergaben",
    "process.bottlenecks": "Bottlenecks",
    "process.exceptions": "Ausnahmen",
    "process.baseline_metrics": "Baseline",
    "process.target_state_principles": "Zielbild-Prinzipien",
    "stage.name": "Value-Stream-Phase",
    "value_stream.constraints": "Value-Stream-Leitplanken",
}

READINESS_FIELD_LABELS = {
    "name": "Prozessname",
    "scope_start": "Scope-Start",
    "scope_end": "Scope-Ende",
    "trigger": "Auslöser",
    "outcome": "Ergebnis",
    "current_flow": "Ist-Ablauf",
    "roles": "Rollen",
    "systems": "Systeme",
    "data_objects": "Datenobjekte",
    "bottlenecks": "Bottlenecks",
    "baseline_metrics": "Baseline",
}

VALIDATION_LABELS = {
    "current_validated": "Aktuelle Prozessversion formal validiert",
    "not_validated": "Entwurfsquelle - noch nicht formal validiert",
    "validation_stale": "Validierung bezieht sich auf eine ältere Prozessversion",
}

UNCERTAINTY_LABELS = {
    "low": "Niedrig",
    "medium": "Mittel",
    "high": "Hoch",
}


def preview_form_field_name(lane: str, field_name: str) -> str:
    return f"{lane}__{field_name}"


class SolutionGenerationPreviewEditForm(forms.Form):
    def __init__(self, *args, preview_payload: dict, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        options = preview_payload.get("options", {})
        edits = preview_payload.get("edits", {})

        for lane in OPTION_LANES:
            option = options.get(lane, {})
            lane_edits = edits.get(lane, {})
            for field_name in GENERATED_OPTION_FIELDS:
                statement = option.get(field_name, {})
                original = str(statement.get("text", "")).strip()
                initial = str(lane_edits.get(field_name, original)).strip()
                widget = self._widget(field_name)
                field_kwargs = {
                    "label": FIELD_LABELS[field_name],
                    "required": True,
                    "initial": initial,
                    "widget": widget,
                }
                if field_name == "name":
                    field_kwargs["max_length"] = 200
                self.fields[preview_form_field_name(lane, field_name)] = forms.CharField(
                    **field_kwargs
                )

    @staticmethod
    def _widget(field_name: str):
        if field_name == "name":
            return forms.TextInput(attrs={"class": "form-control"})
        return forms.Textarea(attrs={"class": "form-control", "rows": 3})

    def normalized_edits(self, preview_payload: dict) -> dict[str, dict[str, str]]:
        options = preview_payload.get("options", {})
        edits: dict[str, dict[str, str]] = {}
        for lane in OPTION_LANES:
            lane_edits: dict[str, str] = {}
            for field_name in GENERATED_OPTION_FIELDS:
                key = preview_form_field_name(lane, field_name)
                value = self.cleaned_data[key].strip()
                original = str(options[lane][field_name]["text"]).strip()
                if value != original:
                    lane_edits[field_name] = value
            if lane_edits:
                edits[lane] = lane_edits
        return edits
