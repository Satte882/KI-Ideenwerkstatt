from pathlib import Path

import pytest
from django.urls import reverse

from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.workflow import JourneyState

ROOT = Path(__file__).resolve().parents[1]


def _use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Pilot für Rechnungsprüfung",
        problem_statement="Die Prüfung ist langsam und erzeugt Rückfragen.",
        business_unit=business_unit,
        affected_process="Eingangsrechnung prüfen",
        business_owner=owner,
        expected_benefit="Prüfzeit messbar senken.",
        status=UseCase.Status.PILOT,
        metric_name="Prüfzeit je Rechnung",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=11,
        metric_target=5,
    )


def test_outcome_workspace_assets_document_scope_and_final_navigation():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "reporting" / "outcome_workspace.html").read_text(
        encoding="utf-8"
    )
    documentation = (ROOT / "docs" / "OUTCOME_WORKSPACE.md").read_text(encoding="utf-8")

    assert "sidebar-workspace-separator" in base
    assert "Wirkung &amp; Betrieb" in base
    assert base.count("reporting:outcome_workspace") == 2
    assert "Pilot → Wirkung → Scale Readiness → Betrieb" in base
    assert "css/outcome-workspace.css" in base
    assert "Entscheidungsrelevanter Review-Snapshot" in template
    assert "B · Gesamtleiste" not in template
    assert "outcome-stage-nav" not in template
    assert "für die Abnahme" not in template
    assert "Arbeitsraum 2" not in template
    assert "keine Live-Synchronisation" in documentation
    assert "keine zweite Journey-Engine" in documentation


@pytest.mark.django_db
def test_outcome_journey_extends_existing_journey_state(owner, business_unit):
    use_case = _use_case(owner, business_unit)

    journey = build_outcome_workspace_journey(use_case, owner)
    keys = [step.key for step in journey.steps]

    assert isinstance(journey, JourneyState)
    assert keys[:2] == ["value_stream", "focus"]
    assert "delivery" in keys
    assert keys[-6:] == [
        "handover",
        "pilot",
        "measurement",
        "outcome_decision",
        "operation",
        "closure",
    ]
    assert journey.next_action is not None
    assert journey.next_action.key in {
        "use_case",
        "assessment",
        "delivery",
        "handover",
        "pilot",
        "measurement",
    }


@pytest.mark.django_db
def test_outcome_workspace_renders_only_outcome_lifecycle_segment(
    client,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    client.force_login(owner)

    for layout in ("continuous", "split"):
        response = client.get(
            reverse("reporting:outcome_workspace"),
            {
                "stage": "effect",
                "layout": layout,
                "use_case": use_case.pk,
            },
        )
        content = response.content.decode()

        assert response.status_code == 200
        assert response.context["active_stage"] == "effect"
        assert response.context["journey"].path_label.endswith("Wirkung & Betrieb")
        assert "cr-lifecycle-rail--header" in content
        assert ">Teilprozess<" in content
        assert 'class="cr-lifecycle-step__label">Discovery</span>' not in content
        assert 'class="cr-lifecycle-step__label">Fokus &amp; Priorisierung</span>' not in content
        assert "Ergebnisentscheidung" in content
        assert content.index("cr-lifecycle-rail--header") < content.index('class="page-header')
        assert "Entscheidungsrelevanter Review-Snapshot" in content
        assert "Externes Delivery-System" in content
        assert "B · Gesamtleiste" not in content


@pytest.mark.django_db
def test_outcome_workspace_defaults_invalid_parameters(client, owner, business_unit):
    _use_case(owner, business_unit)
    client.force_login(owner)

    response = client.get(
        reverse("reporting:outcome_workspace"),
        {"stage": "unknown", "layout": "unknown", "use_case": "invalid"},
    )

    assert response.status_code == 200
    assert response.context["active_stage"] == "pilot"
    assert response.context["selected_use_case"] is not None
