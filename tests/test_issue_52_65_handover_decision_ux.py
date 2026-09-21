from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.use_cases.decision_forms import (
    CONDITIONAL_APPROVAL_FIELDS,
    ApprovalDecisionForm,
)
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-52-65-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def architecture_use_case(coordinator):
    return UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)


def test_intake_names_real_effect_role_and_queue():
    template = Path("templates/use_cases/intake_wizard.html").read_text(encoding="utf-8")
    intake_config = Path("ki_radar/use_cases/intake.py").read_text(encoding="utf-8")

    assert "Use Case anlegen und zur Bewertung bereitstellen" in template
    assert "Use Case anlegen und zur Bewertung übergeben" not in template
    assert 'data-testid="intake-handover-preview"' in template
    assert "Nächste Bearbeitung" in template
    assert "KI-Koordination" in template
    assert "Arbeitsvorrat → Meine Aufgaben" in template
    assert "zur Bewertung bereitgestellt wird" in intake_config


@pytest.mark.django_db
def test_use_case_detail_names_assessment_handover_queue(
    client,
    coordinator,
    architecture_use_case,
):
    architecture_use_case.delivery_packages.all().delete()
    architecture_use_case.approval_decisions.all().delete()
    architecture_use_case.governance_assessments.all().delete()
    architecture_use_case.decision_assessments.all().delete()
    architecture_use_case.status = UseCase.Status.REVIEW
    architecture_use_case.decision_status = UseCase.DecisionStatus.READY
    architecture_use_case.save(update_fields=["status", "decision_status"])
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:detail", kwargs={"pk": architecture_use_case.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["journey"].next_action.key == "assessment"
    assert 'data-testid="assessment-handover-status"' in content
    assert "Zur Bewertung bereitgestellt" in content
    assert "Nächste Bearbeitung" in content
    assert "KI-Koordination" in content
    assert "Arbeitsvorrat → Meine Aufgaben" in content
    assert f'href="{reverse("reporting:dashboard")}"' in content


@pytest.mark.django_db
def test_conditional_decision_fields_are_immediately_required_and_explained():
    form = ApprovalDecisionForm(
        initial={
            "decision_status": UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        }
    )

    for field_name in CONDITIONAL_APPROVAL_FIELDS:
        field = form.fields[field_name]
        assert field.required is True
        assert field.help_text
        assert field.widget.attrs["data-conditional-required"] == "true"
        assert field.widget.attrs["aria-required"] == "true"


@pytest.mark.django_db
def test_non_conditional_decision_keeps_conditional_fields_optional():
    form = ApprovalDecisionForm(
        initial={
            "decision_status": UseCase.DecisionStatus.APPROVED,
        }
    )

    for field_name in CONDITIONAL_APPROVAL_FIELDS:
        field = form.fields[field_name]
        assert field.required is False
        assert field.widget.attrs["aria-required"] == "false"


@pytest.mark.django_db
def test_conditional_decision_still_enforces_all_fields_server_side():
    form = ApprovalDecisionForm(
        data={
            "decision_status": UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            "rationale": "Freigabe ist nur unter nachvollziehbaren Auflagen vertretbar.",
            "governance_confirmed": "on",
        }
    )

    assert form.is_valid() is False
    for field_name in CONDITIONAL_APPROVAL_FIELDS:
        assert field_name in form.errors


def test_decision_template_separates_recommendation_and_binding_action():
    template = Path("templates/use_cases/decision_form.html").read_text(encoding="utf-8")

    assert "Unverbindliche Bewertungsempfehlung" in template
    assert "Vorschlag aus der Bewertung; noch keine verbindliche Entscheidung." in template
    assert 'id="binding-decision"' in template
    assert "Verbindliche Entscheidung speichern" in template
    assert "Entscheidung prüfen, speichern und zurückkehren" not in template
    for field_name in CONDITIONAL_APPROVAL_FIELDS:
        assert f'data-conditional-field="{field_name}"' in template
        assert f'data-required-marker-for="{field_name}"' in template
    assert 'statusField.addEventListener("change", syncConditionalRequirements)' in template
    assert "input.required = required" in template
