import json
from decimal import Decimal

import pytest

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    EvidenceBasis,
    ProcessAnalysis,
    SolutionOption,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.core.models import LLMTaskRun
from ki_radar.core.openrouter import OpenRouterResult
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.ap2_metric_pilot import (
    AP2MetricPilotError,
    TARGET_FIELDS,
    build_ap2_metric_pilot_context,
    generate_and_apply_ap2_metric_pilot,
    validate_ap2_metric_pilot_payload,
)
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.services import create_use_case_from_selected_solution


pytestmark = pytest.mark.django_db


def _process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bezahlte Leistung",
        scope_in="Bedarf bis Zahlung",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Source-to-Pay",
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
        actors="Einkauf",
        systems="ERP und Dateiablage",
        documents="Angebote und Kriterien",
        pain_points="Manuelle Übertragung",
        baseline_metrics="Bearbeitungszeit wird heute pro Vorgang dokumentiert.",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterien",
        bottlenecks="Manuelle Übertragung verlängert die Bearbeitung.",
        diagnostic_observations="Der Angebotsvergleich bindet viel manuelle Bearbeitungszeit.",
        cause_hypotheses="Uneinheitliche Angebotsformate erhöhen den Übertragungsaufwand.",
        confirmed_causes="Unstrukturierte Angebotsdaten erzwingen manuelle Übertragung.",
        constraints="Die fachliche Lieferantenauswahl bleibt beim Einkauf.",
        baseline_metrics="Bearbeitungszeit wird heute pro Vorgang dokumentiert.",
        analyzed_by=owner,
    )


def _option(process, owner, *, name, option_type):
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=option_type,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        evidence_basis=EvidenceBasis.INDICATIVE,
        description=f"Beschreibung {name}",
        expected_value="Manuelle Bearbeitungszeit reduzieren.",
        time_to_value=TimeToValue.UNKNOWN,
        bottleneck_coverage="Reduziert die manuelle Übertragung.",
        feasibility=SolutionOption.Effort.MEDIUM,
        data_requirements="Angebote und Kriterien",
        application_impact="Ergänzung der Fachanwendung",
        integration_effort=SolutionOption.Effort.MEDIUM,
        integration_impact="Lesender Zugriff auf den ERP-Export.",
        technology_constraints="ERP bleibt führend.",
        risks="Extraktionsfehler müssen fachlich erkannt werden.",
        architecture_fit="Assistenz mit menschlicher Entscheidung.",
        created_by=owner,
    )


def _ai_use_case(owner, business_unit):
    process = _process(owner, business_unit)
    _option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    assistant = _option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )
    decision = select_preferred_solution(
        process_analysis=process,
        selected_option=assistant,
        rationale="Die Assistenz adressiert die verbleibende unstrukturierte Extraktion.",
        actor=owner,
    )
    return create_use_case_from_selected_solution(decision=decision, actor=owner).use_case


def _statement(value, source_id="UC.benefit", evidence_basis="hypothesis"):
    return {
        "value": value,
        "source_ids": [source_id],
        "evidence_basis": evidence_basis,
    }


def _payload():
    return {
        "metric_name": _statement("Bearbeitungszeit je Angebotsvergleich"),
        "metric_type": _statement("duration"),
        "metric_direction": _statement("lower"),
        "metric_unit": _statement("Minuten"),
        "metric_measurement_method": _statement(
            "Zeit vom vollständigen Eingang bis zur vergleichbaren Entscheidungsgrundlage."
        ),
        "metric_measurement_population": _statement(
            "Reguläre Angebotsvergleiche im fachlich freigegebenen Prozessscope."
        ),
        "metric_measurement_period": _statement(
            "Ein repräsentativer regulärer Geschäftszyklus ohne künstliche Mindestdauer."
        ),
        "pilot_scope": _statement(
            "Ein abgegrenzter Beschaffungsfalltyp mit menschlicher Prüfung jedes Ergebnisses."
        ),
        "pilot_review_criteria": _statement(
            "Messbarkeit, fachliche Korrektheit, Nutzbarkeit und verbleibender manueller Aufwand."
        ),
        "pilot_abort_criteria": _statement(
            "Pilot unterbrechen, wenn fachliche Fehler nicht zuverlässig erkannt werden "
            "oder der menschliche Kontrollpunkt nicht wirksam bleibt."
        ),
        "unknowns": [
            "Eine belastbare numerische Baseline und ein Zielwert sind noch nicht belegt."
        ],
    }


def _provider_result(payload):
    content = json.dumps(payload)
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
            "cost": 0.001,
        },
        output_chars=len(content),
        finish_reason="stop",
    )


def test_grounded_metric_pilot_draft_fills_only_non_numeric_plan_fields(
    owner,
    business_unit,
    monkeypatch,
):
    use_case = _ai_use_case(owner, business_unit)
    assert use_case.metric_baseline is None
    assert use_case.metric_target is None

    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_metric_pilot.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(_payload()),
    )

    result = generate_and_apply_ap2_metric_pilot(use_case=use_case, actor=owner)

    use_case.refresh_from_db()
    assert set(result.changed_fields) == set(TARGET_FIELDS)
    assert use_case.metric_name == "Bearbeitungszeit je Angebotsvergleich"
    assert use_case.metric_type == UseCase.MetricType.DURATION
    assert use_case.metric_direction == UseCase.MetricDirection.LOWER
    assert use_case.metric_unit == "Minuten"
    assert use_case.pilot_scope.startswith("Ein abgegrenzter Beschaffungsfalltyp")
    assert use_case.metric_baseline is None
    assert use_case.metric_target is None
    assert use_case.planned_pilot_end is None
    assert use_case.pilot_start is None
    assert use_case.ap2_planning_provenance["generated_by"] == "system"
    assert use_case.ap2_planning_provenance["run_id"] == result.run_id
    assert "UC.benefit" in use_case.ap2_planning_provenance["field_sources"]["metric_name"][
        "source_ids"
    ]
    assert LLMTaskRun.objects.get(pk=result.run_id).status == LLMTaskRun.Status.SUCCESS


def test_existing_metric_values_and_numeric_evidence_are_never_overwritten(
    owner,
    business_unit,
    monkeypatch,
):
    use_case = _ai_use_case(owner, business_unit)
    use_case.metric_name = "Manuell bestätigte Durchlaufzeit"
    use_case.metric_baseline = Decimal("12.5")
    use_case.metric_target = Decimal("10")
    use_case.save(
        update_fields=[
            "metric_name",
            "metric_baseline",
            "metric_target",
            "updated_at",
        ]
    )
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_metric_pilot.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(_payload()),
    )

    generate_and_apply_ap2_metric_pilot(use_case=use_case, actor=owner)

    use_case.refresh_from_db()
    assert use_case.metric_name == "Manuell bestätigte Durchlaufzeit"
    assert use_case.metric_baseline == Decimal("12.5")
    assert use_case.metric_target == Decimal("10")


def test_measured_claim_requires_actual_measurement_source(owner, business_unit):
    use_case = _ai_use_case(owner, business_unit)
    context = build_ap2_metric_pilot_context(use_case)
    payload = _payload()
    payload["metric_name"] = _statement(
        "Bearbeitungszeit",
        source_id="UC.benefit",
        evidence_basis="measured",
    )

    with pytest.raises(AP2MetricPilotError, match="Mess- oder Berechnungsquelle"):
        validate_ap2_metric_pilot_payload(payload, context=context)


def test_source_change_during_provider_call_fails_closed(
    owner,
    business_unit,
    monkeypatch,
):
    use_case = _ai_use_case(owner, business_unit)
    process = use_case.architecture_origin.process_analysis

    def provider(_prepared, **_kwargs):
        ProcessAnalysis.objects.filter(pk=process.pk).update(
            confirmed_causes="Zwischenzeitlich fachlich korrigierte Ursache."
        )
        return _provider_result(_payload())

    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_metric_pilot.request_llm_task_provider",
        provider,
    )

    with pytest.raises(AP2MetricPilotError) as exc_info:
        generate_and_apply_ap2_metric_pilot(use_case=use_case, actor=owner)

    assert exc_info.value.code == "source_stale"
    use_case.refresh_from_db()
    assert use_case.metric_name == ""
    assert use_case.ap2_planning_provenance == {}
    run = LLMTaskRun.objects.get(task_type=LLMTaskRun.TaskType.AP2_METRIC_PILOT_DRAFT)
    assert run.status == LLMTaskRun.Status.FAILED
    assert run.error_code == "source_stale"
