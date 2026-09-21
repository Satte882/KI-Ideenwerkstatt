from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ki_radar.accounts.models import BusinessUnit
from ki_radar.reporting.portfolio import (
    _landscape_context,
    annotated_portfolio_queryset,
    build_portfolio_context,
)
from ki_radar.use_cases.models import DecisionAssessment, UseCase


def make_use_case(owner, business_unit, **overrides):
    data = {
        "title": "Richtlinien schneller finden",
        "summary": "Informationen liegen in mehreren Dokumenten.",
        "problem_statement": "Die Suche nach freigegebenen Richtlinien dauert zu lange.",
        "business_unit": business_unit,
        "affected_process": "Interne Informationssuche",
        "submitter": owner,
        "business_owner": owner,
        "expected_benefit": "Suchzeit reduzieren",
        "metric_name": "Suchzeit",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_baseline": Decimal("20"),
        "metric_target": Decimal("8"),
        "metric_measurement_method": "Messung über zehn Suchvorgänge",
        "data_sources": "Freigegebene Richtliniendokumente",
        "status": UseCase.Status.REVIEW,
        "decision_status": UseCase.DecisionStatus.READY,
        "solution_type": UseCase.SolutionType.ASSISTANT,
    }
    data.update(overrides)
    return UseCase.objects.create(**data)


def add_assessment(use_case, coordinator, *, version=1, business_value, feasibility):
    return DecisionAssessment.objects.create(
        use_case=use_case,
        version=version,
        assessed_by=coordinator,
        business_value=business_value,
        strategic_fit=UseCase.Level.MEDIUM,
        technical_feasibility=feasibility,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_url="https://example.com/portfolio-evidence",
        rationale="Repräsentative Prozessmessung und technische Prüfung.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )


@pytest.mark.django_db
def test_matrix_uses_latest_categorical_assessment(owner, coordinator, business_unit):
    use_case = make_use_case(owner, business_unit)
    add_assessment(
        use_case,
        coordinator,
        version=1,
        business_value=UseCase.Level.LOW,
        feasibility=UseCase.Level.LOW,
    )
    add_assessment(
        use_case,
        coordinator,
        version=2,
        business_value=UseCase.Level.HIGH,
        feasibility=UseCase.Level.MEDIUM,
    )

    context = build_portfolio_context({})

    assert context["classified_total"] == 1
    item = context["classified_items"][0]
    assert item.portfolio_business_value == UseCase.Level.HIGH
    assert item.portfolio_technical_feasibility == UseCase.Level.MEDIUM
    assert item.portfolio_confidence == UseCase.Level.HIGH
    high_row = next(row for row in context["matrix_rows"] if row["business_value"] == "high")
    medium_cell = next(
        cell for cell in high_row["cells"] if cell["technical_feasibility"] == "medium"
    )
    assert medium_cell["items"] == [item]


@pytest.mark.django_db
def test_not_pursued_is_hidden_by_default_and_can_be_included(
    owner,
    coordinator,
    business_unit,
):
    use_case = make_use_case(
        owner,
        business_unit,
        decision_status=UseCase.DecisionStatus.NOT_PURSUED,
    )
    add_assessment(
        use_case,
        coordinator,
        business_value=UseCase.Level.HIGH,
        feasibility=UseCase.Level.HIGH,
    )

    hidden = build_portfolio_context({})
    included = build_portfolio_context({"include_not_pursued": "1"})
    explicitly_filtered = build_portfolio_context(
        {"decision_status": UseCase.DecisionStatus.NOT_PURSUED}
    )

    assert hidden["visible_total"] == 0
    assert hidden["not_pursued_total"] == 1
    assert included["visible_total"] == 1
    assert included["classified_items"][0].portfolio_is_not_pursued is True
    assert explicitly_filtered["visible_total"] == 1


@pytest.mark.django_db
def test_use_case_without_assessment_is_listed_as_unclassified(owner, business_unit):
    use_case = make_use_case(owner, business_unit)

    context = build_portfolio_context({})

    assert context["classified_total"] == 0
    assert context["unclassified_total"] == 1
    assert context["unclassified_items"][0]["item"] == use_case
    assert context["unclassified_items"][0]["reason"] == "Keine strukturierte Bewertung"


@pytest.mark.django_db
def test_landscape_grouping_and_business_unit_filter(owner, coordinator, business_unit):
    second_unit = BusinessUnit.objects.create(name="Organisationseinheit B")
    first = make_use_case(owner, business_unit, solution_type=UseCase.SolutionType.ASSISTANT)
    second = make_use_case(
        owner,
        second_unit,
        title="Rechnungen klassifizieren",
        solution_type=UseCase.SolutionType.AUTOMATION,
        decision_status=UseCase.DecisionStatus.APPROVED,
    )
    add_assessment(
        first,
        coordinator,
        business_value=UseCase.Level.HIGH,
        feasibility=UseCase.Level.MEDIUM,
    )
    add_assessment(
        second,
        coordinator,
        business_value=UseCase.Level.MEDIUM,
        feasibility=UseCase.Level.HIGH,
    )

    grouped = build_portfolio_context({"group": "solution_type"})
    filtered = build_portfolio_context({"business_unit": str(second_unit.pk)})

    totals = {group["key"]: group["total"] for group in grouped["landscape_groups"]}
    assert totals[UseCase.SolutionType.ASSISTANT] == 1
    assert totals[UseCase.SolutionType.AUTOMATION] == 1
    assert filtered["visible_total"] == 1
    assert filtered["classified_items"][0] == second


@pytest.mark.django_db
@pytest.mark.parametrize("business_unit_value", ["invalid", "0", "-1", "1.5", "1e3", "   "])
def test_invalid_business_unit_filter_is_ignored(business_unit_value, owner, business_unit):
    make_use_case(owner, business_unit)

    context = build_portfolio_context({"business_unit": business_unit_value})

    assert context["selected"]["business_unit"] == ""
    assert context["visible_total"] == 1


@pytest.mark.django_db
def test_business_unit_filter_accepts_existing_and_missing_positive_ids(owner, business_unit):
    second_unit = BusinessUnit.objects.create(name="Organisationseinheit B")
    first = make_use_case(owner, business_unit)
    second = make_use_case(owner, second_unit, title="Rechnungen klassifizieren")

    filtered = build_portfolio_context({"business_unit": str(second_unit.pk)})
    missing = build_portfolio_context({"business_unit": "999999999"})

    assert filtered["selected"]["business_unit"] == str(second_unit.pk)
    assert filtered["visible_total"] == 1
    assert filtered["unclassified_items"][0]["item"] == second
    assert first not in [entry["item"] for entry in filtered["unclassified_items"]]
    assert missing["selected"]["business_unit"] == "999999999"
    assert missing["visible_total"] == 0


@pytest.mark.django_db
def test_portfolio_view_ignores_invalid_filters_and_falls_back_to_default_group(
    client,
    owner,
    business_unit,
):
    make_use_case(owner, business_unit)
    client.force_login(owner)

    response = client.get(
        reverse("reporting:portfolio"),
        {
            "business_unit": "invalid",
            "lifecycle": "invalid",
            "decision_status": "invalid",
            "solution_type": "invalid",
            "confidence": "invalid",
            "group": "invalid",
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Portfolio-Landkarte nach Organisationseinheit" in content
    assert "1 Use Cases" in content


@pytest.mark.django_db
def test_portfolio_landscape_is_closed_initially_and_open_after_group_change(
    client,
    owner,
    business_unit,
):
    make_use_case(owner, business_unit)
    client.force_login(owner)
    portfolio_url = reverse("reporting:portfolio")

    initial = client.get(portfolio_url).content.decode()
    grouped = client.get(portfolio_url, {"group": "solution_type"}).content.decode()

    disclosure = '<details class="portfolio-secondary-view portfolio-secondary-analysis"'
    assert f"{disclosure}>" in initial
    assert f"{disclosure} open>" in grouped


@pytest.mark.django_db
def test_matrix_and_landscape_queries_are_bounded(owner, coordinator, business_unit):
    for index in range(5):
        use_case = make_use_case(owner, business_unit, title=f"Use Case {index}")
        add_assessment(
            use_case,
            coordinator,
            business_value=UseCase.Level.MEDIUM,
            feasibility=UseCase.Level.HIGH,
        )

    with CaptureQueriesContext(connection) as matrix_queries:
        items = list(annotated_portfolio_queryset())
    with CaptureQueriesContext(connection) as landscape_queries:
        groups = _landscape_context(annotated_portfolio_queryset(), "business_unit")

    assert len(items) == 5
    assert len(groups) == 1
    assert len(matrix_queries) == 1
    assert len(landscape_queries) == 1


@pytest.mark.django_db
def test_portfolio_view_renders_navigation_matrix_and_unclassified_area(
    client,
    owner,
    business_unit,
):
    make_use_case(owner, business_unit)
    client.force_login(owner)
    portfolio_url = reverse("reporting:portfolio")

    response = client.get(portfolio_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Entscheidungs-Matrix" in content
    assert "Portfolio-Landkarte" in content
    assert "Nicht einordenbar" in content
    assert "1 Use Cases" in content
    assert f'href="{portfolio_url}"' in content
    assert "sidebar-link active" in content
