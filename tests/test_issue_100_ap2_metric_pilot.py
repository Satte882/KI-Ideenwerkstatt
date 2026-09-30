import json
from decimal import Decimal

import pytest

from ki_radar.architecture.ap2_architecture import generate_ap2_architecture_inputs
from ki_radar.architecture.architecture_assessment_models import SolutionArchitectureAssessment
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
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.use_cases.ap2_decision_governance import (
    ASSESSMENT_FIELDS,
    GOVERNANCE_FIELDS,
    generate_ap2_decision_governance,
)
from ki_radar.use_cases.ap2_metric_pilot import (
    TARGET_FIELDS,
    AP2MetricPilotError,
    build_ap2_metric_pilot_context,
    generate_and_apply_ap2_metric_pilot,
    validate_ap2_metric_pilot_payload,
)
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
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


def _architecture_payload():
    return {
        name: {
            "value": value,
            "source_ids": ["SO.description"],
            "rationale": "Aus dem beschriebenen Assistenzfall abgeleitet.",
        }
        for name, value in {
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "no",
        }.items()
    }


def _decision_governance_payload():
    values = {
        "business_value": "medium",
        "strategic_fit": "medium",
        "technical_feasibility": "medium",
        "data_readiness": "medium",
        "risk_complexity": "medium",
        "evidence_recency": "limited",
        "evidence_coverage": "limited",
        "independent_review": "critical",
        "assumptions_resolved": "limited",
        "recommendation": "deferred",
        "rationale": "present",
    }
    assert set(values) == set(ASSESSMENT_FIELDS)
    facts = {name: "unknown" for name in GOVERNANCE_FIELDS}
    return {
        "assessment": {
            name: {
                "value": value,
                "source_ids": ["UC.problem"],
                "rationale": "Analyse mit offener Evidenzgrenze.",
            }
            for name, value in values.items()
        },
        "governance": {
            name: {
                "value": value,
                "source_ids": ["UC.problem"],
                "rationale": "Im Fallkontext geprüft; Unbekanntes bleibt offen.",
                "evidence_quote": "",
            }
            for name, value in facts.items()
        },
    }


def test_ap2_architecture_uses_deterministic_advisor_and_preserves_human_input(
    owner, business_unit, monkeypatch
):
    use_case = _ai_use_case(owner, business_unit)
    monkeypatch.setattr(
        "ki_radar.architecture.ap2_architecture.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(_architecture_payload()),
    )
    architecture = generate_ap2_architecture_inputs(use_case=use_case, actor=owner)
    assert architecture.architecture_mode == "controlled_llm"
    assert architecture.assessed_by is None
    assert architecture.ap2_provenance["generated_by"] == "system"
    assert SolutionArchitectureAssessment.objects.count() == 1
    assert generate_ap2_architecture_inputs(use_case=use_case, actor=owner).pk == architecture.pk
    architecture.ap2_provenance = {}
    architecture.assessed_by = owner
    architecture.save(update_fields=["ap2_provenance", "assessed_by"])
    assert generate_ap2_architecture_inputs(use_case=use_case, actor=owner).assessed_by == owner


def test_ap2_decision_governance_unknown_stays_unmaterialized_until_human_answer(
    owner, business_unit, monkeypatch, client
):
    use_case = _ai_use_case(owner, business_unit)
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_decision_governance.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(_decision_governance_payload()),
    )
    assert generate_ap2_decision_governance(use_case=use_case, actor=owner) is None
    use_case.refresh_from_db()
    assessment = DecisionAssessment.objects.get(use_case=use_case)
    assert assessment.assessed_by is None
    assert assessment.ap2_provenance["generated_by"] == "system"
    assert assessment.evidence_quality == DecisionAssessment.EvidenceQuality.EXPERT_OPINION
    assert not ApprovalDecision.objects.exists()
    assert not GovernanceAssessment.objects.exists()
    assert use_case.ap2_governance_draft["facts"]["personal_data"]["value"] == "unknown"

    client.force_login(owner)
    surface = client.get(f"{use_case.get_absolute_url()}ap2-decision/")
    assert surface.status_code == 200
    assert "Werden personenbezogene Daten verarbeitet?" in surface.content.decode()
    assert "Systemgenerierte Analyse" in surface.content.decode()

    answer_response = client.post(
        f"{use_case.get_absolute_url()}ap2-decision/",
        {
            "source_hash": use_case.ap2_governance_draft["source_hash"],
            **{name: "no" for name in GOVERNANCE_FIELDS},
            "personal_data": "yes",
            "external_ai_or_cloud": "yes",
            "human_oversight_planned": "yes",
        },
    )
    assert answer_response.status_code == 302
    screening = GovernanceAssessment.objects.get(use_case=use_case)
    assert screening is not None
    assert screening.reviewer is None
    assert screening.personal_data is True
    assert screening.privacy_review_required is True
    assert screening.security_review_required is True
    assert screening.legal_review_required is False
    statuses = dict(GovernanceReview.objects.values_list("review_type", "status"))
    assert statuses == {
        "privacy": GovernanceReview.Status.OPEN,
        "security": GovernanceReview.Status.OPEN,
        "legal": GovernanceReview.Status.NOT_RELEVANT,
    }
    assert GovernanceReview.objects.filter(result="passed").count() == 0
    assert ApprovalDecision.objects.count() == 0
    assert generate_ap2_decision_governance(use_case=use_case, actor=owner).pk == screening.pk
    assert DecisionAssessment.objects.filter(use_case=use_case).count() == 1


def test_ap2_governance_materializes_only_quoted_yes_no_evidence(owner, business_unit, monkeypatch):
    use_case = _ai_use_case(owner, business_unit)
    facts = {name: "no" for name in GOVERNANCE_FIELDS}
    facts["external_ai_or_cloud"] = "yes"
    facts["human_oversight_planned"] = "yes"
    use_case.problem_statement = "Governance-Angaben: " + "; ".join(
        f"{name}={value}" for name, value in facts.items()
    )
    use_case.save(update_fields=["problem_statement", "updated_at"])
    payload = _decision_governance_payload()
    for name, value in facts.items():
        payload["governance"][name].update(value=value, evidence_quote=f"{name}={value}")
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_decision_governance.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(payload),
    )
    screening = generate_ap2_decision_governance(use_case=use_case, actor=owner)
    assert screening is not None
    assert screening.security_review_required is True
    assert screening.privacy_review_required is False
    assert screening.legal_review_required is False
    assert GovernanceReview.objects.filter(status=GovernanceReview.Status.OPEN).count() == 1
    assert GovernanceReview.objects.filter(status=GovernanceReview.Status.NOT_RELEVANT).count() == 2


def test_ap2_governance_downgrades_unquoted_negative_assertion(owner, business_unit, monkeypatch):
    use_case = _ai_use_case(owner, business_unit)
    payload = _decision_governance_payload()
    payload["governance"]["personal_data"].update(
        value="no", evidence_quote="Keine personenbezogenen Daten"
    )
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_decision_governance.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(payload),
    )
    assert generate_ap2_decision_governance(use_case=use_case, actor=owner) is None
    use_case.refresh_from_db()
    fact = use_case.ap2_governance_draft["facts"]["personal_data"]
    assert fact["value"] == "unknown"
    assert "keinen wörtlich nachvollziehbaren Beleg" in fact["rationale"]
    assert not GovernanceAssessment.objects.exists()
    assert DecisionAssessment.objects.count() == 1


def test_ap2_governance_conflicting_person_data_is_kept_unknown():
    from ki_radar.use_cases.ap2_decision_governance import _preserve_governance_conflicts

    facts = _decision_governance_payload()["governance"]
    facts["personal_data"].update(value="no", evidence_quote="keine Personendaten")
    facts["employee_data"].update(value="yes", evidence_quote="Beschäftigtendaten")
    normalized = _preserve_governance_conflicts(facts)
    assert normalized["personal_data"]["value"] == "unknown"
    assert normalized["personal_data"]["evidence_quote"] == ""
    assert "Widerspruch" in normalized["personal_data"]["rationale"]


def test_ap2_governance_does_not_apply_answers_after_process_changes(
    owner, business_unit, monkeypatch, client
):
    use_case = _ai_use_case(owner, business_unit)
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_decision_governance.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(_decision_governance_payload()),
    )
    generate_ap2_decision_governance(use_case=use_case, actor=owner)
    use_case.refresh_from_db()
    process = use_case.architecture_origin.process_analysis
    ProcessAnalysis.objects.filter(pk=process.pk).update(version=process.version + 1)
    client.force_login(owner)
    response = client.post(
        f"{use_case.get_absolute_url()}ap2-decision/",
        {
            "source_hash": use_case.ap2_governance_draft["source_hash"],
            **{name: "no" for name in GOVERNANCE_FIELDS},
        },
    )
    assert response.status_code == 302
    assert not GovernanceAssessment.objects.exists()


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
    assert (
        "UC.benefit"
        in use_case.ap2_planning_provenance["field_sources"]["metric_name"]["source_ids"]
    )
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
