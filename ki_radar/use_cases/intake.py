from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ki_radar.accelerator.role_default_guard import validate_business_owner_suggestion
from ki_radar.accelerator.role_default_ui import attach_role_default
from ki_radar.accelerator.role_defaults import SUGGESTION, resolve_use_case_business_owner
from ki_radar.accounts.models import BusinessUnit
from ki_radar.accounts.permissions import is_business_owner
from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.core.taxonomy import BusinessDomain

from .form_fields import LocalizedDecimalField
from .models import UseCase

FORM_CONTROL = "form-control"
FORM_SELECT = "form-select"


class IntakeStepForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", FORM_CONTROL)
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = FORM_SELECT
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"


class ProblemStepForm(IntakeStepForm):
    title = forms.CharField(max_length=200, label="Kurztitel")
    business_unit = forms.ModelChoiceField(
        queryset=BusinessUnit.objects.none(), label="Organisationseinheit"
    )
    business_owner = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        label="Business Owner",
        help_text="Die fachlich verantwortliche Person wird ausdrücklich gewählt.",
    )
    problem_statement = forms.CharField(
        label="Welches Problem soll gelöst werden?",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=(
            "Beschreiben Sie beobachtbare Auswirkungen. Vermeiden Sie reine Lösungswünsche wie "
            "„Wir benötigen einen Chatbot“."
        ),
    )

    def __init__(self, *args, value_stream=None, **kwargs):
        self.value_stream = value_stream
        super().__init__(*args, **kwargs)
        self.fields["business_unit"].queryset = BusinessUnit.objects.filter(is_active=True)
        user_model = get_user_model()
        active_users = list(
            user_model.objects.filter(is_active=True, is_anonymized=False)
            .prefetch_related("groups")
            .order_by("last_name", "first_name", "username")
        )
        eligible_ids = [user.pk for user in active_users if is_business_owner(user)]
        self.fields["business_owner"].queryset = user_model.objects.filter(
            pk__in=eligible_ids
        ).order_by("last_name", "first_name", "username")
        attach_role_default(
            self.fields["business_owner"],
            resolve_use_case_business_owner(value_stream=value_stream),
        )

    def clean_problem_statement(self):
        value = self.cleaned_data["problem_statement"].strip()
        technology_only = ["chatbot", "ki-tool", "ki tool", "copilot", "llm"]
        if len(value.split()) < 8 and any(term in value.lower() for term in technology_only):
            raise forms.ValidationError(
                "Bitte beschreiben Sie das konkrete Problem und seine Auswirkung, nicht nur eine "
                "gewünschte Technologie."
            )
        return value

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get("business_owner")
        resolution = getattr(self.fields["business_owner"], "role_default", None)
        if (
            selected is not None
            and self.value_stream is not None
            and resolution is not None
            and resolution.state == SUGGESTION
            and resolution.user_id == selected.pk
        ):
            try:
                validate_business_owner_suggestion(
                    submitted_user_id=selected.pk,
                    value_stream=self.value_stream,
                )
            except ValidationError as exc:
                self.add_error("business_owner", exc)
        return cleaned


class ProcessStepForm(IntakeStepForm):
    process_analysis = forms.ModelChoiceField(
        queryset=ProcessAnalysis.objects.none(),
        required=False,
        label="Ursprungsprozess",
        empty_label="Keinen Ursprungsprozess verknüpfen",
        help_text=(
            "Optional: vorhandene Prozessanalyse verknüpfen. Phase, Value Stream und "
            "strategischer Kontext werden daraus abgeleitet."
        ),
    )
    business_domain = forms.ChoiceField(
        choices=BusinessDomain.choices,
        label="Fachdomäne",
        help_text="Fachliche Zuordnung unabhängig von der organisatorischen Verantwortung.",
    )
    business_capability = forms.CharField(
        max_length=200,
        label="Business Capability",
        help_text="Zum Beispiel Source-to-Pay, Accounts Payable oder Customer Service Management.",
    )
    affected_process = forms.CharField(
        max_length=200,
        required=False,
        label="Betroffener Prozess",
        help_text=(
            "Nur manuell pflegen, wenn kein Ursprungsprozess verknüpft wird. "
            "Bei Auswahl wird der Prozessname automatisch übernommen."
        ),
    )
    summary = forms.CharField(
        label="Kurzbeschreibung des Vorhabens",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Fasse die geplante Unterstützung und ihren fachlichen Zweck in zwei bis drei "
            "Sätzen zusammen. Der heutige Ablauf bleibt über den Ursprungsprozess nachvollziehbar."
        ),
    )
    target_users = forms.CharField(
        label="Beteiligte und betroffene Personen",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    source_systems = forms.CharField(
        required=False,
        label="Heute verwendete Systeme und Dokumente",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(
        self,
        *args,
        business_unit=None,
        source_stage_id=None,
        source_process_analysis_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        queryset = ProcessAnalysis.objects.none()
        if business_unit is not None:
            queryset = ProcessAnalysis.objects.filter(
                stage__value_stream__business_unit=business_unit
            )
            if source_stage_id:
                queryset = queryset.filter(stage_id=source_stage_id)
            if source_process_analysis_id:
                queryset = queryset.filter(pk=source_process_analysis_id)
            queryset = queryset.select_related("stage__value_stream").order_by(
                "stage__value_stream__name",
                "stage__sequence",
                "name",
            )
        self.fields["process_analysis"].queryset = queryset

        if source_process_analysis_id:
            self.initial["process_analysis"] = source_process_analysis_id
            self.fields["process_analysis"].disabled = True
            self.fields["process_analysis"].help_text = (
                "Der Ursprungsprozess wurde aus Discovery übernommen und bleibt für diesen "
                "Intake unverändert."
            )

    def clean(self):
        cleaned = super().clean()
        process_analysis = cleaned.get("process_analysis")
        affected_process = (cleaned.get("affected_process") or "").strip()
        if process_analysis is not None:
            cleaned["affected_process"] = process_analysis.name
        elif not affected_process:
            self.add_error(
                "affected_process",
                "Bitte wählen Sie einen Ursprungsprozess oder benennen Sie den "
                "betroffenen Prozess.",
            )
        else:
            cleaned["affected_process"] = affected_process
        return cleaned


class AffectedPeopleStepForm(IntakeStepForm):
    intended_users = forms.CharField(
        label="Wer würde die Lösung unmittelbar nutzen?",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    intended_purpose = forms.CharField(
        label="Wozu darf die Lösung eingesetzt werden?",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    privacy_review_required = forms.BooleanField(
        required=False,
        label="Personenbezogene oder sensible Daten sind betroffen",
    )
    security_review_required = forms.BooleanField(
        required=False,
        label="Externe Systeme, Cloud-Dienste oder schützenswerte Informationen sind betroffen",
    )
    legal_review_required = forms.BooleanField(
        required=False,
        label="Die Lösung beeinflusst Rechte, Verträge oder Entscheidungen über Personen",
    )


class BenefitStepForm(IntakeStepForm):
    expected_benefit = forms.CharField(
        label="Welche messbare Verbesserung wird erwartet?",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    metric_name = forms.CharField(max_length=200, label="Primäre Erfolgsmetrik")
    metric_type = forms.ChoiceField(choices=UseCase.MetricType.choices, label="Metriktyp")
    metric_direction = forms.ChoiceField(
        choices=UseCase.MetricDirection.choices,
        label="Optimierungsrichtung",
    )
    metric_unit = forms.CharField(max_length=80, label="Einheit")
    metric_baseline = LocalizedDecimalField(
        max_digits=14,
        decimal_places=4,
        required=False,
        label="Baseline-Wert",
        help_text=(
            "Kann in früher Discovery noch offen bleiben. Vor einer positiven Freigabe "
            "muss die Baseline belastbar vorliegen."
        ),
    )
    metric_target = LocalizedDecimalField(
        max_digits=14,
        decimal_places=4,
        required=False,
        label="Zielwert",
        help_text=(
            "Kann in früher Discovery noch offen bleiben. Vor einer positiven Freigabe "
            "muss der Zielwert belastbar definiert sein."
        ),
    )
    metric_measurement_method = forms.CharField(
        label="Messmethode",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Wie, wann und mit welcher Stichprobe wird die Kennzahl erhoben?",
    )

    def clean(self):
        cleaned = super().clean()
        baseline = cleaned.get("metric_baseline")
        target = cleaned.get("metric_target")
        direction = cleaned.get("metric_direction")
        metric_type = cleaned.get("metric_type")
        if metric_type == UseCase.MetricType.PERCENT:
            for field_name, value in [
                ("metric_baseline", baseline),
                ("metric_target", target),
            ]:
                if value is not None and (value < Decimal("0") or value > Decimal("100")):
                    self.add_error(field_name, "Prozentwerte müssen zwischen 0 und 100 liegen.")
        if baseline is None or target is None:
            return cleaned
        if baseline == target:
            self.add_error(
                "metric_target",
                "Der Zielwert muss sich von der Baseline unterscheiden.",
            )
        elif direction == UseCase.MetricDirection.LOWER and target > baseline:
            self.add_error(
                "metric_target",
                "Bei „Niedriger ist besser“ muss der Zielwert unter der Baseline liegen.",
            )
        elif direction == UseCase.MetricDirection.HIGHER and target < baseline:
            self.add_error(
                "metric_target",
                "Bei „Höher ist besser“ muss der Zielwert über der Baseline liegen.",
            )
        return cleaned


class DataStepForm(IntakeStepForm):
    data_sources = forms.CharField(
        label="Benötigte Daten und bekannte Datenquellen",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    solution_type = forms.ChoiceField(choices=UseCase.SolutionType.choices, label="Lösungsrahmen")
    hosting_type = forms.ChoiceField(choices=UseCase.HostingType.choices, label="Hosting-Rahmen")


WIZARD_STEPS = {
    1: {
        "title": "Problem verstehen",
        "subtitle": "Ausgangspunkt ist ein beobachtbares Problem, nicht eine Technologie.",
        "form": ProblemStepForm,
        "example": (
            "Beispiel: Mitarbeitende benötigen durchschnittlich 20 Minuten, um relevante "
            "Informationen in mehreren Richtliniendokumenten zu finden."
        ),
    },
    2: {
        "title": "Prozess und Fachdomäne einordnen",
        "subtitle": (
            "Ordnen Sie das Problem einer fachlichen Capability und dem betroffenen Prozess zu."
        ),
        "form": ProcessStepForm,
    },
    3: {
        "title": "Nutzung und Betroffene klären",
        "subtitle": "Die Antworten bestimmen, welche Governance-Prüfungen erforderlich sind.",
        "form": AffectedPeopleStepForm,
    },
    4: {
        "title": "Nutzenhypothese messbar machen",
        "subtitle": (
            "Eine Kennzahl verbindet Ausgangslage, Ziel und spätere Entscheidung; "
            "Baseline und Ziel dürfen in früher Discovery noch offen sein."
        ),
        "form": BenefitStepForm,
        "example": (
            "Beispiel: Die Bearbeitungszeit sinkt von 30 auf höchstens 15 Minuten je Vorgang, "
            "gemessen über vier Wochen."
        ),
    },
    5: {
        "title": "Daten- und Lösungsrahmen",
        "subtitle": (
            "Für die Aufnahme genügt ein belastbarer Rahmen; Architekturdetails folgen später."
        ),
        "form": DataStepForm,
    },
    6: {
        "title": "Vorprüfung",
        "subtitle": "Prüfen Sie die Angaben, bevor der Use Case zur Bewertung bereitgestellt wird.",
        "form": None,
    },
}
