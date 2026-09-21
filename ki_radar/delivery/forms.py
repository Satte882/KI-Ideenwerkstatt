from functools import cached_property

from django import forms

from .actions import section_responsibility
from .ai_draft import log_ai_assist_event, mvp_scope_page_state, record_saved_assist
from .architecture_artifacts import get_delivery_architecture_artifacts
from .models import DELIVERY_SECTION_DEFINITIONS, DeliveryPackage
from .permissions import allowed_edit_sections
from .services import reset_section_reviews

FORM_CONTROL = "form-control"
SECTION_FIELDS = {
    "problem_and_target": [
        "problem_context",
        "target_outcome",
    ],
    "scope_and_users": [
        "in_scope",
        "out_of_scope",
        "users_and_scenarios",
        "mvp_scope",
        "should_scope",
        "could_scope",
        "wont_this_time",
    ],
    "solution_direction": [
        "solution_outline",
        "architecture_decisions",
    ],
    "architecture_and_data": [
        "system_context",
        "system_landscape",
        "system_responsibilities",
        "data_context",
        "data_quality_and_access",
        "data_flows",
        "integrations",
        "integration_contracts",
        "integration_operations",
        "architecture_artifacts_url",
    ],
    "requirements_and_governance": [
        "functional_requirements",
        "non_functional_requirements",
        "security_privacy_requirements",
        "human_oversight",
        "logging_and_audit",
        "operations_and_support",
    ],
    "acceptance_and_measurement": [
        "acceptance_criteria",
        "test_scenarios",
        "measurement_plan",
    ],
    "delivery_control": [
        "dependencies",
        "risks",
        "assumptions",
        "initial_backlog",
        "external_delivery_url",
        "handover_notes",
    ],
}
DELIVERY_PACKAGE_FIELDS = [
    field_name
    for section_key, _ in DELIVERY_SECTION_DEFINITIONS
    for field_name in SECTION_FIELDS[section_key]
]
ARTIFACT_FIELDS = {
    "system_landscape",
    "system_responsibilities",
    "data_flows",
    "data_quality_and_access",
    "integration_contracts",
    "integration_operations",
    "architecture_artifacts_url",
}
FIELD_TO_SECTION = {
    field_name: section_key
    for section_key, field_names in SECTION_FIELDS.items()
    for field_name in field_names
}


class DeliveryPackageForm(forms.ModelForm):
    ai_assist_run_id = forms.CharField(required=False, widget=forms.HiddenInput())
    ai_assist_edited = forms.CharField(required=False, widget=forms.HiddenInput())
    ai_assist_edit_ratio = forms.CharField(required=False, widget=forms.HiddenInput())
    system_landscape = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Ist-/Ziel-Systemlandschaft",
    )
    system_responsibilities = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Systemverantwortung und Zielkomponenten",
    )
    data_flows = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Daten- und Informationsflüsse",
    )
    data_quality_and_access = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Datenqualität, Zugriff und Schutzbedarf",
    )
    integration_contracts = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Integrationsverträge und Verantwortlichkeiten",
    )
    integration_operations = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Integrationsbetrieb und Fehlerbehandlung",
    )
    architecture_artifacts_url = forms.URLField(
        required=False,
        label="Externe Architekturartefakte und Diagramme (optional)",
        help_text=(
            "Optionaler Link auf vorhandene Diagramme oder Nachweise. Zielarchitektur/"
            "Systemkontext und Daten-/Informationsfluss werden direkt im Package dokumentiert."
        ),
    )

    class Meta:
        model = DeliveryPackage
        fields = DELIVERY_PACKAGE_FIELDS
        widgets = {
            name: forms.Textarea(attrs={"rows": 4})
            for name in DELIVERY_PACKAGE_FIELDS
            if name not in ARTIFACT_FIELDS | {"external_delivery_url"}
        }

    def __init__(self, *args, actor=None, active_section="", **kwargs):
        self.actor = actor
        self.active_section = active_section
        self.editable_sections: set[str] = set()
        super().__init__(*args, **kwargs)
        self._original_mvp_scope = self.instance.mvp_scope if self.instance.pk else ""
        artifacts = get_delivery_architecture_artifacts(self.instance) if self.instance.pk else None
        if artifacts is not None:
            self.initial.update(
                {
                    "system_landscape": artifacts.system_landscape,
                    "system_responsibilities": artifacts.system_responsibilities,
                    "data_flows": artifacts.data_flows,
                    "data_quality_and_access": artifacts.data_quality_and_access,
                    "integration_contracts": artifacts.integration_contracts,
                    "integration_operations": artifacts.integration_operations,
                    "architecture_artifacts_url": artifacts.artifacts_url,
                }
            )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", FORM_CONTROL)
        self.fields["functional_requirements"].widget.attrs["rows"] = 7
        self.fields["acceptance_criteria"].widget.attrs["rows"] = 7
        self.fields["initial_backlog"].widget.attrs["rows"] = 7

        if actor is not None and self.instance.pk:
            self.editable_sections = allowed_edit_sections(actor, self.instance)
            for section_key, field_names in SECTION_FIELDS.items():
                section_enabled = section_key in self.editable_sections and (
                    not self.active_section or section_key == self.active_section
                )
                if section_enabled:
                    continue
                for field_name in field_names:
                    if field_name in self.fields:
                        self.fields[field_name].disabled = True
                        self.fields[field_name].required = False

    @cached_property
    def mvp_scope_ai_state(self):
        show = bool(
            self.instance.pk
            and self.actor is not None
            and self.active_section == "scope_and_users"
            and "scope_and_users" in self.editable_sections
        )
        state = mvp_scope_page_state(self.instance, show=show)
        if state.show:
            log_ai_assist_event(
                "ai_assist_offered",
                package=self.instance,
                actor=self.actor,
                missing_count=len(state.static_missing),
            )
        return state

    @property
    def section_groups(self):
        labels = dict(DELIVERY_SECTION_DEFINITIONS)
        groups = []
        for section_key, _ in DELIVERY_SECTION_DEFINITIONS:
            role, person = section_responsibility(self.instance, section_key)
            groups.append(
                {
                    "key": section_key,
                    "label": labels[section_key],
                    "fields": [self[field_name] for field_name in SECTION_FIELDS[section_key]],
                    "editable": section_key in self.editable_sections,
                    "active": section_key == self.active_section,
                    "responsible_role": role,
                    "responsible_person": person,
                }
            )
        return groups

    @staticmethod
    def section_for_field(field_name: str) -> str:
        return FIELD_TO_SECTION.get(field_name, "")

    def _changed_sections(self) -> set[str]:
        changed = set(self.changed_data)
        return {
            section_key
            for section_key, field_names in SECTION_FIELDS.items()
            if changed.intersection(field_names)
        }

    def save(self, commit=True):
        blocker_before = not bool((self._original_mvp_scope or "").strip())
        package = super().save(commit=False)
        package._architecture_artifacts_payload = {
            "system_landscape": self.cleaned_data["system_landscape"],
            "system_responsibilities": self.cleaned_data["system_responsibilities"],
            "data_flows": self.cleaned_data["data_flows"],
            "data_quality_and_access": self.cleaned_data["data_quality_and_access"],
            "integration_contracts": self.cleaned_data["integration_contracts"],
            "integration_operations": self.cleaned_data["integration_operations"],
            "artifacts_url": self.cleaned_data.get("architecture_artifacts_url", ""),
        }
        changed_sections = self._changed_sections()
        if commit:
            package.save()
            self.save_m2m()
            if changed_sections:
                reset_section_reviews(package, changed_sections)
            record_saved_assist(
                package=package,
                actor=self.actor,
                run_id=self.cleaned_data.get("ai_assist_run_id", ""),
                edited_before_save=self.cleaned_data.get("ai_assist_edited", ""),
                edit_ratio=self.cleaned_data.get("ai_assist_edit_ratio", ""),
                blocker_before=blocker_before,
                blocker_after=not bool((package.mvp_scope or "").strip()),
            )
        return package
