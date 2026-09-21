import pytest
from django import forms
from django.urls import reverse
from django.utils import timezone

from ki_radar.governance.forms import GovernanceAssessmentForm
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.governance_status import build_governance_statuses
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def use_case(owner, business_unit):
    return UseCase.objects.create(
        title="KI",
        problem_statement="Problem",
        business_unit=business_unit,
        affected_process="Prozess",
        business_owner=owner,
        expected_benefit="Nutzen",
    )


@pytest.mark.django_db
def test_governance_updates_required_flags_and_creates_status_artifacts(
    client, coordinator, use_case
):
    client.force_login(coordinator)
    response = client.post(
        reverse("governance:create", args=[use_case.pk]),
        {
            "assessment_date": timezone.localdate(),
            "basis_version": "2026-01",
            "personal_data": "on",
            "privacy_review_required": "on",
            "privacy_review_rationale": "Personenbezogene Daten werden verarbeitet.",
            "security_review_rationale": "Keine zusätzliche Security-Prüfung erforderlich.",
            "legal_review_rationale": "Keine rechtliche Personenwirkung.",
            "result": GovernanceAssessment.Result.PRIVACY,
            "rationale": "Personenbezogene Daten",
        },
    )
    assert response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.privacy_review_required is True
    statuses = {
        artifact.review_type: artifact.status
        for artifact in GovernanceReview.objects.filter(use_case=use_case)
    }
    assert statuses == {
        GovernanceReview.ReviewType.PRIVACY: GovernanceReview.Status.OPEN,
        GovernanceReview.ReviewType.SECURITY: GovernanceReview.Status.NOT_RELEVANT,
        GovernanceReview.ReviewType.LEGAL: GovernanceReview.Status.NOT_RELEVANT,
    }


@pytest.mark.django_db
def test_governance_form_uses_german_labels():
    form = GovernanceAssessmentForm()

    assert form.fields["assessment_date"].label == "Screening-Datum"
    assert form.fields["basis_version"].label == "Prüfgrundlage / Version"
    assert form.fields["personal_data"].label == "Personenbezogene Daten"
    assert form.fields["result"].label == "Screening-Ergebnis"
    assert form.fields["privacy_review_rationale"].label == ("Begründung Datenschutz-Prüfbedarf")


def _assessment(use_case, reviewer, **requirements):
    return GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=reviewer,
        basis_version="2026-07",
        result=GovernanceAssessment.Result.NO_FLAGS,
        rationale="Aktuelles Screening",
        **requirements,
    )


def _edit_payload(use_case, **overrides):
    form = UseCaseForm(instance=use_case)
    payload = {}
    for name, field in form.fields.items():
        value = form.initial.get(name)
        if isinstance(field, forms.BooleanField):
            if value:
                payload[name] = "on"
        elif value is not None:
            payload[name] = getattr(value, "pk", value)
    payload.update(
        {
            "business_domain": "other",
            "business_capability": "Allgemeine Prozessunterstützung",
            "process_area": use_case.affected_process,
            **overrides,
        }
    )
    return payload


@pytest.mark.django_db
def test_governance_status_distinguishes_all_four_states(coordinator, use_case):
    statuses = {status.kind.key: status for status in build_governance_statuses(use_case)}
    assert {status.state for status in statuses.values()} == {"not_assessed"}

    _assessment(
        use_case,
        coordinator,
        security_review_required=True,
        legal_review_required=True,
    )
    use_case.security_review_required = True
    use_case.legal_review_required = True
    use_case.legal_review_completed = True
    use_case.save()

    statuses = {status.kind.key: status for status in build_governance_statuses(use_case)}
    assert statuses["privacy"].state == "not_required"
    assert statuses["security"].state == "open"
    assert statuses["legal"].state == "completed"
    assert statuses["privacy"].label == "Nicht relevant"
    assert statuses["privacy"].actor == coordinator.get_display_name()
    assert statuses["legal"].actor == "System"


@pytest.mark.django_db
def test_general_form_never_exposes_governance_completion_checkboxes(coordinator, use_case):
    _assessment(use_case, coordinator, privacy_review_required=True)
    use_case.privacy_review_required = True
    use_case.save(update_fields=["privacy_review_required", "updated_at"])

    form = UseCaseForm(instance=use_case, current_user=coordinator)

    assert "privacy_review_completed" not in form.fields
    assert "security_review_completed" not in form.fields
    assert "legal_review_completed" not in form.fields


@pytest.mark.django_db
def test_manipulated_post_cannot_complete_review_from_master_data(client, owner, use_case):
    _assessment(use_case, owner, privacy_review_required=True)
    use_case.privacy_review_required = True
    use_case.save(update_fields=["privacy_review_required", "updated_at"])
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:edit", args=[use_case.pk]),
        _edit_payload(use_case, privacy_review_completed="on"),
    )

    assert response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.privacy_review_completed is False


@pytest.mark.django_db
def test_formal_review_completion_and_new_screening_are_historized(client, coordinator, use_case):
    client.force_login(coordinator)
    screening_response = client.post(
        reverse("governance:create", args=[use_case.pk]),
        {
            "assessment_date": timezone.localdate(),
            "basis_version": "2026-07",
            "privacy_review_required": "on",
            "privacy_review_rationale": "Personenbezug erfordert formale Prüfung.",
            "security_review_rationale": "Keine zusätzliche Security-Prüfung.",
            "legal_review_rationale": "Keine rechtliche Personenwirkung.",
            "result": GovernanceAssessment.Result.PRIVACY,
            "rationale": "Erstes Screening",
        },
    )
    assert screening_response.status_code == 302

    review_response = client.post(
        reverse(
            "governance:review",
            kwargs={"use_case_id": use_case.pk, "review_type": "privacy"},
        ),
        {
            "reviewed_at": timezone.localdate(),
            "responsible_role": "Datenschutz",
            "result": GovernanceReview.Result.PASSED,
            "rationale": "Datenschutzanforderungen wurden geprüft.",
            "risks": "Keine verbleibenden hohen Risiken.",
            "measures": "Zugriffsbeschränkung umgesetzt.",
            "conditions": "",
            "evidence_url": "https://example.invalid/privacy-proof",
        },
    )
    assert review_response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.privacy_review_completed is True
    completed = use_case.governance_reviews.filter(
        review_type=GovernanceReview.ReviewType.PRIVACY,
        status=GovernanceReview.Status.COMPLETED,
    ).get()
    assert completed.history.count() == 1
    assert completed.history.first().history_user == coordinator

    reopened_response = client.post(
        reverse("governance:create", args=[use_case.pk]),
        {
            "assessment_date": timezone.localdate(),
            "basis_version": "2026-08",
            "privacy_review_required": "on",
            "privacy_review_rationale": "Neue Datenquelle erfordert erneute Prüfung.",
            "security_review_rationale": "Keine neue Security-Wirkung.",
            "legal_review_rationale": "Keine neue Rechtswirkung.",
            "result": GovernanceAssessment.Result.PRIVACY,
            "rationale": "Neues Screening wegen Datenquellenänderung",
        },
    )
    assert reopened_response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.privacy_review_completed is False
    status = build_governance_statuses(use_case)[0]
    assert status.state == "open"
    assert status.actor == coordinator.get_display_name()
    assert status.changed_at_has_time is True


@pytest.mark.django_db
def test_new_screening_normalizes_obsolete_completion_atomically(client, coordinator, use_case):
    _assessment(use_case, coordinator, privacy_review_required=True)
    use_case.privacy_review_required = True
    use_case.privacy_review_completed = True
    use_case.save()
    client.force_login(coordinator)

    response = client.post(
        reverse("governance:create", args=[use_case.pk]),
        {
            "assessment_date": timezone.localdate(),
            "basis_version": "2026-08",
            "privacy_review_rationale": "Personenbezug entfällt vollständig.",
            "security_review_rationale": "Keine sicherheitskritische Änderung.",
            "legal_review_rationale": "Keine rechtliche Wirkung.",
            "result": GovernanceAssessment.Result.NO_FLAGS,
            "rationale": "Keine Fachprüfung mehr erforderlich",
        },
    )

    assert response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.privacy_review_required is False
    assert use_case.privacy_review_completed is False
    assert use_case.governance_assessments.count() == 2
    status = build_governance_statuses(use_case)[0]
    assert status.state == "not_required"
    assert status.label == "Nicht relevant"


@pytest.mark.django_db
def test_detail_shows_semantic_status_reviewer_and_artifact_link(
    client, owner, coordinator, use_case
):
    _assessment(use_case, coordinator, privacy_review_required=True)
    use_case.privacy_review_required = True
    use_case.save(update_fields=["privacy_review_required", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("use_cases:detail", args=[use_case.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Nicht relevant" in content
    assert "Offen" in content
    assert "Prüfartefakt öffnen" in content
    assert coordinator.get_display_name() in content
    assert timezone.localdate().strftime("%d.%m.%Y") in content


@pytest.mark.django_db
def test_legacy_completion_without_user_has_honest_fallback(coordinator, use_case):
    _assessment(use_case, coordinator, legal_review_required=True)
    use_case.legal_review_required = True
    use_case.legal_review_completed = True
    use_case.save()

    status = build_governance_statuses(use_case)[2]

    assert status.state == "completed"
    assert status.actor == "System"
    assert "Legacy" in status.attribution_note
