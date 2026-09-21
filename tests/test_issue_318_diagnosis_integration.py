import pytest
from django.urls import reverse

from ki_radar.accelerator.solution_generation_sources import (
    VALIDATION_MISSING,
    VALIDATION_STALE,
    build_solution_generation_source_context,
)
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_process(owner, business_unit, *, with_diagnosis=False, validated=False):
    stream = ValueStream.objects.create(
        name="Diagnose-Integration",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Angebote liegen vor",
        outcome="Lieferant ausgewählt",
        scope_in="Angebotsvergleich",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Angebotsvergleich",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.HIGH,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Deep Dive ausgewählt.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        pain_points="Manuelle Übertragung",
        baseline_metrics="Fünf Tage",
    )
    diagnosis = {}
    if with_diagnosis:
        diagnosis = {
            "diagnostic_observations": "Der Vergleich benötigt fünf Tage.",
            "cause_hypotheses": "Uneinheitliche Formate erhöhen den Aufwand.",
            "confirmed_causes": "Angebotsdaten liegen nicht strukturiert vor.",
            "constraints": "Freigabe bleibt beim Einkauf.",
        }
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        status=ProcessAnalysis.Status.VALIDATED if validated else ProcessAnalysis.Status.DRAFT,
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell übertragen und verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterien",
        business_rules="Vier-Augen-Prinzip",
        handoffs="Einkauf an Fachbereich",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        exceptions="Unvollständige Angebote",
        baseline_metrics="Fünf Tage",
        target_state_principles="Nachvollziehbare Entscheidung",
        analyzed_by=owner,
        **diagnosis,
    )


def make_complete_option(process, owner, *, name, option_type):
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=option_type,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        description=f"Beschreibung {name}",
        expected_value=f"Nutzen {name}",
        bottleneck_coverage="Adressiert die bestätigte Ursache.",
        feasibility=SolutionOption.Effort.HIGH,
        data_requirements="Angebote und Kriterien",
        application_impact="Ergänzung der Fachanwendung",
        integration_effort=SolutionOption.Effort.MEDIUM,
        integration_impact="ERP-Export",
        technology_constraints="Nachvollziehbare Verarbeitung",
        risks="Fehlerhafte Eingaben",
        architecture_fit="Passt zur bestehenden Architektur",
        time_to_value=TimeToValue.UNKNOWN,
        created_by=owner,
    )


@pytest.mark.django_db
def test_generation_readiness_does_not_require_diagnosis_or_formal_validation(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)

    context = build_solution_generation_source_context(process)

    assert context.is_ready is True
    assert context.validation_state == VALIDATION_MISSING
    assert process.diagnostic_observations == ""
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_generation_sources_include_structured_diagnosis_when_available(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit, with_diagnosis=True)

    context = build_solution_generation_source_context(process)
    source_ids = {fact.source_id for fact in context.facts}

    assert "process.diagnostic_observations" in source_ids
    assert "process.cause_hypotheses" in source_ids
    assert "process.confirmed_causes" in source_ids
    assert "process.constraints" in source_ids
    assert context.is_ready is True


@pytest.mark.django_db
def test_diagnosis_change_marks_existing_validation_stale(client, owner, business_unit):
    process = make_process(
        owner,
        business_unit,
        with_diagnosis=True,
        validated=True,
    )
    ProcessValidation.objects.create(
        process_analysis=process,
        process_version=process.version,
        validated_by=owner,
        validator_role="Business Owner",
        note="Version 1 geprüft.",
    )
    client.force_login(owner)

    response = client.post(
        reverse("architecture:process_analysis_update", kwargs={"pk": process.pk}),
        {
            "name": process.name,
            "status": process.status,
            "scope_start": process.scope_start,
            "scope_end": process.scope_end,
            "trigger": process.trigger,
            "outcome": process.outcome,
            "current_flow": process.current_flow,
            "roles": process.roles,
            "systems": process.systems,
            "data_objects": process.data_objects,
            "business_rules": process.business_rules,
            "handoffs": process.handoffs,
            "bottlenecks": process.bottlenecks,
            "diagnostic_observations": process.diagnostic_observations,
            "cause_hypotheses": "Neue Hypothese nach zusätzlicher Evidenz.",
            "confirmed_causes": process.confirmed_causes,
            "constraints": process.constraints,
            "exceptions": process.exceptions,
            "baseline_metrics": process.baseline_metrics,
            "target_state_principles": process.target_state_principles,
        },
    )

    process.refresh_from_db()
    context = build_solution_generation_source_context(process)

    assert response.status_code == 302
    assert process.version == 2
    assert process.status == ProcessAnalysis.Status.REVIEW_REQUIRED
    assert process.validations.filter(process_version=1).exists()
    assert not process.validations.filter(process_version=2).exists()
    assert context.validation_state == VALIDATION_STALE


@pytest.mark.django_db
def test_short_path_binds_without_open_hypothesis(owner, business_unit):
    process = make_process(owner, business_unit)
    process.diagnostic_observations = "Der Vergleich benötigt fünf Tage."
    process.confirmed_causes = "Angebotsdaten liegen nicht strukturiert vor."
    process.save(update_fields=["diagnostic_observations", "confirmed_causes", "updated_at"])
    selected = make_complete_option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    make_complete_option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )

    decision = select_preferred_solution(
        process_analysis=process,
        selected_option=selected,
        rationale="Die bestätigte Ursache ist ohne offene Hypothese ausreichend dokumentiert.",
        actor=owner,
    )

    assert process.cause_hypotheses == ""
    assert process.constraints == ""
    assert decision.selected_option == selected


@pytest.mark.django_db
def test_process_detail_separates_hypothesis_from_confirmed_cause(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit, with_diagnosis=True)
    client.force_login(owner)

    response = client.get(process.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "Ursachen und Randbedingungen" in content
    assert "Beobachtung / Problem" in content
    assert "Hypothese / nicht bestätigt" in content
    assert "Bestätigte Ursache" in content
    assert "Kernbefund" in content
    assert "wird nicht automatisch" in content


@pytest.mark.django_db
def test_short_path_does_not_show_unconfirmed_badge_without_hypothesis(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    process.diagnostic_observations = "Der Vergleich benötigt fünf Tage."
    process.confirmed_causes = "Angebotsdaten liegen nicht strukturiert vor."
    process.save(update_fields=["diagnostic_observations", "confirmed_causes", "updated_at"])
    client.force_login(owner)

    content = client.get(process.get_absolute_url()).content.decode()

    assert "Keine offene Hypothese dokumentiert" in content
    assert "Hypothese / nicht bestätigt" not in content
