import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ValueStreamForm
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.delivery.readiness import missing_ready_fields, render_delivery_markdown
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_use_case_journey


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def seeded_demo(db):
    call_command("seed_demo_data", demo_user_password="Focus-Prioritization-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.mark.django_db
def test_selected_focus_requires_complete_screening():
    business_unit = BusinessUnit.objects.create(name="Testbereich")
    form = ValueStreamForm(
        data={
            "name": "Test Value Stream",
            "business_unit": business_unit.pk,
            "status": ValueStream.Status.ACTIVE,
            "description": "End-to-End-Test",
            "trigger": "Kundenbedarf",
            "outcome": "Erfüllter Bedarf",
            "scope_in": "Vom Bedarf bis zum Ergebnis",
            "business_domain": BusinessDomain.PROCUREMENT,
            "focus_status": ValueStreamFocus.Status.SELECTED,
        }
    )

    assert form.is_valid() is False
    assert "capability" in form.errors
    assert "strategic_impact" in form.errors
    assert "focus_rationale" in form.errors


@pytest.mark.django_db
def test_value_stream_form_persists_selected_focus(seeded_demo):
    business_unit = BusinessUnit.objects.create(name="Fokusbereich")
    form = ValueStreamForm(
        data={
            "name": "Beschaffung testen",
            "business_unit": business_unit.pk,
            "owner": seeded_demo.pk,
            "status": ValueStream.Status.ACTIVE,
            "description": "Fokusentscheidung testen",
            "trigger": "Bedarf entsteht",
            "outcome": "Bedarf gedeckt",
            "scope_in": "Bedarf bis Bestellung",
            "strategic_objective": "Durchlaufzeit senken",
            "stakeholders": "Einkauf",
            "constraints": "ERP bleibt führend",
            "business_domain": BusinessDomain.PROCUREMENT,
            "capability": "Source-to-Pay",
            "strategic_impact": "high",
            "economic_potential": "high",
            "pain_intensity": "high",
            "data_accessibility": "medium",
            "change_effort": "medium",
            "focus_status": ValueStreamFocus.Status.SELECTED,
            "focus_rationale": "Hoher Hebel und belastbare Baseline.",
        }
    )

    assert form.is_valid(), form.errors
    value_stream = form.save()
    value_stream.refresh_from_db()

    assert value_stream.focus.is_selected is True
    assert value_stream.focus.business_domain == BusinessDomain.PROCUREMENT
    assert value_stream.focus.capability == "Source-to-Pay"


@pytest.mark.django_db
def test_unselected_value_stream_cannot_start_deep_dive(client, seeded_demo):
    business_unit = BusinessUnit.objects.create(name="Nicht priorisiert")
    value_stream = ValueStream.objects.create(
        name="Ungeprüfter Value Stream",
        business_unit=business_unit,
        owner=seeded_demo,
        status=ValueStream.Status.ACTIVE,
        trigger="Auslöser",
        outcome="Ergebnis",
        scope_in="Scope",
        created_by=seeded_demo,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Prüfschritt",
        description="Noch nicht priorisiert",
    )
    client.force_login(seeded_demo)

    response = client.get(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": stage.pk})
    )

    assert response.status_code == 302
    assert response.url == value_stream.get_absolute_url()
    assert stage.process_analyses.count() == 0


@pytest.mark.django_db
def test_demo_inherits_focus_classification_and_delivery_artifacts(seeded_demo):
    use_case = UseCase.objects.select_related(
        "classification",
        "architecture_origin__stage__value_stream__focus",
    ).get(demo_key=INVOICE_USE_CASE_KEY)
    package = use_case.delivery_packages.select_related("architecture_artifacts").get(version=1)
    journey = build_use_case_journey(use_case, seeded_demo)
    step_keys = [step.key for step in journey.steps]

    assert step_keys[:2] == ["value_stream", "focus"]
    assert use_case.architecture_origin.stage.value_stream.focus.is_selected is True
    assert use_case.classification.business_domain == BusinessDomain.FINANCE
    assert use_case.classification.capability
    assert package.architecture_artifacts.system_landscape
    assert package.architecture_artifacts.data_flows
    assert package.architecture_artifacts.integration_contracts
    assert "Ist-/Ziel-Systemlandschaft" in render_delivery_markdown(package)
    assert "Daten- und Informationsflüsse" in render_delivery_markdown(package)


@pytest.mark.django_db
def test_delivery_readiness_requires_explicit_architecture_artifacts(seeded_demo):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    package = use_case.delivery_packages.select_related("architecture_artifacts").get(version=1)
    artifacts = package.architecture_artifacts
    artifacts.system_landscape = ""
    artifacts.save(update_fields=["system_landscape", "updated_at"])

    assert "Ist-/Ziel-Systemlandschaft" in missing_ready_fields(package)
