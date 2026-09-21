from __future__ import annotations

import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


@pytest.fixture
def solution_option(db, business_unit, owner):
    value_stream = ValueStream.objects.create(
        name="Advisor UI",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bedarf ist bearbeitet",
        scope_in="Testumfang",
        created_by=owner,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.OTHER,
        capability="Dokumentenprüfung",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Advisor-UI-Test ausgewählt.",
        updated_by=owner,
    )

    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Testphase",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Testprozess",
        scope_start="Start",
        scope_end="Ende",
        trigger="Bedarf",
        outcome="Ergebnis",
        current_flow="Aktueller Ablauf",
        roles="Fachrolle",
        systems="Quellsystem",
        data_objects="Dokumente",
        bottlenecks="Manuelle Prüfung",
        baseline_metrics="10 Minuten",
        analyzed_by=owner,
    )
    return SolutionOption.objects.create(
        process_analysis=process,
        name="Semantische Assistenz",
        option_type=SolutionOption.OptionType.GENERATIVE_AI,
        description="Unterstützt die semantische Prüfung.",
        expected_value="Reduziert manuellen Aufwand.",
        created_by=owner,
    )


def _assessment_url(option):
    return reverse(
        "architecture:solution_architecture_assessment_update",
        kwargs={"pk": option.pk},
    )


def _edit_url(option):
    return reverse("architecture:solution_option_update", kwargs={"pk": option.pk})


def _answers(*, simpler="no", semantic="yes", multiple="no", dynamic="no"):
    return {
        "simpler_solution_sufficient": simpler,
        "semantic_reasoning_required": semantic,
        "multiple_known_ai_steps_required": multiple,
        "dynamic_orchestration_required": dynamic,
    }


@pytest.mark.django_db
def test_existing_solution_option_page_shows_exactly_four_architecture_questions(
    client,
    owner,
    solution_option,
):
    client.force_login(owner)

    response = client.get(_edit_url(solution_option))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Architektur-Einschätzung" in content
    assert content.count("Einfachere Lösung ausreichend?") == 1
    assert content.count("Semantisches Reasoning erforderlich?") == 1
    assert content.count("Mehrere bekannte KI-Schritte erforderlich?") == 1
    assert content.count("Dynamische Orchestrierung erforderlich?") == 1
    assert "Warum dieses Muster?" not in content


@pytest.mark.django_db
def test_controlled_llm_is_saved_and_explained_inline(client, owner, solution_option):
    client.force_login(owner)

    response = client.post(_assessment_url(solution_option), _answers())

    assert response.status_code == 302
    assert response.url.endswith("#architecture-assessment")

    response = client.get(_edit_url(solution_option))
    content = response.content.decode()
    assert "Controlled LLM" in content
    assert "Warum dieses Muster?" in content
    assert "Semantische Verarbeitung ist erforderlich" in content
    assert "Warum kein Agent?" in content
    assert "Dynamische Orchestrierung ist nicht erforderlich" in content


@pytest.mark.django_db
def test_open_assessment_shows_open_point_without_agent_explanation(
    client,
    owner,
    solution_option,
):
    client.force_login(owner)

    client.post(
        _assessment_url(solution_option),
        _answers(simpler="yes", semantic="yes"),
    )

    response = client.get(_edit_url(solution_option))
    content = response.content.decode()
    assert "Assessment open" in content
    assert "Offene Punkte" in content
    assert "fachlich widersprüchliche Anforderungen" in content
    assert "Warum kein Agent?" not in content


@pytest.mark.django_db
def test_bounded_agent_shows_mode_without_why_no_agent(client, owner, solution_option):
    client.force_login(owner)

    client.post(
        _assessment_url(solution_option),
        _answers(dynamic="yes"),
    )

    response = client.get(_edit_url(solution_option))
    content = response.content.decode()
    assert "Bounded Agent" in content
    assert "Zwischenzustand dynamisch gewählt" in content
    assert "Warum kein Agent?" not in content


@pytest.mark.django_db
def test_reader_cannot_submit_architecture_assessment(client, reader, solution_option):
    client.force_login(reader)

    response = client.post(_assessment_url(solution_option), _answers())

    assert response.status_code == 403
