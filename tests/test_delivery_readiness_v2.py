import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.delivery.models import (
    DeliveryPackage,
    DeliveryRoleSourceDecision,
    DeliverySectionReview,
)
from ki_radar.delivery.readiness import delivery_status_snapshot, evaluate_delivery_readiness
from ki_radar.delivery.services import (
    create_delivery_package,
    current_handed_over_package,
    render_delivery_markdown,
    resolve_technical_owner_source_change,
    review_delivery_section,
)
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.services import (
    PILOT_HANDOVER_BLOCKER,
    apply_status_transition,
    check_pilot_start,
)
from ki_radar.use_cases.workflow import build_use_case_journey

VALID_RETENTION_POLICY = (
    "Audit-/Traceability-Metadaten — Zweck: Nachvollziehbarkeit; Aufbewahrung: 24 Monate.\n"
    "Prompt-/Input-Rohinhalte — Zweck: Verarbeitung der Anfrage; nicht persistiert.\n"
    "Dokumentinhalte — Zweck: Fachliche Prüfung; Löschung nach Abschluss.\n"
    "Personenbezogene Daten — Zweck: Vorgangsbearbeitung; Löschung nach Zweckfortfall.\n"
    "Technische Logs/Betriebsdaten — Zweck: Störungsanalyse; Aufbewahrung: 30 Tage."
)


def make_approved_use_case(*, owner, technical_owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="Automatische Lieferantenauswahl",
        summary="Angebote strukturiert vergleichen.",
        problem_statement="Uneinheitliche Angebote erzeugen Rückfragen.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf",
        submitter=owner,
        business_owner=owner,
        technical_owner=technical_owner,
        source_systems="ERP, Shared Inbox, Dateiablage",
        data_sources="Angebote und Kriterienkatalog",
        interface_description="Dateiimport und ERP-Export",
        intended_users="Strategischer Einkauf",
        intended_purpose="Angebote extrahieren und vergleichbar darstellen.",
        expected_benefit="Durchlaufzeit reduzieren.",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Median über zehn Vorgänge.",
        metric_measurement_period="Vier Wochen.",
        human_oversight="Einkauf prüft und entscheidet.",
        support_responsibility="Application Management",
        decision_status=UseCase.DecisionStatus.APPROVED,
    )
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=coordinator,
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
        evidence_url="https://example.com/evidence",
        rationale="Repräsentative Messung und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigabe für Delivery.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case


@pytest.mark.django_db
def test_package_creates_seven_reviews_with_source_manifest(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )

    package = create_delivery_package(use_case=use_case, actor=coordinator)

    assert package.readiness_schema_version == 2
    assert package.section_reviews.count() == 7
    assert all(review.source_manifest for review in package.section_reviews.all())
    assert all(
        review.review_status == DeliverySectionReview.ReviewStatus.NEEDS_REVIEW
        for review in package.section_reviews.all()
    )


@pytest.mark.django_db
def test_solution_section_requires_business_and_technical_confirmation(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm",
        actor=owner,
        note="Fachlich bestätigt.",
    )
    review = package.section_reviews.get(section_key="solution_direction")
    assert review.business_confirmed_by == owner
    assert review.technical_confirmed_by is None
    assert review.review_status == DeliverySectionReview.ReviewStatus.NEEDS_REVIEW

    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm",
        actor=other_owner,
        note="Technisch bestätigt.",
    )
    review.refresh_from_db()
    assert review.technical_confirmed_by == other_owner
    assert review.review_status == DeliverySectionReview.ReviewStatus.CONFIRMED


@pytest.mark.django_db
def test_generic_prefill_and_open_reviews_are_readiness_blockers(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    findings = evaluate_delivery_readiness(package)
    codes = {finding.code for finding in findings}

    assert "SECTION_NEEDS_REVIEW" in codes
    assert "OUT_OF_SCOPE_MISSING" in codes
    assert "SYSTEM_RESPONSIBILITIES_GENERIC" in codes
    assert "OUTPUT_TYPE_SEMANTICS_MISSING" in codes
    assert "RETENTION_SEMANTICS_INCOMPLETE" in codes


@pytest.mark.django_db
def test_handed_over_status_remains_complete_with_current_readiness_findings(
    client,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    DeliveryPackage.objects.filter(pk=package.pk).update(
        status=DeliveryPackage.Status.HANDED_OVER,
        handed_over_at=timezone.now(),
    )
    use_case.status = UseCase.Status.REVIEW
    use_case.save(update_fields=["status", "updated_at"])
    package.refresh_from_db()

    snapshot = delivery_status_snapshot(package)
    exported = render_delivery_markdown(package)
    journey = build_use_case_journey(use_case, coordinator)
    outcome = build_outcome_workspace_journey(use_case, coordinator)
    delivery_step = next(step for step in journey.steps if step.key == "delivery")
    handover_step = next(step for step in outcome.steps if step.key == "handover")
    client.force_login(owner)
    response = client.get(reverse("delivery:package_detail", kwargs={"pk": package.pk}))
    list_response = client.get(reverse("delivery:package_list"))

    assert snapshot.code == "handover_inconsistent"
    assert snapshot.handover_complete is False
    assert "Status: Übergabe blockiert (inkonsistenter Bestand)" in exported
    assert "Übergabe blockiert (inkonsistenter Bestand)" in response.content.decode()
    assert "Übergabe blockiert (inkonsistenter Bestand)" in list_response.content.decode()
    assert current_handed_over_package(use_case) is None
    assert delivery_step.state == "complete"
    assert journey.completion_message == ""
    pilot_start_step = next(step for step in journey.steps if step.key == "pilot_start")
    assert pilot_start_step.state == "blocked"
    assert handover_step.state == "complete"
    assert PILOT_HANDOVER_BLOCKER not in check_pilot_start(use_case).blockers
    assert "Governance-Screening" in check_pilot_start(use_case).blockers
    with pytest.raises(ValidationError, match=r"reviews\.services\.create_review"):
        apply_status_transition(
            use_case=use_case,
            target_status=UseCase.Status.PILOT,
            actor=coordinator,
            pilot_start=timezone.localdate(),
        )


@pytest.mark.django_db
def test_internal_architecture_views_keep_artifact_export_meaningful_without_external_url(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.architecture_artifacts.artifacts_url = ""

    exported = render_delivery_markdown(package)

    assert "## Architekturartefakte und Diagramme" in exported
    assert "Im Delivery Package dokumentiert: Zielarchitektur/Systemkontext" in exported
    assert "Daten-/Informationsfluss" in exported


@pytest.mark.django_db
def test_percentage_quality_target_requires_population_and_sample_size(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.acceptance_criteria = "Fehlerquote < 2 %."
    package.test_scenarios = "Fachliche Ausgaben prüfen."
    package.measurement_plan = "Fehlerquote im Pilot ermitteln."

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "EVALUATION_POPULATION_MISSING" in codes
    assert "EVALUATION_SAMPLE_SIZE_MISSING" in codes
    assert "CRITICAL_ERROR_CLASSES_UNDOCUMENTED" in codes


@pytest.mark.django_db
def test_statistical_keywords_and_deferred_placeholders_are_not_evidence(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.acceptance_criteria = "Fehlerquote < 2 %. Recall > 90 %."
    package.test_scenarios = "Kritische Fehlerklassen später definieren; Testset später festlegen."
    package.measurement_plan = (
        "Testpopulation später festlegen. Stichprobengröße später festlegen. "
        "Aussagekraft später bewerten."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "EVALUATION_POPULATION_MISSING" in codes
    assert "EVALUATION_SAMPLE_SIZE_MISSING" in codes
    assert "EVALUATION_UNCERTAINTY_UNDOCUMENTED" in codes
    assert "CRITICAL_ERROR_CLASSES_UNDOCUMENTED" in codes
    assert "RECALL_POSITIVE_CASES_MISSING" in codes


@pytest.mark.django_db
def test_complete_statistical_context_clears_quality_warnings(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.acceptance_criteria = "Fehlerquote < 2 %. Recall > 90 %."
    package.test_scenarios = (
        "Kritische Fehlerklasse falscher Betrag wird mit 20 gezielten Testfällen geprüft."
    )
    package.measurement_plan = (
        "Testpopulation: eingehende Rechnungen; Stichprobengröße n=400; "
        "davon 62 positive Fälle; Aussagekraft über ein 95-%-Konfidenzintervall."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "EVALUATION_POPULATION_MISSING" not in codes
    assert "EVALUATION_SAMPLE_SIZE_MISSING" not in codes
    assert "EVALUATION_UNCERTAINTY_UNDOCUMENTED" not in codes
    assert "CRITICAL_ERROR_CLASSES_UNDOCUMENTED" not in codes
    assert "RECALL_POSITIVE_CASES_MISSING" not in codes


@pytest.mark.django_db
def test_critical_class_requires_its_own_non_negated_test_scope(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.acceptance_criteria = "Fehlerquote < 2 %."
    package.test_scenarios = (
        "Kritische Fehlerklasse falscher Betrag wird nicht getestet. "
        "20 Fälle decken ausschließlich den Happy Path ab."
    )
    package.measurement_plan = (
        "Testpopulation: eingehende Rechnungen; Stichprobengröße n=400; "
        "Aussagekraft über ein 95-%-Konfidenzintervall."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "CRITICAL_ERROR_CLASSES_UNDOCUMENTED" in codes


@pytest.mark.django_db
def test_generative_output_rejects_unjustified_numeric_confidence(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = "Jeder generative Textentwurf zeigt Confidence 87 %."

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED" in codes


@pytest.mark.parametrize(
    "statement",
    [
        "Generativer Textentwurf zeigt 87 % Konfidenz.",
        "Generativer Textentwurf zeigt Confidence 87 %, ist aber nicht kalibriert.",
    ],
)
@pytest.mark.django_db
def test_generative_confidence_recognizes_reverse_order_and_negated_calibration(
    statement,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = statement

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED" in codes


@pytest.mark.django_db
def test_output_types_require_grounding_or_rule_evidence(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = (
        "Generative Textentwürfe werden fachlich geprüft. "
        "Regelbasierte Prüfungen werden protokolliert."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "GENERATIVE_GROUNDING_INCOMPLETE" in codes
    assert "RULE_BASED_OUTPUT_EVIDENCE_INCOMPLETE" in codes


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        (
            "Generative Textentwürfe: Grounding ist deaktiviert. "
            "Unsicherheit wird nicht angezeigt.",
            "GENERATIVE_GROUNDING_INCOMPLETE",
        ),
        (
            "Regelbasierte Prüfungen haben keine Regelreferenz und kein Prüfergebnis.",
            "RULE_BASED_OUTPUT_EVIDENCE_INCOMPLETE",
        ),
    ],
)
@pytest.mark.django_db
def test_output_evidence_must_be_affirmative(
    statement,
    expected_code,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = statement

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert expected_code in codes


@pytest.mark.django_db
def test_missing_output_type_semantics_are_blocking(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = "Der Einkauf prüft und entscheidet."

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "OUTPUT_TYPE_SEMANTICS_MISSING" in codes


@pytest.mark.django_db
def test_calibrated_classifier_confidence_and_grounded_generation_are_allowed(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = (
        "Klassifikation: Confidence 0,8 ist kalibriert und fachlich definiert.\n"
        "Generative Textentwürfe zeigen Quellen und fehlende Grundlagen."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED" not in codes
    assert "GENERATIVE_GROUNDING_INCOMPLETE" not in codes


@pytest.mark.django_db
def test_explicitly_non_applicable_output_type_does_not_create_false_blocker(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = (
        "Keine generativen Ausgaben. Extraktion/Klassifikation: Es wird keine numerische "
        "Confidence ausgegeben; der Einkauf validiert das Ergebnis."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "OUTPUT_TYPE_SEMANTICS_MISSING" not in codes
    assert "GENERATIVE_GROUNDING_INCOMPLETE" not in codes


@pytest.mark.django_db
def test_reverse_output_type_non_applicability_does_not_create_blocker(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.human_oversight = (
        "Generative Texte: nicht anwendbar. Extraktion/Klassifikation: Es wird keine "
        "numerische Confidence ausgegeben; der Einkauf validiert das Ergebnis."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "OUTPUT_TYPE_SEMANTICS_MISSING" not in codes
    assert "GENERATIVE_GROUNDING_INCOMPLETE" not in codes


@pytest.mark.django_db
def test_synchronous_retry_cannot_exceed_end_to_end_latency_budget(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.non_functional_requirements = (
        "Nutzerseitiges Ende-zu-Ende-Latenzbudget P95 < 8 Sekunden. "
        "Provider-Timeout 8 Sekunden; danach 1 synchroner Retry."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "LATENCY_RETRY_BUDGET_CONFLICT" in codes


@pytest.mark.parametrize(
    "retry_text",
    [
        "Provider-Timeout 4 Sekunden; danach 2 synchrone Retries.",
        "Provider-Timeout 4 Sekunden; maximal zwei synchrone Wiederholungen.",
        ("Request-Timeout 6 Sekunden; Provider-Timeout 4 Sekunden; danach 1 synchroner Retry."),
    ],
)
@pytest.mark.django_db
def test_synchronous_retry_requires_complete_total_budget(
    retry_text,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.non_functional_requirements = (
        "Nutzerseitiges Ende-zu-Ende-Latenzbudget P95 < 8 Sekunden. " + retry_text
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "LATENCY_RETRY_BUDGET_CONFLICT" in codes


@pytest.mark.django_db
def test_explicit_total_sync_duration_within_budget_is_allowed(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.non_functional_requirements = (
        "Nutzerseitiges Ende-zu-Ende-Latenzbudget P95 < 8 Sekunden. "
        "Request-Timeout 6 Sekunden; Provider-Timeout 2 Sekunden; zwei synchrone Retries. "
        "Maximale Gesamtdauer aller synchronen Versuche: 6 Sekunden."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "LATENCY_RETRY_BUDGET_CONFLICT" not in codes


@pytest.mark.django_db
def test_explicit_total_cannot_contradict_calculated_retry_duration(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.non_functional_requirements = (
        "Nutzerseitiges Ende-zu-Ende-Latenzbudget P95 < 8 Sekunden. "
        "Provider-Timeout 4 Sekunden. Der Nutzerpfad ist synchron. "
        "Danach erfolgen zwei Retries. Maximale Gesamtdauer: 6 Sekunden."
    )

    findings = evaluate_delivery_readiness(package)
    latency_finding = next(
        finding for finding in findings if finding.code == "LATENCY_RETRY_BUDGET_CONFLICT"
    )

    assert "widerspricht" in latency_finding.message


@pytest.mark.django_db
def test_asynchronous_retry_does_not_conflict_with_user_latency_budget(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.non_functional_requirements = (
        "Nutzerseitiges Ende-zu-Ende-Latenzbudget P95 < 8 Sekunden. "
        "Provider-Timeout 8 Sekunden; ein Retry läuft asynchron außerhalb des Nutzerpfads."
    )

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "LATENCY_RETRY_BUDGET_CONFLICT" not in codes


@pytest.mark.django_db
def test_retention_requires_separate_raw_content_and_metadata_semantics(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.logging_and_audit = "Auditnachweise haben eine Aufbewahrung von 24 Monaten."

    findings = evaluate_delivery_readiness(package)
    retention = next(
        finding for finding in findings if finding.code == "RETENTION_SEMANTICS_INCOMPLETE"
    )

    assert retention.severity == "blocker"
    assert "Prompt-/Input-Rohinhalte" in retention.message
    assert "Dokumentinhalte" in retention.message


@pytest.mark.parametrize(
    "policy",
    [
        (
            "Audit-Metadaten, Prompt-Rohinhalte, Dokumentinhalte, personenbezogene Daten "
            "und technische Logs; keine Zweckbindung und keine Löschung vorgesehen."
        ),
        (
            "Audit-/Traceability-Metadaten — Zweck: Nachvollziehbarkeit; Frist benennen.\n"
            "Prompt-/Input-Rohinhalte — Zweck: Verarbeitung; nicht persistiert.\n"
            "Dokumentinhalte — Zweck: Prüfung; Löschung nach Abschluss.\n"
            "Personenbezogene Daten — Zweck: Bearbeitung; Löschung nach Zweckfortfall.\n"
            "Technische Logs/Betriebsdaten — Zweck: Betrieb; Aufbewahrung: 30 Tage."
        ),
    ],
)
@pytest.mark.django_db
def test_retention_rejects_keyword_lists_negation_and_placeholders(
    policy,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.logging_and_audit = policy

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "RETENTION_SEMANTICS_INCOMPLETE" in codes


@pytest.mark.django_db
def test_retention_requires_policy_even_without_retention_keywords(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.logging_and_audit = "Fachliche Entscheidungen werden protokolliert."

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "RETENTION_SEMANTICS_INCOMPLETE" in codes


@pytest.mark.django_db
def test_complete_retention_policy_with_non_persistence_is_allowed(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    package.logging_and_audit = VALID_RETENTION_POLICY

    codes = {finding.code for finding in evaluate_delivery_readiness(package)}

    assert "RETENTION_SEMANTICS_INCOMPLETE" not in codes


@pytest.mark.django_db
def test_not_applicable_requires_reason(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    with pytest.raises(ValidationError, match="begründet"):
        review_delivery_section(
            package=package,
            section_key="architecture_and_data",
            action="not_applicable",
            actor=coordinator,
            note="",
        )


@pytest.mark.django_db
def test_methodology_page_and_download_use_same_complete_file(client, owner):
    client.force_login(owner)
    source_path = Path(settings.BASE_DIR) / "docs" / "DELIVERY_METHODOLOGY.md"
    source = source_path.read_text(encoding="utf-8")

    page = client.get(reverse("delivery:methodology_reference"))
    download = client.get(reverse("delivery:methodology_download"))

    assert page.status_code == 200
    assert "Vorgehensmodell für produktionsreife KI-Systeme" in page.content.decode()
    assert "Vorgehensmodell herunterladen" in page.content.decode()
    assert download.status_code == 200
    assert download["Content-Type"].startswith("text/markdown")
    assert "attachment;" in download["Content-Disposition"]
    assert (
        "KI-Radar_Vorgehensmodell_CRISP-MLQ_ML-Test-Score_v2.0.md"
        in download["Content-Disposition"]
    )
    assert download.content.decode() == source


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("### A. Daten", "### B. Modell"),
        ("### B. Modell", "### C. Infrastruktur"),
        ("### C. Infrastruktur", "### D. Monitoring"),
        ("### D. Monitoring", "Die Liste ist eine deutschsprachige"),
    ],
)
def test_methodology_contains_all_28_ml_test_score_checks(start, end):
    source = (Path(settings.BASE_DIR) / "docs" / "DELIVERY_METHODOLOGY.md").read_text(
        encoding="utf-8"
    )
    block = source.split(start, 1)[1].split(end, 1)[0]
    assert len(re.findall(r"^\d+\.", block, flags=re.MULTILINE)) == 7


def test_methodology_contains_all_24_sections_and_required_components():
    source = (Path(settings.BASE_DIR) / "docs" / "DELIVERY_METHODOLOGY.md").read_text(
        encoding="utf-8"
    )
    for section_number in range(1, 25):
        assert re.search(rf"^# {section_number}\. ", source, flags=re.MULTILINE)
    for marker in [
        "Konflikt- und Eskalationsverfahren",
        "Stufe A: Kompaktes Vorhaben",
        "Stufe B: Standardvorhaben",
        "Stufe C: Erweitertes Vorhaben",
        "Berechnung des ML Test Score",
        "Übertragung auf generative KI",
        "Quality-Gate-Protokoll",
    ]:
        assert marker in source


@pytest.mark.django_db
def test_package_detail_shows_methodology_actions(
    client,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    client.force_login(coordinator)

    response = client.get(reverse("delivery:package_detail", kwargs={"pk": package.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Vorgehensmodell" in content
    assert "Vorgehensmodell herunterladen" in content
    assert reverse("delivery:methodology_reference") in content
    assert reverse("delivery:methodology_download") in content


@pytest.mark.django_db
def test_shared_section_requires_explicit_confirmation_role(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    with pytest.raises(ValidationError, match="ausdrücklich auswählen"):
        review_delivery_section(
            package=package,
            section_key="solution_direction",
            action="confirm",
            actor=coordinator,
        )


@pytest.mark.django_db
def test_authorized_substitutes_can_confirm_only_the_selected_role(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_business",
        actor=other_owner,
    )
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_technical",
        actor=coordinator,
    )

    review = package.section_reviews.get(section_key="solution_direction")
    assert review.business_confirmed_by == other_owner
    assert review.business_confirmation_role == "Berechtigte fachliche Stellvertretung"
    assert review.technical_confirmed_by == coordinator
    assert review.technical_confirmation_role == "Berechtigte technische Stellvertretung"
    assert review.review_status == DeliverySectionReview.ReviewStatus.CONFIRMED


@pytest.mark.django_db
def test_non_admin_cannot_confirm_both_roles(owner, other_owner, coordinator, business_unit):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_business",
        actor=coordinator,
    )

    with pytest.raises(ValidationError, match="Technischer Administrator"):
        review_delivery_section(
            package=package,
            section_key="solution_direction",
            action="confirm_technical",
            actor=coordinator,
            role_collapse_reason="Testdurchlauf.",
        )


@pytest.mark.django_db
def test_dual_owner_is_not_an_exception(owner, business_unit, coordinator):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_business",
        actor=owner,
    )

    with pytest.raises(ValidationError, match="Technischer Administrator"):
        review_delivery_section(
            package=package,
            section_key="solution_direction",
            action="confirm_technical",
            actor=owner,
            role_collapse_reason="Kleines Team.",
        )


@pytest.mark.django_db
def test_technical_admin_can_use_audited_same_person_exception(
    owner, other_owner, coordinator, technical_admin, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_business",
        actor=technical_admin,
    )

    with pytest.raises(ValidationError, match="Admin-Sonderbestätigung"):
        review_delivery_section(
            package=package,
            section_key="solution_direction",
            action="confirm_technical",
            actor=technical_admin,
        )

    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_technical",
        actor=technical_admin,
        role_collapse_reason="Vollständiger administrativer Test des Delivery-Flows.",
    )
    review = package.section_reviews.get(section_key="solution_direction")

    assert review.admin_override_confirmed is True
    assert review.has_role_collapse is True
    assert review.review_status == DeliverySectionReview.ReviewStatus.CONFIRMED
    assert review.business_confirmation_role == "Admin-Sonderbestätigung"
    assert review.technical_confirmation_role == "Admin-Sonderbestätigung"
    assert review.role_collapse_reason.startswith("Vollständiger administrativer Test")
    assert "INDEPENDENT_CONFIRMATION_MISSING" in {
        finding.code for finding in evaluate_delivery_readiness(package)
    }

    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_technical",
        actor=coordinator,
    )
    review.refresh_from_db()

    assert review.admin_override_confirmed is False
    assert review.has_role_collapse is False
    assert "INDEPENDENT_CONFIRMATION_MISSING" not in {
        finding.code for finding in evaluate_delivery_readiness(package)
    }


@pytest.mark.django_db
def test_delivery_page_labels_admin_override_by_confirmation_role(
    client, owner, other_owner, coordinator, technical_admin, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_business",
        actor=technical_admin,
    )
    review_delivery_section(
        package=package,
        section_key="solution_direction",
        action="confirm_technical",
        actor=technical_admin,
        role_collapse_reason="Administrativer Ende-zu-Ende-Test.",
    )
    client.force_login(technical_admin)

    response = client.get(package.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert f"Fachlich: {technical_admin} · Admin-Sonderbestätigung" in body
    assert f"Technisch: {technical_admin} · Admin-Sonderbestätigung" in body
    assert "Admin-Sonderbestätigung ohne Vier-Augen-Prinzip" in body
    assert "Administrativer Ende-zu-Ende-Test" in body


@pytest.mark.django_db
def test_delivery_uses_canonical_working_values_and_reports_field_level_source_change(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    assert package.problem_context == use_case.problem_statement
    assert package.problem_context.count(use_case.problem_statement) == 1
    assert package.solution_outline == use_case.intended_purpose

    use_case.expected_benefit = "Durchlaufzeit und Rückfragen reduzieren."
    use_case.save(update_fields=["expected_benefit", "updated_at"])
    findings = evaluate_delivery_readiness(package)

    messages = [
        finding.message for finding in findings if finding.code == "SOURCE_CHANGED_AFTER_SNAPSHOT"
    ]
    assert any("Ziel und erwartetes Ergebnis" in message for message in messages)
    assert any("Durchlaufzeit und Rückfragen reduzieren" in message for message in messages)


@pytest.mark.django_db
def test_delivery_package_snapshots_technical_owner_and_blocks_unresolved_source_change(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)

    assert package.technical_owner == other_owner
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    findings = evaluate_delivery_readiness(package)
    assert package.technical_owner == other_owner
    assert any(
        finding.code == "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED" and finding.severity == "blocker"
        for finding in findings
    )


@pytest.mark.django_db
def test_technical_owner_source_change_can_be_adopted_with_audit_decision(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    review_delivery_section(
        package=package,
        section_key="architecture_and_data",
        action="confirm_technical",
        actor=coordinator,
    )
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    decision = resolve_technical_owner_source_change(
        package=package,
        action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
        rationale="Die technische Verantwortung wurde organisatorisch neu zugeordnet.",
        actor=coordinator,
    )

    package.refresh_from_db()
    review = package.section_reviews.get(section_key="architecture_and_data")
    assert package.technical_owner == owner
    assert decision.old_value_id == str(other_owner.pk)
    assert decision.new_value_id == str(owner.pk)
    assert decision.decided_by == coordinator
    decision.rationale = "Nachträglich verändert"
    with pytest.raises(ValidationError, match="Quellenentscheidung ist unveränderlich"):
        decision.save()
    with pytest.raises(ValidationError, match="Quellenentscheidung ist unveränderlich"):
        decision.delete()
    assert review.review_status == DeliverySectionReview.ReviewStatus.NEEDS_REVIEW
    assert not any(
        finding.code == "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED"
        for finding in evaluate_delivery_readiness(package)
    )
    export = render_delivery_markdown(package)
    assert "Quellenentscheidungen" in export
    assert "Die technische Verantwortung wurde organisatorisch neu zugeordnet." in export


@pytest.mark.django_db
def test_technical_owner_source_change_can_be_kept_and_handover_version_is_immutable(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    decision = resolve_technical_owner_source_change(
        package=package,
        action=DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE,
        rationale="Die bestehende Package-Zuordnung bleibt für diese Version verantwortlich.",
        actor=coordinator,
    )
    package.refresh_from_db()
    assert package.technical_owner == other_owner
    assert decision.decision == DeliveryRoleSourceDecision.Decision.KEEP_PACKAGE
    assert not any(
        finding.code == "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED"
        for finding in evaluate_delivery_readiness(package)
    )

    package.status = package.Status.HANDED_OVER
    package.save(update_fields=["status", "updated_at"])
    use_case.technical_owner = coordinator
    use_case.save(update_fields=["technical_owner", "updated_at"])
    with pytest.raises(ValidationError, match="unveränderlich"):
        resolve_technical_owner_source_change(
            package=package,
            action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
            rationale="Darf nach Übergabe nicht mehr erfolgen.",
            actor=coordinator,
        )


@pytest.mark.django_db
def test_directly_involved_owners_can_resolve_technical_owner_source_change(
    owner, other_owner, coordinator, business_unit
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])

    decision = resolve_technical_owner_source_change(
        package=package,
        action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
        rationale="Der neue Technical Owner übernimmt die aktuelle Package-Version.",
        actor=owner,
    )

    package.refresh_from_db()
    assert package.technical_owner == owner
    assert decision.decided_by == owner


@pytest.mark.django_db
def test_unrelated_user_cannot_resolve_technical_owner_source_change(
    owner, other_owner, coordinator, business_unit, django_user_model
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])
    unrelated = django_user_model.objects.create_user(username="unrelated-role-decider")

    with pytest.raises(ValidationError, match="fehlt die Berechtigung"):
        resolve_technical_owner_source_change(
            package=package,
            action=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
            rationale="Unberechtigter Übernahmeversuch.",
            actor=unrelated,
        )


@pytest.mark.django_db
def test_technical_owner_source_change_is_visible_and_resolvable_in_delivery_ui(
    client,
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(use_case=use_case, actor=coordinator)
    use_case.technical_owner = owner
    use_case.save(update_fields=["technical_owner", "updated_at"])
    client.force_login(coordinator)

    response = client.get(reverse("delivery:package_detail", kwargs={"pk": package.pk}))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Offene Abweichung" in content
    assert str(other_owner) in content
    assert str(owner) in content
    assert (
        reverse("delivery:package_resolve_technical_owner_source", kwargs={"pk": package.pk})
        in content
    )

    response = client.post(
        reverse("delivery:package_resolve_technical_owner_source", kwargs={"pk": package.pk}),
        {
            "action": DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
            "rationale": "Die neue technische Verantwortung gilt für die aktuelle Package-Version.",
        },
    )

    assert response.status_code == 302
    package.refresh_from_db()
    assert package.technical_owner == owner
    assert package.role_source_decisions.filter(
        decision=DeliveryRoleSourceDecision.Decision.ADOPT_SOURCE,
        decided_by=coordinator,
    ).exists()
