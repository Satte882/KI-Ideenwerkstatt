from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

from ki_radar.accelerator.role_default_ui import attach_role_default
from ki_radar.accelerator.role_defaults import (
    resolve_use_case_business_owner,
    resolve_use_case_coordinator,
    resolve_use_case_technical_owner,
)
from ki_radar.accounts.models import BusinessUnit
from ki_radar.accounts.permissions import is_business_owner, is_coordinator
from ki_radar.core.taxonomy import BusinessDomain

from .form_fields import LocalizedDecimalInput
from .governance_status import build_governance_statuses
from .models import UseCase


def _user_choice_label(user) -> str:
    return user.get_display_name()


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class UseCaseForm(forms.ModelForm):
    business_domain = forms.ChoiceField(
        choices=BusinessDomain.choices,
        label="Fachdomäne",
    )
    business_capability = forms.CharField(
        max_length=200,
        label="Business Capability",
    )
    process_area = forms.CharField(
        max_length=200,
        required=False,
        label="Prozessbereich",
    )

    class Meta:
        model = UseCase
        fields = [
            "title",
            "summary",
            "problem_statement",
            "business_unit",
            "business_domain",
            "business_capability",
            "process_area",
            "affected_process",
            "target_users",
            "business_owner",
            "coordinator",
            "technical_owner",
            "priority",
            "next_review_date",
            "planned_pilot_end",
            "solution_type",
            "hosting_type",
            "provider",
            "product_name",
            "model_name",
            "source_systems",
            "data_sources",
            "interface_description",
            "intended_users",
            "intended_purpose",
            "expected_benefit",
            "benefit_category",
            "metric_name",
            "metric_type",
            "metric_direction",
            "metric_unit",
            "metric_baseline",
            "metric_target",
            "metric_measurement_method",
            "metric_actual",
            "metric_measurement_period",
            "metric_measured_at",
            "metric_evidence_url",
            "baseline",
            "success_criterion",
            "target_value",
            "realized_result",
            "one_time_cost",
            "recurring_cost",
            "business_value",
            "technical_feasibility",
            "data_readiness",
            "risk_complexity",
            "human_oversight",
            "support_responsibility",
        ]
        localized_fields = (
            "metric_baseline",
            "metric_target",
            "metric_actual",
            "one_time_cost",
            "recurring_cost",
        )
        widgets = {
            "next_review_date": DateInput(),
            "planned_pilot_end": DateInput(),
            "metric_measured_at": DateInput(),
            "metric_baseline": LocalizedDecimalInput(),
            "metric_target": LocalizedDecimalInput(),
            "metric_actual": LocalizedDecimalInput(),
            "one_time_cost": LocalizedDecimalInput(),
            "recurring_cost": LocalizedDecimalInput(),
            "problem_statement": forms.Textarea(attrs={"rows": 4}),
            "summary": forms.Textarea(attrs={"rows": 2}),
            "expected_benefit": forms.Textarea(attrs={"rows": 3}),
            "metric_measurement_method": forms.Textarea(attrs={"rows": 2}),
            "baseline": forms.Textarea(attrs={"rows": 2}),
            "success_criterion": forms.Textarea(attrs={"rows": 2}),
            "realized_result": forms.Textarea(attrs={"rows": 2}),
            "human_oversight": forms.Textarea(attrs={"rows": 2}),
            "support_responsibility": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "metric_name": "Genau eine primäre Kennzahl, an der der Pilot bewertet wird.",
            "metric_unit": "Zum Beispiel Minuten je Rechnung, Prozent, Euro oder Fälle pro Woche.",
            "metric_measurement_method": (
                "Wie und mit welcher Stichprobe wird die Kennzahl erhoben?"
            ),
            "metric_actual": "Erst zum Pilotabschluss eintragen.",
            "metric_evidence_url": "Link auf die freigegebene Auswertung oder den Messnachweis.",
        }
        labels = {
            "title": "Titel",
            "summary": "Kurzbeschreibung",
            "problem_statement": "Problemstellung",
            "business_unit": "Organisationseinheit",
            "affected_process": "Betroffener Prozess",
            "target_users": "Zielgruppe",
            "business_owner": "Business Owner",
            "coordinator": "KI-Koordinator",
            "technical_owner": "Technischer Owner",
            "priority": "Priorität",
            "next_review_date": "Nächster Entscheidungstermin",
            "planned_pilot_end": "Geplantes Pilotende",
            "solution_type": "Lösungstyp",
            "hosting_type": "Hosting",
            "provider": "Anbieter",
            "product_name": "Produktname",
            "model_name": "Modellname",
            "source_systems": "Quellsysteme",
            "data_sources": "Datenquellen",
            "interface_description": "Schnittstellenbeschreibung",
            "intended_users": "Vorgesehene Nutzer",
            "intended_purpose": "Vorgesehener Zweck",
            "expected_benefit": "Erwarteter Nutzen",
            "benefit_category": "Nutzenkategorie",
            "baseline": "Historische Baseline",
            "success_criterion": "Historisches Erfolgskriterium",
            "target_value": "Historischer Zielwert",
            "realized_result": "Historisches Ergebnis",
            "one_time_cost": "Einmalige Kosten",
            "recurring_cost": "Laufende Kosten",
            "business_value": "Business Value",
            "technical_feasibility": "Technische Machbarkeit",
            "data_readiness": "Datenreife",
            "risk_complexity": "Risiko und Komplexität",
            "human_oversight": "Menschliche Aufsicht",
            "support_responsibility": "Support-Verantwortung",
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            try:
                classification = self.instance.classification
            except ObjectDoesNotExist:
                classification = None
            if classification is not None:
                self.initial.update(
                    {
                        "business_domain": classification.business_domain,
                        "business_capability": classification.capability,
                        "process_area": classification.process_area,
                    }
                )
        self.initial.setdefault("business_domain", BusinessDomain.OTHER)
        self.initial.setdefault("process_area", self.initial.get("affected_process", ""))
        self.governance_statuses = build_governance_statuses(self.instance)
        self.governance_boundary_field = "human_oversight"
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-control"
                if not isinstance(field.widget, forms.CheckboxInput)
                else "form-check-input",
            )
        for field_name in [
            "business_unit",
            "business_domain",
            "business_owner",
            "coordinator",
            "technical_owner",
            "priority",
            "solution_type",
            "hosting_type",
            "metric_type",
            "metric_direction",
            "business_value",
            "technical_feasibility",
            "data_readiness",
            "risk_complexity",
        ]:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["class"] = "form-select"
        self.fields["business_unit"].queryset = BusinessUnit.objects.filter(is_active=True)
        user_model = get_user_model()
        active_users = list(
            user_model.objects.filter(is_active=True, is_anonymized=False)
            .prefetch_related("groups")
            .order_by("last_name", "first_name", "username")
        )
        active_ids = [user.pk for user in active_users]
        business_owner_ids = [user.pk for user in active_users if is_business_owner(user)]
        coordinator_ids = [user.pk for user in active_users if is_coordinator(user)]
        ordered_users = user_model.objects.order_by("last_name", "first_name", "username")
        self.fields["business_owner"].queryset = ordered_users.filter(pk__in=business_owner_ids)
        self.fields["coordinator"].queryset = ordered_users.filter(pk__in=coordinator_ids)
        self.fields["technical_owner"].queryset = ordered_users.filter(pk__in=active_ids)
        for field_name in ("business_owner", "coordinator", "technical_owner"):
            self.fields[field_name].label_from_instance = _user_choice_label
        self.fields["business_owner"].required = True

        role_source = self.instance if self.instance.pk else None
        attach_role_default(
            self.fields["business_owner"],
            resolve_use_case_business_owner(use_case=role_source),
        )
        attach_role_default(
            self.fields["coordinator"],
            resolve_use_case_coordinator(use_case=role_source),
        )
        attach_role_default(
            self.fields["technical_owner"],
            resolve_use_case_technical_owner(use_case=role_source),
        )

        if current_user and self.instance.pk and not is_coordinator(current_user):
            for name in ["business_owner", "coordinator"]:
                if name in self.fields:
                    self.fields[name].disabled = True

    def save(self, commit=True):
        use_case = super().save(commit=False)
        use_case._classification_payload = {
            "business_domain": self.cleaned_data["business_domain"],
            "capability": self.cleaned_data["business_capability"],
            "process_area": self.cleaned_data.get("process_area") or use_case.affected_process,
        }
        if commit:
            use_case.save()
            self.save_m2m()
        return use_case

    def clean(self):
        cleaned = super().clean()
        start = self.instance.pilot_start
        end = cleaned.get("planned_pilot_end")
        if start and end and end < start:
            self.add_error(
                "planned_pilot_end", "Das geplante Pilotende darf nicht vor dem Pilotbeginn liegen."
            )

        metric_type = cleaned.get("metric_type")
        baseline = cleaned.get("metric_baseline")
        target = cleaned.get("metric_target")
        actual = cleaned.get("metric_actual")
        direction = cleaned.get("metric_direction")
        if metric_type == UseCase.MetricType.PERCENT:
            for field_name, value in [
                ("metric_baseline", baseline),
                ("metric_target", target),
                ("metric_actual", actual),
            ]:
                if value is not None and not 0 <= value <= 100:
                    self.add_error(field_name, "Prozentwerte müssen zwischen 0 und 100 liegen.")
        if baseline is not None and target is not None:
            if baseline == target:
                self.add_error(
                    "metric_target",
                    "Der Zielwert muss sich von der Baseline unterscheiden.",
                )
            elif direction == UseCase.MetricDirection.LOWER and target > baseline:
                self.add_error(
                    "metric_target",
                    "Bei 'Niedriger ist besser' muss der Zielwert unter der Baseline liegen.",
                )
            elif direction == UseCase.MetricDirection.HIGHER and target < baseline:
                self.add_error(
                    "metric_target",
                    "Bei 'Höher ist besser' muss der Zielwert über der Baseline liegen.",
                )
        return cleaned
