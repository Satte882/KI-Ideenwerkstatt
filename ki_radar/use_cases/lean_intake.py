# ruff: noqa: I001
from decimal import Decimal

from .intake import (
    AffectedPeopleStepForm as LegacyAffectedPeopleStepForm,
    BenefitStepForm as LegacyBenefitStepForm,
    DataStepForm as LegacyDataStepForm,
    ProblemStepForm as LegacyProblemStepForm,
    ProcessStepForm as LegacyProcessStepForm,
    WIZARD_STEPS as LEGACY_WIZARD_STEPS,
)
from .models import UseCase


class _LeanOptionalMixin:
    optional_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.optional_fields:
            self.fields[field_name].required = False


class ProblemStepForm(_LeanOptionalMixin, LegacyProblemStepForm):
    optional_fields = ("problem_statement",)

    def clean_problem_statement(self):
        return (self.cleaned_data.get("problem_statement") or "").strip()


class ProcessStepForm(_LeanOptionalMixin, LegacyProcessStepForm):
    optional_fields = (
        "business_domain",
        "business_capability",
        "affected_process",
        "summary",
        "target_users",
        "source_systems",
    )

    def clean(self):
        cleaned = self.cleaned_data
        process_analysis = cleaned.get("process_analysis")
        affected_process = (cleaned.get("affected_process") or "").strip()
        if process_analysis is not None:
            cleaned["affected_process"] = process_analysis.name
        else:
            cleaned["affected_process"] = affected_process
        return cleaned


class AffectedPeopleStepForm(_LeanOptionalMixin, LegacyAffectedPeopleStepForm):
    optional_fields = ("intended_users", "intended_purpose")


class BenefitStepForm(_LeanOptionalMixin, LegacyBenefitStepForm):
    optional_fields = (
        "expected_benefit",
        "metric_name",
        "metric_type",
        "metric_direction",
        "metric_unit",
        "metric_baseline",
        "metric_target",
        "metric_measurement_method",
    )

    def clean(self):
        cleaned = self.cleaned_data
        baseline = cleaned.get("metric_baseline")
        target = cleaned.get("metric_target")
        direction = cleaned.get("metric_direction")
        metric_type = cleaned.get("metric_type")
        if metric_type == UseCase.MetricType.PERCENT:
            for field_name, value in (
                ("metric_baseline", baseline),
                ("metric_target", target),
            ):
                if value is not None and not Decimal("0") <= value <= Decimal("100"):
                    self.add_error(field_name, "Prozentwerte müssen zwischen 0 und 100 liegen.")
        if baseline is None or target is None or baseline == target:
            return cleaned
        if direction == UseCase.MetricDirection.LOWER and target > baseline:
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


class DataStepForm(_LeanOptionalMixin, LegacyDataStepForm):
    optional_fields = ("data_sources", "solution_type", "hosting_type")


LEAN_FORMS = {
    1: ProblemStepForm,
    2: ProcessStepForm,
    3: AffectedPeopleStepForm,
    4: BenefitStepForm,
    5: DataStepForm,
}

WIZARD_STEPS = {
    number: {**config, "form": LEAN_FORMS.get(number, config["form"])}
    for number, config in LEGACY_WIZARD_STEPS.items()
}
