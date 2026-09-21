import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ProcessAnalysisForm
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import (
    comparison_blockers,
    diagnosis_readiness_blockers,
    ordered_solution_options,
    select_preferred_solution,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_process(owner, business_unit, *, with_diagnosis=False):
    stream = ValueStream.objects.create(
        name="Diagnose-Readiness",
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
        rationale="Deep Dive ist fachlich priorisiert.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        pain_points="Manuelle Übertragung und Rückfragen",
        baseline_metrics="Fünf Tage",
    )
    diagnosis = {}
    if with_diagnosis:
        diagnosis = {
            "diagnostic_observations": "Der Vergleich benötigt fünf Tage und mehrere Rückfragen.",
            "cause_hypotheses": "Uneinheitliche Formate erhöhen den manuellen Aufwand.",
            "confirmed_causes": "Angebotsdaten liegen nicht strukturiert vor.",
        }
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        status=ProcessAnalysis.Status.VALIDATED,
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell übertragen und verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterien",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        baseline_metrics="Fünf Tage",
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
        bottleneck_coverage="Reduziert die manuelle Übertragung.",
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
def test_legacy_bottlenecks_are_not_reinterpreted_as_diagnosis(owner, business_unit):
    process = make_process(owner, business_unit)

    assert process.bottlenecks
    assert process.diagnostic_observations == ""
    assert process.cause_hypotheses == ""
    assert process.confirmed_causes == ""
    assert diagnosis_readiness_blockers(process) == [
        "Beobachtung/Problem",
        "bestätigte Ursache",
    ]


@pytest.mark.django_db
def test_hypothesis_without_confirmed_cause_does_not_make_diagnosis_ready(owner, business_unit):
    process = make_process(owner, business_unit)
    process.diagnostic_observations = "Der Vergleich benötigt fünf Tage."
    process.cause_hypotheses = "Uneinheitliche Formate könnten die Ursache sein."

    assert diagnosis_readiness_blockers(process) == ["bestätigte Ursache"]


@pytest.mark.django_db
def test_solution_exploration_stays_open_without_diagnosis(owner, business_unit):
    process = make_process(owner, business_unit)
    first = make_complete_option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    second = make_complete_option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )

    options = ordered_solution_options(process)

    assert options == [first, second]
    assert comparison_blockers(options) == []
    assert diagnosis_readiness_blockers(process)


@pytest.mark.django_db
def test_binding_preference_is_blocked_until_confirmed_diagnosis(owner, business_unit):
    process = make_process(owner, business_unit)
    first = make_complete_option(
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

    with pytest.raises(ValidationError) as exc_info:
        select_preferred_solution(
            process_analysis=process,
            selected_option=first,
            rationale="Die einfachere Option ist ausreichend.",
            actor=owner,
        )

    message = " ".join(exc_info.value.messages)
    assert "Diagnose noch nicht belastbar" in message
    assert "Beobachtung/Problem" in message
    assert "bestätigte Ursache" in message
    assert "weiterhin exploriert und verglichen" in message
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_confirmed_diagnosis_allows_preference_without_constraint(owner, business_unit):
    process = make_process(owner, business_unit, with_diagnosis=True)
    first = make_complete_option(
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
        selected_option=first,
        rationale="Die organisatorische Option adressiert die bestätigte Ursache ausreichend.",
        actor=owner,
    )

    assert process.constraints == ""
    assert decision.selected_option == first
    assert decision.process_version == process.version
    assert decision.diagnosis_snapshot == {
        "diagnostic_observations": process.diagnostic_observations,
        "cause_hypotheses": process.cause_hypotheses,
        "confirmed_causes": process.confirmed_causes,
        "constraints": "",
        "validation": None,
    }

    ProcessAnalysis.objects.filter(pk=process.pk).update(
        version=process.version + 1,
        confirmed_causes="Eine später bestätigte andere Ursache.",
    )
    decision.refresh_from_db()
    assert decision.process_version == process.version
    assert decision.diagnosis_snapshot["confirmed_causes"] == (
        "Angebotsdaten liegen nicht strukturiert vor."
    )


@pytest.mark.django_db
def test_compare_view_surfaces_actionable_diagnosis_blocker(client, owner, business_unit):
    process = make_process(owner, business_unit)
    first = make_complete_option(
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
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", kwargs={"pk": process.pk})

    initial_response = client.get(url)
    initial_content = initial_response.content.decode()
    assert initial_response.status_code == 200
    assert "Vor einer verbindlichen Präferenz" in initial_content
    assert "Es fehlen: Beobachtung/Problem, bestätigte Ursache" in initial_content
    assert "Diagnose ergänzen" in initial_content
    assert "Bevorzugte Option auswählen</button>" not in initial_content

    response = client.post(
        url,
        {
            "selected_option": first.pk,
            "rationale": "Die einfachere Option ist ausreichend.",
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Diagnose noch nicht belastbar" in content
    assert "weiterhin exploriert und verglichen" in content
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_process_analysis_form_exposes_optional_diagnosis_semantics():
    form = ProcessAnalysisForm()

    assert form.fields["diagnostic_observations"].required is False
    assert form.fields["cause_hypotheses"].required is False
    assert form.fields["confirmed_causes"].required is False
    assert form.fields["constraints"].required is False
    assert form.fields["diagnostic_observations"].label == "Beobachtung / Problem"
    assert "unbestätigt" in form.fields["cause_hypotheses"].help_text
    assert "bestätigte" in form.fields["confirmed_causes"].help_text
    assert "Gesamtfluss" in form.fields["constraints"].help_text
    assert "nicht automatisch ein Constraint" in form.fields["constraints"].help_text


@pytest.mark.django_db
def test_diagnosis_change_versions_validated_process(client, owner, business_unit):
    process = make_process(owner, business_unit, with_diagnosis=True)
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
    assert response.status_code == 302
    assert process.version == 2
    assert process.status == ProcessAnalysis.Status.REVIEW_REQUIRED
