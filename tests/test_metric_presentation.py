from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils.translation import override

from ki_radar.delivery.services import build_initial_delivery_data
from ki_radar.use_cases.form_fields import LocalizedDecimalField, LocalizedDecimalInput
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.intake import BenefitStepForm
from ki_radar.use_cases.metric_presentation import (
    MISSING_VALUE,
    MetricPresentation,
    build_metric_presentation,
    format_count_decimal,
)
from ki_radar.use_cases.models import UseCase


@pytest.mark.parametrize(
    ("metric_type", "value", "unit", "expected"),
    [
        (UseCase.MetricType.DURATION, Decimal("11.0000"), "Minuten", "11,0 Minuten"),
        (UseCase.MetricType.DURATION, Decimal("8.2500"), "Minuten", "8,25 Minuten"),
        (UseCase.MetricType.PERCENT, Decimal("12.3450"), "", "12,35 %"),
        (UseCase.MetricType.CURRENCY, Decimal("5000.0000"), "", "5.000,00 €"),
        (UseCase.MetricType.COUNT, Decimal("42.0000"), "Fälle", "42 Fälle"),
        (UseCase.MetricType.NUMBER, Decimal("7.1250"), "Punkte", "7,125 Punkte"),
    ],
)
def test_metric_types_are_presented_consistently(metric_type, value, unit, expected):
    result = build_metric_presentation(metric_type=metric_type, value=value, unit=unit)

    assert isinstance(result, MetricPresentation)
    assert result.display == expected
    assert result.is_missing is False
    assert result.uses_fallback is False


def test_metric_presentation_contract_for_duration():
    result = build_metric_presentation(
        metric_type=UseCase.MetricType.DURATION,
        value=Decimal("8.25"),
        unit="Minuten",
    )

    assert result == MetricPresentation(
        formatted_value="8,25",
        unit="Minuten",
        display="8,25 Minuten",
        metric_type=UseCase.MetricType.DURATION,
        is_missing=False,
        uses_fallback=False,
    )


@pytest.mark.parametrize("metric_type", [None, "", "future_metric_type"])
def test_unknown_metric_type_uses_lossless_generic_fallback(metric_type):
    result = build_metric_presentation(
        metric_type=metric_type,
        value=Decimal("8.2500"),
        unit="Minuten",
    )

    assert result.formatted_value == "8,25"
    assert result.display == "8,25 Minuten"
    assert result.uses_fallback is True


def test_missing_metric_value_does_not_append_unit():
    result = build_metric_presentation(
        metric_type=UseCase.MetricType.DURATION,
        value=None,
        unit="Minuten",
    )

    assert result.formatted_value == MISSING_VALUE
    assert result.display == MISSING_VALUE
    assert result.is_missing is True


def test_count_trailing_zero_cleanup_is_not_rounding():
    assert format_count_decimal(Decimal("5.0000")) == "5"
    assert format_count_decimal(Decimal("5.2500")) == "5,25"
    assert format_count_decimal(Decimal("5.2501")) == "5,2501"


def test_localized_decimal_widget_preserves_integer_zeroes_and_precision():
    widget = LocalizedDecimalInput()

    with override("de"):
        assert widget.format_value(Decimal("1000.0000")) == "1000"
        assert widget.format_value(Decimal("8.2500")) == "8,25"
        assert widget.format_value("acht,25") == "acht,25"


def test_benefit_form_accepts_german_decimal_separator():
    with override("de"):
        form = BenefitStepForm(
            data={
                "expected_benefit": "Bearbeitungszeit reduzieren",
                "metric_name": "Bearbeitungszeit",
                "metric_type": UseCase.MetricType.DURATION,
                "metric_direction": UseCase.MetricDirection.LOWER,
                "metric_unit": "Minuten",
                "metric_baseline": "11,0",
                "metric_target": "8,25",
                "metric_measurement_method": "Messung über 100 Vorgänge",
            }
        )

        assert isinstance(form.fields["metric_baseline"], LocalizedDecimalField)
        assert isinstance(form.fields["metric_baseline"].widget, LocalizedDecimalInput)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["metric_baseline"] == Decimal("11.0")
        assert form.cleaned_data["metric_target"] == Decimal("8.25")


@pytest.mark.django_db
def test_model_form_localized_fields_parse_comma_values():
    with override("de"):
        form = UseCaseForm()
        target_field = form.fields["metric_target"]

        assert target_field.localize is True
        assert isinstance(target_field.widget, LocalizedDecimalInput)
        assert target_field.clean("8,25") == Decimal("8.25")


@pytest.fixture
def metric_use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Metrikdarstellung prüfen",
        summary="Ein kompakter Testfall für lokalisierte Metrikwerte.",
        problem_statement="Technische Dezimaldarstellung erschwert die fachliche Prüfung.",
        business_unit=business_unit,
        affected_process="Metrikprüfung",
        target_users="Fachliche Prüfer",
        business_owner=owner,
        expected_benefit="Metrikwerte fachlich lesbar darstellen.",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("11.0000"),
        metric_target=Decimal("8.2500"),
        metric_actual=Decimal("8.9000"),
        metric_measurement_method="Messung über 100 Vorgänge",
        one_time_cost=Decimal("5000.00"),
        recurring_cost=Decimal("300.00"),
        status=UseCase.Status.PILOT,
    )


@pytest.mark.django_db
def test_detail_and_outcome_workspace_use_same_localized_values(
    client,
    owner,
    metric_use_case,
):
    client.force_login(owner)

    detail = client.get(metric_use_case.get_absolute_url())
    outcome = client.get(
        reverse("reporting:outcome_workspace"),
        {"stage": "effect", "use_case": metric_use_case.pk},
    )

    assert detail.status_code == 200
    assert outcome.status_code == 200
    for response in (detail, outcome):
        content = response.content.decode()
        assert "11,0 Minuten" in content
        assert "8,25 Minuten" in content
        assert "8,9 Minuten" in content
        assert "11.0000" not in content
        assert "8.2500" not in content
    assert "5.000,00 €" in detail.content.decode()


@pytest.mark.django_db
def test_csv_export_uses_localized_values_without_unit_duplication(
    client,
    owner,
    metric_use_case,
):
    client.force_login(owner)

    response = client.get(reverse("use_cases:export_csv"))
    content = response.content.decode("utf-8-sig")

    assert response.status_code == 200
    assert ";11,0;8,25;8,9;Minuten;" in content
    assert "11.0000" not in content
    assert "8.2500" not in content


@pytest.mark.django_db
def test_delivery_snapshot_uses_localized_metric_values(owner, business_unit):
    use_case = UseCase.objects.create(
        title="Delivery-Snapshot",
        summary="Messstand übernehmen",
        problem_statement="Messwerte werden technisch formatiert.",
        business_unit=business_unit,
        affected_process="Delivery",
        target_users="Delivery-Team",
        business_owner=owner,
        intended_users="Delivery-Team",
        intended_purpose="Messstand nachvollziehbar übergeben",
        expected_benefit="Lesbare Messwerte",
        source_systems="Quellsystem",
        data_sources="Messdaten",
        interface_description="",
        human_oversight="Fachliche Kontrolle",
        support_responsibility="IT-Service",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("11.0000"),
        metric_target=Decimal("8.2500"),
        metric_measurement_method="Messung über 100 Vorgänge",
    )
    decision = SimpleNamespace(
        conditions="",
        condition_owner=None,
        condition_due_date=None,
        rationale="Freigabe für den Test",
        assessment=SimpleNamespace(get_risk_complexity_display=lambda: "Mittel"),
        get_decision_status_display=lambda: "Freigegeben",
    )

    data = build_initial_delivery_data(use_case, decision)

    assert "Baseline 11,0 Minuten" in data["measurement_plan"]
    assert "Ziel 8,25 Minuten" in data["measurement_plan"]
    assert "11.0000" not in data["measurement_plan"]
    assert "8.2500" not in data["measurement_plan"]


def test_delivery_snapshot_is_labelled_in_ui_and_markdown():
    template = Path("templates/delivery/package_detail.html").read_text(encoding="utf-8")
    export = Path("ki_radar/delivery/exports.py").read_text(encoding="utf-8")

    label = "Übernommener Messstand bei Erstellung von Delivery v"
    assert label in template
    assert label in export
