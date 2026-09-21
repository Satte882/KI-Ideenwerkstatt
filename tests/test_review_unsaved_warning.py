import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Review-Warnung testen",
        problem_statement="Die Lifecycle-Entscheidung muss nachvollziehbar dokumentiert werden.",
        business_unit=business_unit,
        affected_process="Lifecycle-Review",
        business_owner=owner,
        expected_benefit="Keine unbemerkten Verluste auditrelevanter Eingaben.",
    )


def _review_payload(*, rationale: str, new_status: str) -> dict[str, str]:
    return {
        "review_date": timezone.localdate().isoformat(),
        "decision": Review.Decision.START_REVIEW,
        "new_status": new_status,
        "rationale": rationale,
        "open_actions": "",
        "action_owner": "",
        "action_due_date": "",
        "next_review_date": "",
    }


@pytest.mark.django_db
def test_review_get_warns_only_after_form_changes(client, coordinator, use_case):
    client.force_login(coordinator)

    response = client.get(reverse("reviews:create", args=[use_case.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'id="review-form"' in content
    assert 'data-initially-dirty="false"' in content
    assert 'src="/static/js/review-form-dirty-guard.js"' in content
    assert "Bei ungespeicherten Änderungen warnt der Browser" in content


@pytest.mark.django_db
def test_invalid_review_post_keeps_rationale_and_remains_marked_unsaved(
    client,
    coordinator,
    use_case,
):
    client.force_login(coordinator)
    rationale = "Diese Begründung darf nach einem Validierungsfehler nicht verschwinden."

    response = client.post(
        reverse("reviews:create", args=[use_case.pk]),
        _review_payload(rationale=rationale, new_status=UseCase.Status.IDEA),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert rationale in content
    assert 'data-initially-dirty="true"' in content
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_successful_review_persists_rationale_and_shows_it_in_history(
    client,
    coordinator,
    use_case,
):
    client.force_login(coordinator)
    rationale = "Die Prüfung wird mit dokumentierter Begründung gestartet."

    response = client.post(
        reverse("reviews:create", args=[use_case.pk]),
        _review_payload(rationale=rationale, new_status=UseCase.Status.REVIEW),
        follow=True,
    )

    use_case.refresh_from_db()
    review = Review.objects.get(use_case=use_case)
    assert response.status_code == 200
    assert use_case.status == UseCase.Status.REVIEW
    assert review.rationale == rationale
    assert rationale in response.content.decode()
