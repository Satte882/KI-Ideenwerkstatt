from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.core.demo_architecture_data import INVOICE_STREAM_NAME, INVOICE_USE_CASE_KEY
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.primary_actions import _normalize_second_approval_action
from ki_radar.use_cases.workflow import JourneyState, JourneyStep


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-51-64-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def architecture_use_case(coordinator):
    return UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)


def _complete_process(stage, coordinator):
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Issue 51 kanonische Lösungsaktion",
        status=ProcessAnalysis.Status.TARGET_DEFINED,
        scope_start="Eingang",
        scope_end="Ergebnis",
        trigger="Auslöser",
        outcome="Nachvollziehbares Ergebnis",
        current_flow="Ist-Ablauf mit mehreren manuellen Schritten.",
        roles="Fachbereich und IT",
        systems="ERP und DMS",
        data_objects="Auftrag und Dokument",
        bottlenecks="Medienbruch und Rückfragen",
        baseline_metrics="Zehn Minuten je Vorgang",
        analyzed_by=coordinator,
    )


@pytest.mark.django_db
def test_value_stream_renders_one_canonical_primary_action(
    client,
    coordinator,
    architecture_use_case,
):
    value_stream = ValueStream.objects.create(
        name="Issue 51 Value Stream",
        business_unit=architecture_use_case.business_unit,
        owner=architecture_use_case.business_owner,
        created_by=coordinator,
        trigger="Ein Bedarf liegt vor.",
        outcome="Der Bedarf ist erfüllt.",
        scope_in="Bedarf bis Ergebnis.",
    )
    client.force_login(coordinator)

    response = client.get(
        reverse("architecture:value_stream_detail", kwargs={"pk": value_stream.pk})
    )
    content = response.content.decode()
    action = response.context["journey"].next_action

    assert response.status_code == 200
    assert action.key == "value_stream"
    assert content.count('data-testid="primary-next-action-control"') == 1
    assert f'href="{action.url}"' in content
    assert f"{action.action_label} →" in content
    assert (
        'class="btn btn-primary" href="/architecture/value-streams/'
        not in content.split('id="end-to-end-phasen"', 1)[0]
    )


@pytest.mark.django_db
def test_process_page_uses_journey_action_and_shows_full_reason(client, coordinator):
    value_stream = ValueStream.objects.get(name=INVOICE_STREAM_NAME)
    process = _complete_process(value_stream.stages.first(), coordinator)
    client.force_login(coordinator)

    response = client.get(
        reverse("architecture:process_analysis_detail", kwargs={"pk": process.pk})
    )
    content = response.content.decode()
    action = response.context["journey"].next_action

    assert response.status_code == 200
    assert action.key == "solution"
    assert content.count('data-testid="primary-next-action-control"') == 1
    assert f'href="{action.url}"' in content
    assert f"{action.action_label} →" in content
    assert action.reason in content
    assert "Noch keine Lösungsoption ist dokumentiert." in content


@pytest.mark.django_db
def test_use_case_detail_hides_duplicate_current_actions(
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
    action = response.context["journey"].next_action

    assert response.status_code == 200
    assert action.key == "assessment"
    assert content.count('data-testid="primary-next-action"') == 1
    assert content.count('data-testid="primary-next-action-control"') == 1
    assert f'href="{action.url}"' in content
    assert f'class="dropdown-item" href="{action.url}">Bewertung anlegen</a>' not in content
    assert 'id="next-action"' in content
    assert 'data-testid="journey-next-action-context"' not in content


def test_second_approval_action_points_to_actual_review():
    approval = SimpleNamespace(pk=17, is_pending_second_approval=True)
    use_case = SimpleNamespace(approval_decisions=SimpleNamespace(first=lambda: approval))
    old_step = JourneyStep(
        key="approval",
        label="Freigabe",
        state="blocked",
        url="/use-cases/current/",
        action_label="Zweitfreigabe öffnen",
        reason="Eine unabhängige Bestätigung fehlt.",
    )
    journey = JourneyState(
        path_label="Direkter Intake",
        steps=(old_step,),
        next_action=old_step,
    )

    normalized = _normalize_second_approval_action(use_case, journey)

    assert normalized.next_action.url == reverse(
        "use_cases:second_approval_review", kwargs={"decision_id": approval.pk}
    )
    assert normalized.next_action.action_label == "Zweitprüfung öffnen"
    assert normalized.next_action.action_method == "get"


def test_next_action_css_does_not_truncate_or_hide_reason():
    css = Path("static/css/context-topbar.css").read_text(encoding="utf-8")
    reason_rule = css.split(".journey-topbar-next-reason {", 1)[1].split("}", 1)[0]

    assert "white-space: normal" in reason_rule
    assert "overflow-wrap: anywhere" in reason_rule
    assert "text-overflow: ellipsis" not in css
    assert ".journey-topbar-next-reason {\n    display: none;" not in css
