from decimal import Decimal

import pytest
from django.urls import reverse

from ki_radar.use_cases.blockers import build_blocker_details
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.services import current_decision_check


def make_use_case(owner, business_unit, **overrides):
    data = {
        "title": "Richtlinien schneller finden",
        "summary": "Informationen liegen in mehreren Dokumenten.",
        "problem_statement": (
            "Mitarbeitende benötigen lange, um freigegebene Richtlinien zu finden."
        ),
        "business_unit": business_unit,
        "affected_process": "Interne Informationssuche",
        "target_users": "Mitarbeitende",
        "submitter": owner,
        "business_owner": owner,
        "expected_benefit": "Suchzeit reduzieren",
        "metric_name": "Suchzeit",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("20"),
        "metric_target": Decimal("8"),
        "metric_measurement_method": "",
        "data_sources": "Freigegebene Richtliniendokumente",
        "status": UseCase.Status.REVIEW,
    }
    data.update(overrides)
    return UseCase.objects.create(**data)


@pytest.mark.django_db
def test_blocker_details_are_derived_from_canonical_strings(owner, business_unit):
    use_case = make_use_case(owner, business_unit)
    check = current_decision_check(use_case)

    details = build_blocker_details(use_case, check.blockers)

    assert [detail.label for detail in details] == check.blockers
    assert "Readiness offen: Messmethode" in check.warnings
    measurement = build_blocker_details(use_case, ["Messmethode"])[0]
    assert measurement.category == "data"
    assert measurement.field_name == "metric_measurement_method"
    assert "highlight=metric_measurement_method" in measurement.target_href
    assert measurement.target_href.endswith("#field-metric_measurement_method")
    approval = next(detail for detail in details if detail.label == "Positive Freigabeentscheidung")
    assert approval.category == "process"


@pytest.mark.django_db
def test_unknown_blocker_receives_safe_fallback(owner, business_unit):
    use_case = make_use_case(owner, business_unit)

    details = build_blocker_details(use_case, ["Neue unbekannte Voraussetzung"])

    assert len(details) == 1
    assert details[0].label == "Neue unbekannte Voraussetzung"
    assert details[0].target_url == use_case.get_absolute_url()


@pytest.mark.django_db
def test_edit_view_highlights_only_known_form_field(client, owner, business_unit):
    use_case = make_use_case(owner, business_unit)
    client.force_login(owner)

    response = client.get(
        reverse("use_cases:edit", kwargs={"pk": use_case.pk}),
        {"highlight": "metric_measurement_method"},
    )

    assert response.status_code == 200
    assert response.context["highlight_field"] == "metric_measurement_method"
    content = response.content.decode()
    assert 'id="field-metric_measurement_method"' in content
    assert "Messmethode ist für die nächste Entscheidung erforderlich" in content

    unknown = client.get(
        reverse("use_cases:edit", kwargs={"pk": use_case.pk}),
        {"highlight": "invented_css_class"},
    )
    assert unknown.context["highlight_field"] == ""
    assert "invented_css_class" not in unknown.content.decode()


@pytest.mark.django_db
def test_wizard_stepper_marks_invalid_current_step(client, owner, business_unit):
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:create"),
        {
            "title": "Chatbot",
            "business_unit": business_unit.pk,
            "problem_statement": "Wir brauchen einen Chatbot.",
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "wizard-step-error" in content
    assert "enthält Fehler" in content
    assert "Bitte prüfen Sie die markierten Angaben" in content


@pytest.mark.django_db
def test_dashboard_and_detail_show_actionable_blocker_summary(
    client,
    owner,
    business_unit,
):
    use_case = make_use_case(owner, business_unit)
    client.force_login(owner)

    dashboard = client.get(reverse("reporting:dashboard"))
    assert dashboard.status_code == 200
    dashboard_content = dashboard.content.decode()
    assert "offen" in dashboard_content
    assert "Ersten Punkt bearbeiten" in dashboard_content

    detail = client.get(reverse("use_cases:detail", kwargs={"pk": use_case.pk}))
    assert detail.status_code == 200
    detail_content = detail.content.decode()
    assert "Bewertungsbereit" in detail_content
    assert "Bewertung anlegen" in detail_content
    assert "Zum ersten offenen Punkt" not in detail_content
