import json
from decimal import Decimal

import pytest
from django.utils import timezone

from ki_radar.architecture.architecture_assessment import (
    save_solution_architecture_assessment,
)
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
from ki_radar.delivery.ap3_autonomous import (
    AP3DeliveryError,
    prepare_autonomous_delivery_package,
    TARGET_FIELDS,
)
from ki_radar.delivery.models import DeliveryPackage, DeliverySectionReview
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.governance.services import create_screening_review_artifacts
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
        scope_in="Angebotsvergleich",
        scope_out="Verhandlung und Bestellung",
        status=ValueStream.Status.ACTIVE,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        actors="Einkauf",
        systems="ERP und Dateiablage",
        documents="Angebote und Kriterien",
        pain_points="Manuelle Übertragung",
        baseline_metrics="Bearbeitungszeit wird pro Vorgang dokumentiert.",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell übertragen und verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterien",
        business_rules="Finale Lieferantenauswahl bleibt beim Einkauf.",
        handoffs="Fachbereich bestätigt Muss-Kriterien.",
        bottlenecks="Manuelle Übertragung verlängert die Bearbeitung.",
        diagnostic_observations="Unterschiedliche Formate erzeugen Rückfragen.",
        cause_hypotheses="Unstrukturierte Daten erhöhen den manuellen Aufwand.",
        confirmed_causes="Unstrukturierte Angebotsdaten erzwingen manuelle Übertragung.",
        constraints="ERP bleibt führendes System.",
        exceptions="Unvollständige Angebote gehen zurück an den Einkauf.",
        baseline_metrics="Bearbeitungszeit wird pro Vorgang dokumentiert.",
        target_state_principles="Assistieren statt autonom entscheiden.",
        analyzed_by=owner,
    )


def _option(process, owner, *, name, option_type, contains_ai=False):
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=option_type,
        contains_ai_component=contains_ai,
        evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
        evidence_basis=EvidenceBasis.INDICATIVE,
        description=f"{name} strukturiert Angebotsdaten und unterstützt den Vergleich.",
        expected_value="Manuelle Übertragung reduzieren und Vergleich nachvollziehbar machen.",
        time_to_value=TimeToValue.UNKNOWN,
        bottleneck_coverage="Adressiert die manuelle Übertragung.",
        feasibility=SolutionOption.Effort.MEDIUM,
        data_requirements="Angebote, Kriterien und Lieferantenstammdaten.",
        application_impact="Ergänzung der bestehenden Fachanwendung.",
        integration_effort=SolutionOption.Effort.MEDIUM,
        integration_impact="Lesender ERP-Export und Dateiablage.",
        technology_constraints="ERP bleibt führend.",
        risks="Extraktionsfehler müssen fachlich erkannt werden.",
        architecture_fit="Kontrollierte Assistenz mit menschlicher Entscheidung.",
        created_by=owner,
    )


def _approved_ap3_case(owner, business_unit):
    process = _process(owner, business_unit)
    _option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    selected = _option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
        contains_ai=True,
    )
    selection = select_preferred_solution(
        process_analysis=process,
        selected_option=selected,
        rationale="Die Assistenz adressiert die verbleibende unstrukturierte Extraktion.",
        actor=owner,
    )
    use_case = create_use_case_from_selected_solution(
        decision=selection,
        actor=owner,
    ).use_case
    use_case.technical_owner = owner
    use_case.source_systems = "ERP und Dateiablage"
    use_case.data_sources = "Angebote, Kriterien und Lieferantenstammdaten"
    use_case.interface_description = "Lesender ERP-Export"
    use_case.human_oversight = "Einkauf prüft jeden Vorschlag vor der Übernahme."
    use_case.support_responsibility = "Application Management"
    use_case.metric_name = "Bearbeitungszeit"
    use_case.metric_type = UseCase.MetricType.DURATION
    use_case.metric_direction = UseCase.MetricDirection.LOWER
    use_case.metric_unit = "Minuten"
    use_case.metric_baseline = Decimal("45")
    use_case.metric_target = Decimal("30")
    use_case.metric_measurement_method = "Median der Bearbeitungszeit je Angebotsvergleich."
    use_case.metric_measurement_population = "Reguläre Angebotsvergleiche im Pilot."
    use_case.metric_measurement_period = "Pilotphase"
    use_case.pilot_scope = "Abgegrenzter Angebotsvergleich mit menschlicher Kontrolle."
    use_case.pilot_review_criteria = "Fachliche Korrektheit und verbleibender manueller Aufwand."
    use_case.pilot_abort_criteria = "Abbruch bei nicht kontrollierbaren fachlichen Fehlern."
    use_case.success_criterion = "Bearbeitungszeit sinkt bei fachlich korrekten Ergebnissen."
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save()

    save_solution_architecture_assessment(
        solution_option=selected,
        answers={
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "no",
        },
        actor=owner,
    )

    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=owner,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        rationale="Fachlicher und technischer Kontext ist für die Delivery vorbereitet.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )

    screening = GovernanceAssessment(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=owner,
        basis_version="test-ap3",
        personal_data=False,
        employee_data=False,
        automated_person_assessment=False,
        influences_person_decisions=False,
        biometric_data=False,
        safety_critical=False,
        regulated_product=False,
        health_safety_rights_impact=False,
        external_ai_or_cloud=False,
        generated_external_content=False,
        human_oversight_planned=True,
        privacy_review_required=False,
        security_review_required=False,
        legal_review_required=False,
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Keine formalen Reviews erforderlich.",
    )
    screening.full_clean()
    screening.save()
    create_screening_review_artifacts(assessment=screening, actor=owner)

    approval = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigabe für Delivery.",
        decided_by=owner,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case, approval


def _provider_result(payload):
    content = json.dumps(payload)
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        output_chars=len(content),
        finish_reason="stop",
    )


def _synthesis_payload(
    *,
    functional_requirements="Konkreter fachlicher Ablauf aus dem freigegebenen Prozess.",
):
    payload = {
        field_name: {
            "value": f"Konkreter fallbezogener Inhalt für {field_name.replace('_', ' ')}.",
            "source_ids": ["DEL.problem_context"],
            "basis": "derived",
        }
        for field_name in TARGET_FIELDS
    }
    payload["functional_requirements"]["value"] = functional_requirements
    payload["unknowns"] = []
    return payload


def _verifier_payload(*, repair=False):
    if not repair:
        return {
            "verdict": "pass",
            "critical_findings": [],
            "noncritical_findings": [],
        }
    return {
        "verdict": "repair",
        "critical_findings": [
            {
                "code": "REQ_TOO_GENERIC",
                "fields": ["functional_requirements"],
                "rationale": "Die funktionale Anforderung ist noch nicht fallbezogen genug.",
                "source_ids": ["DEL.problem_context"],
            }
        ],
        "noncritical_findings": [],
    }


def _repair_payload():
    return {
        "repairs": [
            {
                "field": "functional_requirements",
                "value": (
                    "Eingehende Angebotsdaten aus dem belegten Quellkontext strukturiert "
                    "aufbereiten und dem Einkauf zur fachlichen Prüfung vorlegen."
                ),
                "source_ids": ["DEL.problem_context"],
                "basis": "derived",
            }
        ],
        "unknowns": [],
    }


def test_ap3_prepares_one_canonical_package_with_mapper_synthesis_and_verifier(
    owner, business_unit, monkeypatch
):
    use_case, approval = _approved_ap3_case(owner, business_unit)
    calls = []

    def fake_provider(_prepared, *, response_format):
        name = response_format["json_schema"]["name"]
        calls.append(name)
        if name == "ap3_delivery_synthesis":
            return _provider_result(_synthesis_payload())
        if name == "ap3_delivery_verification":
            return _provider_result(_verifier_payload())
        raise AssertionError(name)

    monkeypatch.setattr(
        "ki_radar.delivery.ap3_autonomous.request_llm_task_provider",
        fake_provider,
    )

    result = prepare_autonomous_delivery_package(use_case=use_case, actor=owner)
    package = result.package
    package.refresh_from_db()

    assert result.created is True
    assert package.generated_from_decision_id == approval.pk
    assert package.status == DeliveryPackage.Status.DRAFT
    assert package.problem_context == use_case.problem_statement
    assert package.functional_requirements
    assert package.mvp_scope
    assert package.architecture_artifacts.system_responsibilities
    assert package.section_reviews.count() == 7
    assert set(package.section_reviews.values_list("review_status", flat=True)) == {
        DeliverySectionReview.ReviewStatus.NEEDS_REVIEW
    }
    assert calls == ["ap3_delivery_synthesis", "ap3_delivery_verification"]
    assert LLMTaskRun.objects.filter(
        task_type=LLMTaskRun.TaskType.AP3_DELIVERY_PACKAGE,
        object_id=str(package.pk),
    ).count() == 2
    assert not package.handed_over_at
    assert GovernanceReview.objects.filter(result=GovernanceReview.Result.PASSED).count() == 0

    for review in package.section_reviews.all():
        assert "ap3_verifier" in review.source_manifest
        assert review.source_manifest["ap3_verifier"]["verdict"] == "pass"


def test_ap3_resume_is_idempotent_and_does_not_create_or_call_provider_again(
    owner, business_unit, monkeypatch
):
    use_case, _approval = _approved_ap3_case(owner, business_unit)
    calls = []

    def fake_provider(_prepared, *, response_format):
        name = response_format["json_schema"]["name"]
        calls.append(name)
        if name == "ap3_delivery_synthesis":
            return _provider_result(_synthesis_payload())
        return _provider_result(_verifier_payload())

    monkeypatch.setattr(
        "ki_radar.delivery.ap3_autonomous.request_llm_task_provider",
        fake_provider,
    )
    first = prepare_autonomous_delivery_package(use_case=use_case, actor=owner)
    before_calls = len(calls)

    second = prepare_autonomous_delivery_package(use_case=use_case, actor=owner)

    assert second.package.pk == first.package.pk
    assert second.created is False
    assert DeliveryPackage.objects.filter(use_case=use_case).count() == 1
    assert len(calls) == before_calls


def test_ap3_never_overwrites_existing_manual_delivery_content(
    owner, business_unit, monkeypatch
):
    use_case, _approval = _approved_ap3_case(owner, business_unit)
    from ki_radar.delivery.services import create_delivery_package

    package = create_delivery_package(
        use_case=use_case,
        actor=owner,
        use_evidence_mapper=True,
    )
    package.functional_requirements = "Manuell bestätigte funktionale Anforderung."
    package.save(update_fields=["functional_requirements", "updated_at"])

    def fake_provider(_prepared, *, response_format):
        name = response_format["json_schema"]["name"]
        if name == "ap3_delivery_synthesis":
            return _provider_result(
                _synthesis_payload(
                    functional_requirements="Systemvorschlag, der nicht gewinnen darf."
                )
            )
        return _provider_result(_verifier_payload())

    monkeypatch.setattr(
        "ki_radar.delivery.ap3_autonomous.request_llm_task_provider",
        fake_provider,
    )
    result = prepare_autonomous_delivery_package(use_case=use_case, actor=owner)
    result.package.refresh_from_db()

    assert result.package.functional_requirements == "Manuell bestätigte funktionale Anforderung."


def test_ap3_allows_one_targeted_repair_and_reverifies(
    owner, business_unit, monkeypatch
):
    use_case, _approval = _approved_ap3_case(owner, business_unit)
    verifier_calls = 0

    def fake_provider(_prepared, *, response_format):
        nonlocal verifier_calls
        name = response_format["json_schema"]["name"]
        if name == "ap3_delivery_synthesis":
            return _provider_result(_synthesis_payload())
        if name == "ap3_delivery_repair":
            return _provider_result(_repair_payload())
        if name == "ap3_delivery_verification":
            verifier_calls += 1
            return _provider_result(_verifier_payload(repair=verifier_calls == 1))
        raise AssertionError(name)

    monkeypatch.setattr(
        "ki_radar.delivery.ap3_autonomous.request_llm_task_provider",
        fake_provider,
    )
    result = prepare_autonomous_delivery_package(use_case=use_case, actor=owner)
    result.package.refresh_from_db()

    assert verifier_calls == 2
    assert result.verification.verdict == "pass"
    assert result.repaired_fields == ("functional_requirements",)
    assert "Eingehende Angebotsdaten" in result.package.functional_requirements
    assert LLMTaskRun.objects.filter(
        task_type=LLMTaskRun.TaskType.AP3_DELIVERY_PACKAGE,
        object_id=str(result.package.pk),
    ).count() == 4


def test_ap3_rejects_ungrounded_quantitative_delivery_claim(
    owner, business_unit, monkeypatch
):
    use_case, _approval = _approved_ap3_case(owner, business_unit)
    payload = _synthesis_payload()
    payload["functional_requirements"]["value"] = (
        "Der Ablauf muss innerhalb von 999 Sekunden enden."
    )

    monkeypatch.setattr(
        "ki_radar.delivery.ap3_autonomous.request_llm_task_provider",
        lambda _prepared, **_kwargs: _provider_result(payload),
    )

    with pytest.raises(AP3DeliveryError) as exc_info:
        prepare_autonomous_delivery_package(use_case=use_case, actor=owner)

    assert exc_info.value.code == "ungrounded_quantitative_claim"
    package = DeliveryPackage.objects.get(use_case=use_case)
    assert package.functional_requirements == ""
    run = LLMTaskRun.objects.get(
        task_type=LLMTaskRun.TaskType.AP3_DELIVERY_PACKAGE,
        object_id=str(package.pk),
    )
    assert run.status == LLMTaskRun.Status.FAILED
