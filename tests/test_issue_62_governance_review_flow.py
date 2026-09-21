import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import User
from ki_radar.core.demo_architecture_data import INVOICE_USE_CASE_KEY
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.governance.services import create_screening_review_artifacts
from ki_radar.use_cases.blockers import build_blocker_details
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_demo_seed(settings):
    settings.DEBUG = True


@pytest.fixture
def coordinator(db):
    call_command("seed_demo_data", demo_user_password="Issue-62-Governance-Demo-2026!")
    return User.objects.get(username="demo_ki_koordinator")


@pytest.fixture
def use_case(coordinator):
    use_case = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
    use_case.governance_reviews.all().delete()
    use_case.governance_assessments.all().delete()
    use_case.privacy_review_required = False
    use_case.privacy_review_completed = False
    use_case.security_review_required = False
    use_case.security_review_completed = False
    use_case.legal_review_required = False
    use_case.legal_review_completed = False
    use_case.save()
    return use_case


def _screening(use_case, coordinator, **requirements):
    defaults = {
        "privacy_review_required": False,
        "security_review_required": False,
        "legal_review_required": False,
    }
    defaults.update(requirements)
    assessment = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Governance-Leitlinie 1.0",
        result=GovernanceAssessment.Result.CLARIFICATION,
        rationale="Screening für den geführten Prüfpfad.",
        privacy_review_rationale="Datenschutz-Prüfbedarf wurde bewertet.",
        security_review_rationale="Security-Prüfbedarf wurde bewertet.",
        legal_review_rationale="Rechts-Prüfbedarf wurde bewertet.",
        **defaults,
    )
    for field_name, value in defaults.items():
        setattr(use_case, field_name, value)
    use_case.save()
    create_screening_review_artifacts(assessment=assessment, actor=coordinator)
    return assessment


@pytest.mark.django_db
def test_review_redirects_to_screening_when_screening_is_missing(client, coordinator, use_case):
    client.force_login(coordinator)
    review_url = reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
    )

    response = client.get(review_url)

    assert response.status_code == 302
    assert response.url == reverse("governance:create", kwargs={"use_case_id": use_case.pk})


@pytest.mark.django_db
def test_required_review_uses_dedicated_workspace(client, coordinator, use_case):
    _screening(use_case, coordinator, privacy_review_required=True)
    client.force_login(coordinator)

    response = client.get(
        reverse(
            "governance:review",
            kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Datenschutzprüfung" in content
    assert "Formale Prüfung abschließen" in content
    assert "Prüfergebnis" in content
    assert "Festgestellte Risiken" in content
    assert "Maßnahmen" in content
    assert "Auflagen" in content
    assert "Nachweislink" in content
    assert "Screening, keine formale Fachprüfung" not in content
    assert "Das Governance-Screening begründet nur den Prüfbedarf" in content
    assert "Stammdaten bearbeiten" not in content


@pytest.mark.django_db
def test_not_relevant_review_is_a_reasoned_artifact(client, coordinator, use_case):
    screening = _screening(use_case, coordinator)
    client.force_login(coordinator)

    response = client.get(
        reverse(
            "governance:review",
            kwargs={"use_case_id": use_case.pk, "review_type": "legal"},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Bewusste Nicht-Relevanz" in content
    assert "Nicht relevant" in content
    assert "Formale Prüfung abschließen" not in content
    review = GovernanceReview.objects.get(
        use_case=use_case,
        screening=screening,
        review_type=GovernanceReview.ReviewType.LEGAL,
    )
    assert review.status == GovernanceReview.Status.NOT_RELEVANT
    assert review.rationale == "Rechts-Prüfbedarf wurde bewertet."
    assert review.reviewer == coordinator


@pytest.mark.django_db
def test_completed_review_creates_artifact_and_opens_next_required_review(
    client, coordinator, use_case
):
    screening = _screening(
        use_case,
        coordinator,
        privacy_review_required=True,
        security_review_required=True,
    )
    client.force_login(coordinator)
    privacy_url = reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
    )

    response = client.post(
        privacy_url,
        {
            "reviewed_at": timezone.localdate().isoformat(),
            "responsible_role": "Datenschutz",
            "result": GovernanceReview.Result.PASSED,
            "rationale": "Datenschutzanforderungen sind geprüft und erfüllt.",
            "risks": "Restrisiko dokumentiert.",
            "measures": "Berechtigungskonzept umgesetzt.",
            "conditions": "",
            "evidence_url": "https://example.invalid/governance/privacy-proof",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": "security"},
    )
    use_case.refresh_from_db()
    review = GovernanceReview.objects.get(
        use_case=use_case,
        screening=screening,
        review_type=GovernanceReview.ReviewType.PRIVACY,
        status=GovernanceReview.Status.COMPLETED,
    )
    assert review.reviewer == coordinator
    assert review.is_completed is True
    assert review.created_at is not None
    assert review.history.count() == 1
    assert use_case.privacy_review_completed is True


@pytest.mark.django_db
def test_completed_review_allows_evidence_to_follow_as_readiness(client, coordinator, use_case):
    screening = _screening(use_case, coordinator, privacy_review_required=True)
    client.force_login(coordinator)

    response = client.post(
        reverse(
            "governance:review",
            kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
        ),
        {
            "reviewed_at": timezone.localdate().isoformat(),
            "responsible_role": "Datenschutz",
            "result": GovernanceReview.Result.PASSED,
            "rationale": "Prüfung abgeschlossen.",
            "risks": "Keine hohen Restrisiken.",
            "measures": "Kontrollen dokumentiert.",
            "conditions": "",
            "evidence_url": "",
        },
    )

    assert response.status_code == 302
    assert GovernanceReview.objects.filter(
        screening=screening,
        status=GovernanceReview.Status.COMPLETED,
        result=GovernanceReview.Result.PASSED,
        evidence_url="",
    ).exists()


@pytest.mark.django_db
def test_conditional_requires_conditions_but_failed_details_are_readiness(
    client, coordinator, use_case
):
    screening = _screening(use_case, coordinator, security_review_required=True)
    client.force_login(coordinator)
    url = reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": "security"},
    )

    conditional = client.post(
        url,
        {
            "reviewed_at": timezone.localdate().isoformat(),
            "responsible_role": "Informationssicherheit",
            "result": GovernanceReview.Result.PASSED_WITH_CONDITIONS,
            "rationale": "Nur unter Auflagen vertretbar.",
            "risks": "Externe Schnittstelle.",
            "measures": "Monitoring vorgesehen.",
            "conditions": "",
            "evidence_url": "https://example.invalid/security-proof",
        },
    )
    assert conditional.status_code == 200
    assert "Auflagen müssen strukturiert dokumentiert werden" in conditional.content.decode()

    failed = client.post(
        url,
        {
            "reviewed_at": timezone.localdate().isoformat(),
            "responsible_role": "Informationssicherheit",
            "result": GovernanceReview.Result.FAILED,
            "rationale": "Kontrollniveau nicht ausreichend.",
            "risks": "",
            "measures": "",
            "conditions": "",
            "evidence_url": "https://example.invalid/security-failed",
        },
    )
    assert failed.status_code == 302
    assert GovernanceReview.objects.filter(
        screening=screening,
        status=GovernanceReview.Status.COMPLETED,
        result=GovernanceReview.Result.FAILED,
        risks="",
        measures="",
    ).exists()


@pytest.mark.django_db
def test_governance_blockers_link_to_screening_and_review_workspaces(use_case):
    details = build_blocker_details(
        use_case,
        ["Governance-Vorprüfung", "Datenschutzprüfung"],
    )

    assert details[0].target_url == reverse(
        "governance:create", kwargs={"use_case_id": use_case.pk}
    )
    assert details[1].target_url == reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
    )
