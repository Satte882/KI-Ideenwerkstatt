from django import forms
from django.db.models import Q

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_TECH_ADMIN,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel

from .focus import ValueStreamFocus, get_value_stream_focus
from .models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
    WorkDesignAssessment,
    WorkDesignTask,
)

FORM_CONTROL = "form-control"
FORM_SELECT = "form-select"
VALUE_STREAM_OWNER_GROUPS = (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_TECH_ADMIN,
)


def eligible_value_stream_owners():
    return (
        User.objects.filter(is_active=True, is_anonymized=False)
        .filter(Q(is_superuser=True) | Q(groups__name__in=VALUE_STREAM_OWNER_GROUPS))
        .distinct()
        .order_by("last_name", "first_name", "username")
    )


def is_eligible_value_stream_owner(user) -> bool:
    if user is None or not user.is_active or user.is_anonymized:
        return False
    return bool(
        user.is_superuser or user.groups.filter(name__in=VALUE_STREAM_OWNER_GROUPS).exists()
    )


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", FORM_SELECT)
            else:
                field.widget.attrs.setdefault("class", FORM_CONTROL)
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 3)


class ValueStreamForm(StyledModelForm):
    business_domain = forms.ChoiceField(
        choices=BusinessDomain.choices,
        label="Fachdomäne",
    )
    capability = forms.CharField(
        max_length=200,
        required=False,
        label="Business Capability",
    )
    strategic_impact = forms.ChoiceField(
        choices=[("", "Noch nicht bewertet"), *ScreeningLevel.choices],
        required=False,
        label="Strategischer Impact",
    )
    economic_potential = forms.ChoiceField(
        choices=[("", "Noch nicht bewertet"), *ScreeningLevel.choices],
        required=False,
        label="Wirtschaftliches Potenzial",
    )
    pain_intensity = forms.ChoiceField(
        choices=[("", "Noch nicht bewertet"), *ScreeningLevel.choices],
        required=False,
        label="Problem- und Schmerzintensität",
    )
    data_accessibility = forms.ChoiceField(
        choices=[("", "Noch nicht bewertet"), *ScreeningLevel.choices],
        required=False,
        label="Datenzugänglichkeit",
    )
    change_effort = forms.ChoiceField(
        choices=[("", "Noch nicht bewertet"), *ScreeningLevel.choices],
        required=False,
        label="Veränderungsaufwand",
    )
    focus_status = forms.ChoiceField(
        choices=ValueStreamFocus.Status.choices,
        label="Fokusentscheidung",
    )
    focus_rationale = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        label="Begründung der Fokusentscheidung",
    )

    class Meta:
        model = ValueStream
        fields = [
            "name",
            "business_unit",
            "owner",
            "status",
            "description",
            "trigger",
            "outcome",
            "scope_in",
            "scope_out",
            "strategic_objective",
            "stakeholders",
            "constraints",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "trigger": forms.Textarea(attrs={"rows": 3}),
            "outcome": forms.Textarea(attrs={"rows": 3}),
            "scope_in": forms.Textarea(attrs={"rows": 3}),
            "scope_out": forms.Textarea(attrs={"rows": 3}),
            "strategic_objective": forms.Textarea(attrs={"rows": 3}),
            "stakeholders": forms.Textarea(attrs={"rows": 3}),
            "constraints": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment_warnings = []

        business_units = BusinessUnit.objects.filter(is_active=True).order_by("name")
        owners = eligible_value_stream_owners()

        if self.instance.pk:
            if self.instance.business_unit_id and not self.instance.business_unit.is_active:
                business_units = BusinessUnit.objects.filter(
                    Q(is_active=True) | Q(pk=self.instance.business_unit_id)
                ).order_by("name")
                self.assignment_warnings.append(
                    "Die aktuell zugeordnete Organisationseinheit ist inaktiv. "
                    "Bitte vor dem Speichern eine aktive Organisationseinheit auswählen."
                )
            if self.instance.owner_id and not is_eligible_value_stream_owner(self.instance.owner):
                owners = (
                    User.objects.filter(
                        Q(
                            is_active=True,
                            is_anonymized=False,
                            groups__name__in=VALUE_STREAM_OWNER_GROUPS,
                        )
                        | Q(is_active=True, is_anonymized=False, is_superuser=True)
                        | Q(pk=self.instance.owner_id)
                    )
                    .distinct()
                    .order_by("last_name", "first_name", "username")
                )
                self.assignment_warnings.append(
                    "Die aktuell zugeordnete Person ist nicht mehr als Value-Stream-Owner "
                    "geeignet. Bitte vor dem Speichern eine aktive berechtigte Person auswählen."
                )

        self.fields["business_unit"].queryset = business_units
        self.fields["business_unit"].label = "Organisationseinheit"
        self.fields["business_unit"].help_text = (
            "Nur aktive Organisationseinheiten. Fehlende Einheiten können durch die "
            "Administration gepflegt werden."
        )
        self.fields["scope_in"].help_text = "Verbindlicher Umfang dieses Value Streams."
        self.fields[
            "scope_out"
        ].help_text = "Optional, aber empfohlen: ausdrücklich ausgeschlossene Bereiche."
        self.fields["owner"].queryset = owners
        self.fields["owner"].label = "Value-Stream-Owner"
        self.fields["owner"].help_text = (
            "Aktive Business Owner, KI-Koordinatoren oder Technische Administratoren. "
            "Die Rolle ist von Business Owner und Technical Owner "
            "eines späteren Use Cases getrennt."
        )

        focus = get_value_stream_focus(self.instance) if self.instance.pk else None
        if focus is not None and not self.is_bound:
            self.initial.update(
                {
                    "business_domain": focus.business_domain,
                    "capability": focus.capability,
                    "strategic_impact": focus.strategic_impact,
                    "economic_potential": focus.economic_potential,
                    "pain_intensity": focus.pain_intensity,
                    "data_accessibility": focus.data_accessibility,
                    "change_effort": focus.change_effort,
                    "focus_status": focus.status,
                    "focus_rationale": focus.rationale,
                }
            )
        else:
            self.initial.setdefault("business_domain", BusinessDomain.OTHER)
            self.initial.setdefault("focus_status", ValueStreamFocus.Status.NOT_SCREENED)

    def clean_business_unit(self):
        business_unit = self.cleaned_data["business_unit"]
        if not business_unit.is_active:
            raise forms.ValidationError(
                "Für einen Value Stream muss eine aktive Organisationseinheit gewählt werden."
            )
        return business_unit

    def clean_owner(self):
        owner = self.cleaned_data.get("owner")
        if owner is not None and not is_eligible_value_stream_owner(owner):
            raise forms.ValidationError(
                "Der Value-Stream-Owner muss aktiv und als Business Owner, "
                "KI-Koordinator oder Technischer Administrator berechtigt sein."
            )
        return owner

    def clean(self):
        cleaned = super().clean()
        focus_status = cleaned.get("focus_status")
        if focus_status == ValueStreamFocus.Status.NOT_SCREENED:
            return cleaned
        required = {
            "capability": "Business Capability",
            "strategic_impact": "Strategischer Impact",
            "economic_potential": "Wirtschaftliches Potenzial",
            "pain_intensity": "Problem- und Schmerzintensität",
            "data_accessibility": "Datenzugänglichkeit",
            "change_effort": "Veränderungsaufwand",
            "focus_rationale": "Begründung der Fokusentscheidung",
        }
        for field_name, label in required.items():
            if not str(cleaned.get(field_name, "")).strip():
                self.add_error(field_name, f"{label} ist für eine Fokusentscheidung erforderlich.")
        return cleaned

    def save(self, commit=True):
        value_stream = super().save(commit=False)
        value_stream._focus_payload = {
            "business_domain": self.cleaned_data["business_domain"],
            "capability": self.cleaned_data.get("capability", ""),
            "strategic_impact": self.cleaned_data.get("strategic_impact", ""),
            "economic_potential": self.cleaned_data.get("economic_potential", ""),
            "pain_intensity": self.cleaned_data.get("pain_intensity", ""),
            "data_accessibility": self.cleaned_data.get("data_accessibility", ""),
            "change_effort": self.cleaned_data.get("change_effort", ""),
            "status": self.cleaned_data["focus_status"],
            "rationale": self.cleaned_data.get("focus_rationale", ""),
        }
        if commit:
            value_stream.save()
        return value_stream


class ValueStreamStageForm(StyledModelForm):
    class Meta:
        model = ValueStreamStage
        fields = [
            "sequence",
            "name",
            "description",
            "actors",
            "systems",
            "documents",
            "pain_points",
            "baseline_metrics",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "actors": forms.Textarea(attrs={"rows": 3}),
            "systems": forms.Textarea(attrs={"rows": 3}),
            "documents": forms.Textarea(attrs={"rows": 3}),
            "pain_points": forms.Textarea(attrs={"rows": 4}),
            "baseline_metrics": forms.Textarea(attrs={"rows": 3}),
        }


class ProcessAnalysisForm(StyledModelForm):
    def clean_status(self):
        status = self.cleaned_data["status"]
        if status == ProcessAnalysis.Status.VALIDATED and (
            not self.instance.pk or self.instance.status != ProcessAnalysis.Status.VALIDATED
        ):
            raise forms.ValidationError(
                "Der Status 'Ist-Prozess validiert' wird ausschließlich über die "
                "eigenständige Validierungsaktion gesetzt."
            )
        return status

    class Meta:
        model = ProcessAnalysis
        fields = [
            "name",
            "status",
            "scope_start",
            "scope_end",
            "trigger",
            "outcome",
            "current_flow",
            "roles",
            "systems",
            "data_objects",
            "business_rules",
            "handoffs",
            "bottlenecks",
            "diagnostic_observations",
            "cause_hypotheses",
            "confirmed_causes",
            "constraints",
            "exceptions",
            "baseline_metrics",
            "target_state_principles",
        ]
        widgets = {
            "current_flow": forms.Textarea(attrs={"rows": 7}),
            "roles": forms.Textarea(attrs={"rows": 4}),
            "systems": forms.Textarea(attrs={"rows": 4}),
            "data_objects": forms.Textarea(attrs={"rows": 4}),
            "business_rules": forms.Textarea(attrs={"rows": 4}),
            "handoffs": forms.Textarea(attrs={"rows": 4}),
            "bottlenecks": forms.Textarea(attrs={"rows": 5}),
            "diagnostic_observations": forms.Textarea(attrs={"rows": 4}),
            "cause_hypotheses": forms.Textarea(attrs={"rows": 4}),
            "confirmed_causes": forms.Textarea(attrs={"rows": 4}),
            "constraints": forms.Textarea(attrs={"rows": 4}),
            "exceptions": forms.Textarea(attrs={"rows": 4}),
            "baseline_metrics": forms.Textarea(attrs={"rows": 4}),
            "target_state_principles": forms.Textarea(attrs={"rows": 5}),
        }
        help_texts = {
            "diagnostic_observations": (
                "Beschreibe das beobachtbare Symptom oder Problem, ohne eine Ursache "
                "zu unterstellen."
            ),
            "cause_hypotheses": (
                "Vermutete Ursache; Hypothesen bleiben ausdrücklich als unbestätigt gekennzeichnet."
            ),
            "confirmed_causes": "Nur fachlich oder durch Evidenz bestätigte Ursachen eintragen.",
            "constraints": (
                "Optional: Nur eintragen, wenn eine Randbedingung oder ein Engpass den "
                "Gesamtfluss begrenzt; ein lokales Problem ist nicht automatisch ein Constraint."
            ),
        }


WORK_DESIGN_SOURCE_AREAS = (
    "Marketing",
    "Sales",
    "Finance",
    "Legal",
    "IT / Engineering",
    "Customer Experience",
    "HR",
    "Operations",
    "Sonstiges",
)

WORK_DESIGN_CRITERIA = (
    "business_value",
    "handoff_friction",
    "recurrence",
    "context_proximity",
    "ai_leverage",
    "data_readiness",
    "judgment_stakes",
    "specialist_accountability",
)

WORK_DESIGN_CRITERION_HELP = {
    "business_value": "0 = kein erkennbarer Beitrag · 4 = hoher Beitrag zum Geschäftsergebnis",
    "handoff_friction": "0 = kaum Reibung · 4 = starke Warte- oder Übergabereibung",
    "recurrence": "0 = selten erwartet · 4 = häufig erwartet",
    "context_proximity": "0 = wenig Kontext in der Rolle · 4 = direkter Arbeitskontext",
    "ai_leverage": "0 = kaum sinnvoll unterstützbar · 4 = hoher KI-Hebel",
    "data_readiness": "0 = Daten fehlen weitgehend · 4 = Daten gut verfügbar und nutzbar",
    "judgment_stakes": "0 = geringe Tragweite · 4 = kritische fachliche Entscheidung",
    "specialist_accountability": (
        "0 = kaum gebundene Fachverantwortung · 4 = Verantwortung muss beim Spezialisten bleiben"
    ),
}


class WorkDesignAssessmentForm(StyledModelForm):
    class Meta:
        model = WorkDesignAssessment
        fields = ["role_name", "business_outcome"]
        widgets = {
            "business_outcome": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "role_name": (
                "Konkrete Rolle bewusst bestätigen oder eingeben. Der Rollenfreitext "
                "der Prozessanalyse wird nicht automatisch als Primärrolle interpretiert."
            ),
            "business_outcome": (
                "Welches Geschäftsergebnis soll durch die neue Aufgabenverteilung "
                "verbessert werden?"
            ),
        }


class WorkDesignRangeInput(forms.NumberInput):
    input_type = "range"


class WorkDesignTaskForm(StyledModelForm):
    source_area = forms.ChoiceField(
        choices=(("", "Nicht zugeordnet"), *((area, area) for area in WORK_DESIGN_SOURCE_AREAS)),
        required=False,
        label="Herkunftsbereich",
    )

    class Meta:
        model = WorkDesignTask
        fields = [
            "name",
            "source_area",
            "target_work_split",
            "approval_role",
            *WORK_DESIGN_CRITERIA,
        ]
        labels = {
            "business_value": "Geschäftswert",
            "handoff_friction": "Übergabereibung",
            "recurrence": "Erwartete Wiederholung",
            "context_proximity": "Kontextnähe",
            "ai_leverage": "KI-Hebel",
            "data_readiness": "Datenreife",
            "judgment_stakes": "Entscheidungsrisiko",
            "specialist_accountability": "Fachverantwortung",
        }
        widgets = {
            "target_work_split": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "target_work_split": (
                "Beschreibe knapp, welche Arbeit künftig bei der Rolle liegt und was "
                "beim Spezialisten bleibt."
            ),
            "approval_role": (
                "Bei relevanter Verantwortungsgrenze erforderlich; sonst kann das Feld "
                "leer bleiben."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_source_area = ""
        if self.instance.pk:
            current_source_area = self.instance.source_area
        if current_source_area and current_source_area not in WORK_DESIGN_SOURCE_AREAS:
            self.fields["source_area"].choices = (
                ("", "Nicht zugeordnet"),
                (current_source_area, current_source_area),
                *((area, area) for area in WORK_DESIGN_SOURCE_AREAS),
            )

        for field_name in WORK_DESIGN_CRITERIA:
            field = self.fields[field_name]
            field.required = True
            field.help_text = WORK_DESIGN_CRITERION_HELP[field_name]
            field.widget = WorkDesignRangeInput(
                attrs={
                    "min": 0,
                    "max": 4,
                    "step": 1,
                    "class": "form-range work-design-range",
                    "data-output": f"id_{field_name}_output",
                    "data-touched": f"id_{field_name}_touched",
                    "data-rating-ready": "false",
                    "disabled": "disabled",
                }
            )
            if not self.is_bound:
                current_value = getattr(self.instance, field_name, None)
                self.initial[field_name] = current_value if current_value is not None else 2

            touched_name = f"{field_name}_touched"
            self.fields[touched_name] = forms.CharField(
                required=False,
                widget=forms.HiddenInput,
                initial=(
                    "1"
                    if self.instance.pk and getattr(self.instance, field_name) is not None
                    else ""
                ),
            )

    def clean(self):
        cleaned = super().clean()
        for field_name in WORK_DESIGN_CRITERIA:
            touched_name = f"{field_name}_touched"
            if cleaned.get(touched_name) != "1":
                self.add_error(
                    field_name,
                    "Bitte diesen Regler einmal bewusst setzen; 2 ist eine echte "
                    "Bewertung, kein Default.",
                )
        return cleaned


class ProcessValidationForm(forms.Form):
    note = forms.CharField(
        required=False,
        label="Validierungsnotiz",
        widget=forms.Textarea(attrs={"rows": 4, "class": FORM_CONTROL}),
        help_text="Optional: geprüfte Grundlage, Einschränkungen oder Hinweise.",
    )
    evidence_url = forms.URLField(
        required=False,
        assume_scheme="https",
        label="Nachweis",
        widget=forms.URLInput(attrs={"class": FORM_CONTROL}),
        help_text="Optionaler Link auf Protokoll, Workshop-Ergebnis oder andere Evidenz.",
    )


class SolutionOptionForm(StyledModelForm):
    def __init__(self, *args, process_analysis=None, **kwargs):
        super().__init__(*args, **kwargs)
        if process_analysis is not None:
            self.process_analysis = process_analysis
        elif not self.instance._state.adding:
            self.process_analysis = self.instance.process_analysis
        else:
            self.process_analysis = None
        self.fields[
            "evaluation_status"
        ].help_text = (
            "Als bewertet markieren, sobald die Vergleichskriterien transparent dokumentiert sind."
        )
        self.fields["evidence_basis"].help_text = (
            "Kennzeichnet die Belastbarkeit der Aussagen zu Nutzen und Lösungsfit. "
            "Hypothesen sind zulässig, müssen aber als solche sichtbar bleiben."
        )
        self.fields["time_to_value"].help_text = (
            "Qualitativer Trade-off. 'Unbekannt' verwenden, wenn keine belastbare "
            "Zeitangabe vorliegt."
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("evaluation_status") != SolutionOption.EvaluationStatus.ASSESSED:
            return cleaned
        required = {
            "bottleneck_coverage": "Abdeckung von Bottleneck und Ursache",
            "data_requirements": "Datenanforderungen",
            "application_impact": "Auswirkung auf Anwendungen",
            "integration_impact": "Integrationen",
            "risks": "Risiken und Nachteile",
            "architecture_fit": "Begründung und Architecture Fit",
        }
        for field_name, label in required.items():
            if not str(cleaned.get(field_name, "")).strip():
                self.add_error(
                    field_name,
                    f"{label} ist für den Status 'Bewertet' erforderlich.",
                )
        return cleaned

    class Meta:
        model = SolutionOption
        fields = [
            "name",
            "option_type",
            "contains_ai_component",
            "evaluation_status",
            "evidence_basis",
            "description",
            "expected_value",
            "time_to_value",
            "bottleneck_coverage",
            "feasibility",
            "data_requirements",
            "application_impact",
            "integration_effort",
            "integration_impact",
            "technology_constraints",
            "risks",
            "architecture_fit",
        ]
        labels = {
            "option_type": "Lösungstyp",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "expected_value": forms.Textarea(attrs={"rows": 4}),
            "bottleneck_coverage": forms.Textarea(attrs={"rows": 4}),
            "data_requirements": forms.Textarea(attrs={"rows": 4}),
            "application_impact": forms.Textarea(attrs={"rows": 4}),
            "integration_impact": forms.Textarea(attrs={"rows": 4}),
            "technology_constraints": forms.Textarea(attrs={"rows": 4}),
            "risks": forms.Textarea(attrs={"rows": 4}),
            "architecture_fit": forms.Textarea(attrs={"rows": 5}),
        }


class SolutionSelectionForm(forms.Form):
    selected_option = forms.ModelChoiceField(
        queryset=SolutionOption.objects.none(),
        label="Bevorzugte Option",
        widget=forms.RadioSelect,
    )
    rationale = forms.CharField(
        label="Auswahlbegründung",
        widget=forms.Textarea(attrs={"rows": 5, "class": FORM_CONTROL}),
        help_text=(
            "Begründen Sie den Trade-off aus Problem-Fit, Nutzen, Risiko, Aufwand und "
            "Time-to-Value. KI, Nicht-KI und Hybrid sind gleichwertig zulässige Ergebnisse."
        ),
    )

    def __init__(self, *args, options=(), **kwargs):
        super().__init__(*args, **kwargs)
        option_ids = [option.pk for option in options]
        field = self.fields["selected_option"]
        field.queryset = SolutionOption.objects.filter(pk__in=option_ids)
        field.choices = [("", "---------"), *((option.pk, option.name) for option in options)]
