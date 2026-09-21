from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import DecisionAssessment, UseCase
from ki_radar.use_cases.services import (
    confirm_conditional_decision,
    create_decision_assessment,
    submit_approval_decision,
)


def complete_intake_data(business_unit, business_owner, **overrides):
    data = {
        "title": "Wissenssuche verbessern",
        "business_unit": business_unit.pk,
        "business_owner": business_owner.pk,
        "problem_statement": (
            "Mitarbeitende benötigen zu viel Zeit, um verbindliche Informationen zu finden."
        ),
        "affected_process": "Interne Wissenssuche",
        "business_domain": BusinessDomain.CORPORATE_SERVICES,
        "business_capability": "Knowledge Management",
        "summary": "Eine Anfrage löst heute eine manuelle Suche aus.",
        "target_users": "Mitarbeitende im Kundenservice",
        "source_systems": "SharePoint und PDF-Richtlinien",
        "intended_users": "Mitarbeitende im Kundenservice",
        "intended_purpose": "Relevante Textstellen mit Quellenhinweis auffinden",
        "privacy_review_required": False,
        "security_review_required": False,
        "legal_review_required": False,
        "expected_benefit": "Suchzeit je Anfrage reduzieren",
        "metric_name": "Suchzeit je Anfrage",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_baseline": "20",
        "metric_target": "8",
        "metric_measurement_method": "Vierwöchige Stichprobe über 100 Anfragen",
        "data_sources": "Freigegebene Richtlinien und Arbeitsanweisungen",
        "solution_type": UseCase.SolutionType.ASSISTANT,
        "hosting_type": UseCase.HostingType.INTERNAL,
    }
    data.update(overrides)
    return data


def set_intake_session(client, business_unit, business_owner, **overrides):
    session = client.session
    session["use_case_intake"] = complete_intake_data(
        business_unit,
        business_owner,
        **overrides,
    )
    session.save()


def make_coordinator(username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


@pytest.fixture
def approver(db, business_unit):
    return make_coordinator("approver", business_unit)


@pytest.fixture
def second_approver(db, business_unit):
    return make_coordinator("second-approver", business_unit)


@pytest.fixture
def decision_ready_use_case(owner, business_unit):
    use_case = UseCase.objects.create(
        title="Rechnungsprüfung unterstützen",
        summary="Eingehende Rechnungen werden heute manuell geprüft.",
        problem_statement="Die manuelle Prüfung bindet Kapazität und verlängert die Durchlaufzeit.",
        business_unit=business_unit,
        affected_process="Rechnungsprüfung",
        target_users="Sachbearbeitung im Rechnungswesen",
        submitter=owner,
        business_owner=owner,
        intended_users="Sachbearbeitung",
        intended_purpose="Hinweise auf unvollständige Rechnungen geben",
        expected_benefit="Durchlaufzeit reduzieren",
        metric_name="Bearbeitungszeit je Rechnung",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Minuten",
        metric_baseline=Decimal("30"),
        metric_target=Decimal("15"),
        metric_measurement_method="Vierwöchige Stichprobe über alle Eingangsrechnungen",
        data_sources="Rechnungs-PDF und Bestelldaten",
        status=UseCase.Status.REVIEW,
        decision_status=UseCase.DecisionStatus.READY,
    )
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        basis_version="test-screening-v1",
        result=GovernanceAssessment.Result.NO_FLAGS,
    )
    return use_case


def assessment_data(**overrides):
    data = {
        "assessment_date": timezone.localdate(),
        "business_value": UseCase.Level.HIGH,
        "strategic_fit": UseCase.Level.MEDIUM,
        "technical_feasibility": UseCase.Level.HIGH,
        "data_readiness": UseCase.Level.MEDIUM,
        "risk_complexity": UseCase.Level.MEDIUM,
        "evidence_quality": DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        "evidence_recency": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_coverage": DecisionAssessment.ConfidenceFactor.SOLID,
        "independent_review": DecisionAssessment.ConfidenceFactor.SOLID,
        "assumptions_resolved": DecisionAssessment.ConfidenceFactor.SOLID,
        "evidence_url": "https://example.com/evidence",
        "rationale": "Messung und technische Vorprüfung stützen die Empfehlung.",
        "governance_precheck_completed": True,
        "recommendation": UseCase.DecisionStatus.APPROVED,
    }
    data.update(overrides)
    return data


def approval_data(**overrides):
    data = {
        "decision_status": UseCase.DecisionStatus.APPROVED,
        "rationale": "Nutzen, Evidenz und Risiken rechtfertigen die Freigabe.",
        "governance_confirmed": True,
        "conditions": "",
        "condition_owner": None,
        "condition_due_date": None,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_confidence_is_derived_from_evidence(coordinator, decision_ready_use_case):
    assessment = create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(),
    )

    assert assessment.confidence_level == UseCase.Level.HIGH
    assert assessment.confidence_label == "Hoch"


@pytest.mark.django_db
def test_assessor_cannot_approve_own_assessment(coordinator, decision_ready_use_case):
    create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(),
    )

    with pytest.raises(ValidationError, match="verschieden"):
        submit_approval_decision(
            use_case=decision_ready_use_case,
            actor=coordinator,
            data=approval_data(),
        )

    decision_ready_use_case.refresh_from_db()
    assert decision_ready_use_case.decision_status == UseCase.DecisionStatus.READY


@pytest.mark.django_db
def test_low_confidence_is_readiness_for_approval(
    coordinator,
    approver,
    decision_ready_use_case,
):
    create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(
            evidence_quality=DecisionAssessment.EvidenceQuality.ASSUMPTION,
            evidence_recency=DecisionAssessment.ConfidenceFactor.CRITICAL,
        ),
    )

    decision = submit_approval_decision(
        use_case=decision_ready_use_case,
        actor=approver,
        data=approval_data(),
    )

    assert decision.is_final


@pytest.mark.django_db
def test_open_required_governance_review_is_readiness_for_approval(
    coordinator,
    approver,
    decision_ready_use_case,
):
    decision_ready_use_case.privacy_review_required = True
    decision_ready_use_case.privacy_review_completed = False
    decision_ready_use_case.save()
    create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(),
    )

    decision = submit_approval_decision(
        use_case=decision_ready_use_case,
        actor=approver,
        data=approval_data(),
    )

    assert decision.is_final


@pytest.mark.django_db
def test_valid_independent_approval_changes_status(
    coordinator,
    approver,
    decision_ready_use_case,
):
    assessment = create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(),
    )

    decision = submit_approval_decision(
        use_case=decision_ready_use_case,
        actor=approver,
        data=approval_data(),
    )

    decision_ready_use_case.refresh_from_db()
    assert decision.assessment == assessment
    assert decision.is_final
    assert decision_ready_use_case.decision_status == UseCase.DecisionStatus.APPROVED


@pytest.mark.django_db
def test_conditional_approval_requires_second_independent_person(
    coordinator,
    approver,
    second_approver,
    owner,
    decision_ready_use_case,
):
    create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS),
    )
    decision = submit_approval_decision(
        use_case=decision_ready_use_case,
        actor=approver,
        data=approval_data(
            decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            conditions="Messkonzept vor Pilotstart fachlich bestätigen.",
            condition_owner=owner,
            condition_due_date=timezone.localdate() + timedelta(days=14),
            second_approval_assignee=second_approver,
        ),
    )

    decision_ready_use_case.refresh_from_db()
    assert decision.is_pending_second_approval
    assert decision_ready_use_case.decision_status == UseCase.DecisionStatus.READY

    with pytest.raises(PermissionDenied, match="Personentrennung"):
        confirm_conditional_decision(decision=decision, actor=approver)

    confirm_conditional_decision(decision=decision, actor=second_approver)
    decision_ready_use_case.refresh_from_db()
    decision.refresh_from_db()
    assert decision.second_approved_by == second_approver
    assert decision_ready_use_case.decision_status == (
        UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS
    )


@pytest.mark.django_db
def test_guided_intake_creates_assessment_ready_use_case(client, owner, business_unit):
    client.force_login(owner)
    response = client.post(
        reverse("use_cases:create"),
        {
            "title": "Wissenssuche verbessern",
            "business_unit": business_unit.pk,
            "business_owner": owner.pk,
            "problem_statement": (
                "Mitarbeitende benötigen zu viel Zeit, um verbindliche Informationen in "
                "mehreren Richtliniendokumenten zu finden."
            ),
        },
    )
    assert response.status_code == 302

    response = client.post(
        reverse("use_cases:intake_step", args=[2]),
        {
            "business_domain": BusinessDomain.CORPORATE_SERVICES,
            "business_capability": "Knowledge Management",
            "affected_process": "Interne Wissenssuche",
            "summary": "Eine Anfrage löst heute eine manuelle Suche in mehreren Ablagen aus.",
            "target_users": "Mitarbeitende im Kundenservice",
            "source_systems": "SharePoint und PDF-Richtlinien",
        },
    )
    assert response.status_code == 302

    client.post(
        reverse("use_cases:intake_step", args=[3]),
        {
            "intended_users": "Mitarbeitende im Kundenservice",
            "intended_purpose": "Relevante Textstellen mit Quellenhinweis auffinden",
        },
    )
    client.post(
        reverse("use_cases:intake_step", args=[4]),
        {
            "expected_benefit": "Suchzeit je Anfrage reduzieren",
            "metric_name": "Suchzeit je Anfrage",
            "metric_type": UseCase.MetricType.DURATION,
            "metric_direction": UseCase.MetricDirection.LOWER,
            "metric_unit": "Minuten",
            "metric_baseline": "20",
            "metric_target": "8",
            "metric_measurement_method": "Vierwöchige Stichprobe über 100 Anfragen",
        },
    )
    client.post(
        reverse("use_cases:intake_step", args=[5]),
        {
            "data_sources": "Freigegebene Richtlinien und Arbeitsanweisungen",
            "solution_type": UseCase.SolutionType.ASSISTANT,
            "hosting_type": UseCase.HostingType.INTERNAL,
        },
    )
    response = client.post(reverse("use_cases:intake_step", args=[6]))

    use_case = UseCase.objects.get(title="Wissenssuche verbessern")
    assert response.status_code == 302
    assert use_case.business_owner == owner
    assert use_case.decision_status == UseCase.DecisionStatus.READY
    assert use_case.metric_baseline == Decimal("20")


@pytest.mark.django_db
@pytest.mark.parametrize("step", range(1, 7))
def test_intake_uses_validated_progress_class(client, owner, business_unit, step):
    client.force_login(owner)
    if step == 6:
        set_intake_session(client, business_unit, owner)

    response = client.get(reverse("use_cases:intake_step", args=[step]))
    content = response.content.decode()

    assert response.status_code == 200
    assert f'class="progress-bar wizard-progress-{step}"' in content
    assert f'aria-valuenow="{step}"' in content
    assert 'aria-valuemin="1"' in content
    assert 'aria-valuemax="6"' in content


@pytest.mark.django_db
def test_intake_progress_rejects_arbitrary_step_class(client, owner):
    client.force_login(owner)

    response = client.get(reverse("use_cases:intake_step", args=[999]))

    assert response.status_code == 302
    assert "wizard-progress-999" not in response.content.decode()


def test_intake_template_progress_has_no_inline_style():
    template = Path("templates/use_cases/intake_wizard.html").read_text(encoding="utf-8")

    assert '<div class="progress-bar {{ progress_class }}"></div>' in template
    assert "style=" not in template


def test_intake_progress_classes_define_all_six_widths():
    stylesheet = Path("static/css/app.css").read_text(encoding="utf-8")
    expected_widths = ["16.6667%", "33.3333%", "50%", "66.6667%", "83.3333%", "100%"]

    for step, width in enumerate(expected_widths, start=1):
        assert f".wizard-progress-{step} {{ width: {width}; }}" in stylesheet


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("privacy", "security", "legal", "required_count"),
    [
        (False, False, False, 0),
        (True, False, False, 1),
        (True, True, False, 2),
        (True, True, True, 3),
    ],
)
def test_intake_precheck_lists_required_reviews_separately(
    client,
    owner,
    business_unit,
    privacy,
    security,
    legal,
    required_count,
):
    client.force_login(owner)
    set_intake_session(
        client,
        business_unit,
        owner,
        privacy_review_required=privacy,
        security_review_required=security,
        legal_review_required=legal,
    )

    response = client.get(reverse("use_cases:intake_step", args=[6]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "<dt>Datenschutz</dt>" in content
    assert "<dt>Informationssicherheit</dt>" in content
    assert "<dt>Recht</dt>" in content
    assert content.count("<dd>Erforderlich</dd>") == required_count
    assert content.count("<dd>Nicht erforderlich</dd>") == 3 - required_count


@pytest.mark.django_db
def test_detail_page_exposes_decision_layer(
    client,
    coordinator,
    decision_ready_use_case,
):
    create_decision_assessment(
        use_case=decision_ready_use_case,
        actor=coordinator,
        data=assessment_data(),
    )
    client.force_login(coordinator)

    response = client.get(reverse("use_cases:detail", args=[decision_ready_use_case.pk]))

    assert response.status_code == 200
    assert "Belastbare Freigabeentscheidung" in response.content.decode()
    assert "Confidence" in response.content.decode()
