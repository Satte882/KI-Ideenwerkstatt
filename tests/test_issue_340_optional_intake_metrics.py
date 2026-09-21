import pytest
from django.urls import reverse

from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.use_cases.decision_forms import DecisionAssessmentForm
from ki_radar.use_cases.intake import BenefitStepForm
from ki_radar.use_cases.intake_views import SESSION_KEY
from ki_radar.use_cases.models import DecisionAssessment, UseCase
from ki_radar.use_cases.services import approval_check, check_pilot_start


def benefit_step_data(**overrides):
    data = {
        "expected_benefit": "Durchlaufzeit und manuelle Prüfarbeit reduzieren",
        "metric_name": "Durchlaufzeit bis zur freigabefähigen Fassung",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_measurement_method": (
            "Im Pilot den Zeitraum zwischen Start der Bearbeitung und freigabefähiger Fassung "
            "messen."
        ),
    }
    data.update(overrides)
    return data


def make_assessment(use_case, owner):
    return DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=owner,
        business_value=UseCase.Level.MEDIUM,
        strategic_fit=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.ASSUMPTION,
        evidence_recency=DecisionAssessment.ConfidenceFactor.LIMITED,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.LIMITED,
        independent_review=DecisionAssessment.ConfidenceFactor.LIMITED,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.LIMITED,
        evidence_url="https://example.com/demo-evidence",
        rationale="Frühe Bewertung auf Hypothesenbasis.",
        recommendation=UseCase.DecisionStatus.DEFERRED,
    )


def test_benefit_step_allows_unknown_baseline_and_target():
    form = BenefitStepForm(data=benefit_step_data())

    assert form.fields["metric_baseline"].required is False
    assert form.fields["metric_target"].required is False
    assert form.is_valid(), form.errors
    assert form.cleaned_data["metric_baseline"] is None
    assert form.cleaned_data["metric_target"] is None


def test_assumption_assessment_does_not_require_a_fake_evidence_link():
    data = {
        "assessment_date": "2026-08-23",
        "business_value": UseCase.Level.MEDIUM,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.MEDIUM,
        "data_readiness": UseCase.Level.LOW,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.ASSUMPTION,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.CRITICAL,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.CRITICAL,
        "independent_review": DecisionAssessment.ConfidenceFactor.CRITICAL,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.CRITICAL,
        "evidence_url": "",
        "rationale": "Frühe Hypothese ohne externen Nachweis.",
        "recommendation": UseCase.DecisionStatus.DEFERRED,
    }

    form = DecisionAssessmentForm(data=data)

    assert form.fields["evidence_url"].required is False
    assert form.is_valid(), form.errors


def test_stronger_assessment_still_requires_evidence_link():
    data = {
        "assessment_date": "2026-08-23",
        "business_value": UseCase.Level.MEDIUM,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.MEDIUM,
        "data_readiness": UseCase.Level.MEDIUM,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.EXPERT_OPINION,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.LIMITED,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.LIMITED,
        "independent_review": DecisionAssessment.ConfidenceFactor.LIMITED,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.LIMITED,
        "evidence_url": "",
        "rationale": "Fachliche Einschätzung.",
        "recommendation": UseCase.DecisionStatus.DEFERRED,
    }

    form = DecisionAssessmentForm(data=data)

    assert form.fields["evidence_url"].required is True
    assert not form.is_valid()
    assert "evidence_url" in form.errors


def test_benefit_step_validates_present_percentage_value_even_if_other_value_is_unknown():
    form = BenefitStepForm(
        data=benefit_step_data(
            metric_type=UseCase.MetricType.PERCENT,
            metric_unit="%",
            metric_baseline="120",
        )
    )

    assert not form.is_valid()
    assert "metric_baseline" in form.errors
    assert "metric_target" not in form.errors


@pytest.mark.django_db
def test_guided_intake_persists_unknown_metrics_as_null(client, owner, business_unit):
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:create"),
        {
            "title": "Reiseausschreibung unterstützen",
            "business_unit": business_unit.pk,
            "business_owner": owner.pk,
            "problem_statement": (
                "Mitarbeitende führen Informationen aus mehreren Quellen manuell zusammen und "
                "prüfen sie wiederholt auf Vollständigkeit und Konsistenz."
            ),
        },
    )
    assert response.status_code == 302

    response = client.post(
        reverse("use_cases:intake_step", args=[2]),
        {
            "business_domain": BusinessDomain.PRODUCTION,
            "business_capability": "Reiseprodukt- und Angebotsmanagement",
            "affected_process": "Reiseausschreibung erstellen, prüfen und abstimmen",
            "summary": "Informationen werden zusammengeführt, geprüft und abgestimmt.",
            "target_users": "Touristik und Produktmanagement",
            "source_systems": "Produktdaten, Dokumentenablage und Kommunikation",
        },
    )
    assert response.status_code == 302

    response = client.post(
        reverse("use_cases:intake_step", args=[3]),
        {
            "intended_users": "Touristik und Produktmanagement",
            "intended_purpose": "Entwurf und Qualitätsprüfung fachlich unterstützen",
        },
    )
    assert response.status_code == 302

    response = client.post(
        reverse("use_cases:intake_step", args=[4]),
        benefit_step_data(),
    )
    assert response.status_code == 302
    stored = client.session[SESSION_KEY]
    assert "metric_baseline" in stored
    assert "metric_target" in stored
    assert stored["metric_baseline"] is None
    assert stored["metric_target"] is None

    response = client.post(
        reverse("use_cases:intake_step", args=[5]),
        {
            "data_sources": "Produktdaten, Leistungsinformationen und Qualitätsvorgaben",
            "solution_type": UseCase.SolutionType.ASSISTANT,
            "hosting_type": UseCase.HostingType.UNKNOWN,
        },
    )
    assert response.status_code == 302

    response = client.post(reverse("use_cases:intake_step", args=[6]))

    use_case = UseCase.objects.get(title="Reiseausschreibung unterstützen")
    assert response.status_code == 302
    assert use_case.metric_baseline is None
    assert use_case.metric_target is None
    assert use_case.decision_status == UseCase.DecisionStatus.READY
    assert use_case.metric_result_label == "Metrik definiert · Baseline und Ziel offen"


@pytest.mark.django_db
def test_positive_approval_shows_baseline_and_target_as_readiness(owner, business_unit):
    use_case = UseCase.objects.create(
        title="Früher Use Case",
        problem_statement="Ein relevantes Problem ist beschrieben.",
        business_unit=business_unit,
        affected_process="Fachprozess",
        business_owner=owner,
        expected_benefit="Bearbeitungszeit reduzieren",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_measurement_method="Im Pilot über vier Wochen messen",
        data_sources="Fachdaten",
    )
    make_assessment(use_case, owner)

    positive = approval_check(
        use_case=use_case,
        target_status=UseCase.DecisionStatus.APPROVED,
        governance_confirmed=True,
    )
    negative = approval_check(
        use_case=use_case,
        target_status=UseCase.DecisionStatus.DEFERRED,
    )

    assert "Readiness offen: Baseline-Wert" in positive.warnings
    assert "Readiness offen: Zielwert" in positive.warnings
    assert negative.blockers == []


@pytest.mark.django_db
def test_pilot_gate_keeps_metric_requirements_as_readiness(owner, business_unit):
    use_case = UseCase.objects.create(
        title="Pilot noch nicht messbereit",
        problem_statement="Ein relevantes Problem ist beschrieben.",
        business_unit=business_unit,
        affected_process="Fachprozess",
        business_owner=owner,
        expected_benefit="Bearbeitungszeit reduzieren",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_measurement_method="Im Pilot über vier Wochen messen",
        data_sources="Fachdaten",
        status=UseCase.Status.REVIEW,
    )

    check = check_pilot_start(use_case)

    assert "Readiness offen: Baseline-Wert" in check.warnings
    assert "Readiness offen: Zielwert" in check.warnings
