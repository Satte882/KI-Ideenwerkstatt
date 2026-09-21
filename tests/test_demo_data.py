from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.core.demo_data import (
    DEMO_PREFIX,
    demo_business_unit_names,
    demo_use_case_titles,
    demo_usernames,
)
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_debug_for_demo_seed(settings):
    settings.DEBUG = True


@pytest.mark.django_db
def test_seed_demo_data_creates_complete_dataset():
    call_command("seed_demo_data")

    demo_use_cases = UseCase.objects.filter(title__in=demo_use_case_titles())

    assert BusinessUnit.objects.filter(name__in=demo_business_unit_names()).count() == 3
    assert User.objects.filter(username__in=demo_usernames()).count() == 4
    assert demo_use_cases.count() == 10
    assert GovernanceAssessment.objects.filter(use_case__in=demo_use_cases).count() >= 6
    assert Review.objects.filter(use_case__in=demo_use_cases).count() >= 6
    assert demo_use_cases.filter(status=UseCase.Status.PILOT, realized_result__gt="").exists()
    assert demo_use_cases.filter(status=UseCase.Status.OPERATION).exists()
    assert demo_use_cases.filter(
        status=UseCase.Status.ENDED,
        ending_reason__gt="",
        lessons_learned__gt="",
        data_and_access_handling__gt="",
    ).exists()
    assert demo_use_cases.filter(
        status__in=[
            UseCase.Status.IDEA,
            UseCase.Status.REVIEW,
            UseCase.Status.PILOT,
            UseCase.Status.OPERATION,
        ],
        governance_assessments__isnull=True,
    ).exists()


@pytest.mark.django_db
def test_seed_demo_data_is_idempotent_and_restores_changed_fields():
    call_command("seed_demo_data")
    counts = {
        "units": BusinessUnit.objects.filter(name__in=demo_business_unit_names()).count(),
        "users": User.objects.filter(username__in=demo_usernames()).count(),
        "use_cases": UseCase.objects.filter(title__in=demo_use_case_titles()).count(),
        "governance": GovernanceAssessment.objects.filter(
            use_case__title__in=demo_use_case_titles()
        ).count(),
        "reviews": Review.objects.filter(use_case__title__in=demo_use_case_titles()).count(),
    }

    use_case = UseCase.objects.get(title=f"{DEMO_PREFIX} Interner Wissensassistent")
    use_case.priority = UseCase.Priority.LOW
    use_case.save(update_fields=["priority"])

    call_command("seed_demo_data")

    assert (
        BusinessUnit.objects.filter(name__in=demo_business_unit_names()).count() == counts["units"]
    )
    assert User.objects.filter(username__in=demo_usernames()).count() == counts["users"]
    assert UseCase.objects.filter(title__in=demo_use_case_titles()).count() == counts["use_cases"]
    assert (
        GovernanceAssessment.objects.filter(use_case__title__in=demo_use_case_titles()).count()
        == counts["governance"]
    )
    assert (
        Review.objects.filter(use_case__title__in=demo_use_case_titles()).count()
        == counts["reviews"]
    )
    use_case.refresh_from_db()
    assert use_case.priority == UseCase.Priority.HIGH


@pytest.mark.django_db
def test_seed_demo_data_does_not_change_existing_superuser():
    superuser = User.objects.create_superuser(
        username="admin",
        email="admin@example.invalid",
        password="Existing-Superuser-2026!",
        first_name="Existing",
    )
    original_password = superuser.password

    call_command("seed_demo_data")

    superuser.refresh_from_db()
    assert superuser.is_superuser is True
    assert superuser.password == original_password
    assert superuser.first_name == "Existing"


@pytest.mark.django_db
def test_seed_demo_data_uses_supplied_password():
    supplied_secret = uuid4().hex + "A1!"

    call_command("seed_demo_data", demo_user_password=supplied_secret)
    user = User.objects.get(username="demo_ki_koordinator")
    assert user.check_password(supplied_secret)


@pytest.mark.django_db
def test_seed_demo_data_refuses_when_debug_is_disabled(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="only allowed with DEBUG=True"):
        call_command("seed_demo_data", demo_user_password=uuid4().hex + "A1!")


@pytest.mark.django_db
def test_demo_data_contains_all_lifecycle_statuses():
    call_command("seed_demo_data")

    statuses = set(
        UseCase.objects.filter(title__in=demo_use_case_titles()).values_list("status", flat=True)
    )

    assert statuses == {
        UseCase.Status.IDEA,
        UseCase.Status.REVIEW,
        UseCase.Status.PILOT,
        UseCase.Status.OPERATION,
        UseCase.Status.ENDED,
    }


@pytest.mark.django_db
def test_demo_data_contains_due_and_overdue_reviews():
    today = timezone.localdate()

    call_command("seed_demo_data")

    active = UseCase.objects.filter(title__in=demo_use_case_titles()).exclude(
        status=UseCase.Status.ENDED
    )
    assert active.filter(next_review_date__lt=today).count() >= 2
    assert (
        active.filter(
            next_review_date__gte=today,
            next_review_date__lte=today + timedelta(days=30),
        ).count()
        >= 2
    )


@pytest.mark.django_db
def test_governance_screenings_and_reviews_are_linked_to_demo_use_cases():
    call_command("seed_demo_data")

    governance = GovernanceAssessment.objects.filter(use_case__title__in=demo_use_case_titles())
    reviews = Review.objects.filter(use_case__title__in=demo_use_case_titles())

    assert governance.filter(
        use_case__isnull=False, reviewer__username="demo_ki_koordinator"
    ).count()
    assert reviews.filter(use_case__isnull=False, reviewer__username="demo_ki_koordinator").count()
    assert governance.filter(personal_data=True).exists()
    assert governance.filter(automated_person_assessment=True).exists()
    assert reviews.filter(
        previous_status__isnull=False,
        new_status__isnull=False,
        rationale__contains="KI-Radar Demo-Datensatz",
    ).exists()


@pytest.mark.django_db
def test_demo_data_contains_confirmed_go_live_exception():
    call_command("seed_demo_data")

    exception_review = Review.objects.get(
        use_case__title=f"{DEMO_PREFIX} Unterstuetzung bei Kundenanfragen",
        decision=Review.Decision.GO_LIVE,
    )
    use_case = exception_review.use_case

    assert exception_review.go_live_exception_confirmed is True
    assert use_case.status == UseCase.Status.OPERATION
    assert use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED
    assert use_case.legal_review_completed is True
    assert use_case.support_responsibility


@pytest.mark.django_db
def test_clear_demo_data_removes_only_seeded_demo_data():
    manual_unit = BusinessUnit.objects.create(name="Manuelle Organisationseinheit")
    manual_user = User.objects.create_user(
        username="manual_user",
        password="Manual-User-2026!",
        business_unit=manual_unit,
    )
    manual_use_case = UseCase.objects.create(
        title="Manuell angelegter Use Case",
        problem_statement="Nicht Teil des Demo-Datensatzes.",
        business_unit=manual_unit,
        affected_process="Manueller Prozess",
        business_owner=manual_user,
        expected_benefit="Manueller Nutzen",
    )

    call_command("seed_demo_data")
    call_command("clear_demo_data")

    assert UseCase.objects.filter(title__in=demo_use_case_titles()).count() == 0
    assert User.objects.filter(username__in=demo_usernames()).count() == 0
    assert BusinessUnit.objects.filter(name__in=demo_business_unit_names()).count() == 0
    assert BusinessUnit.objects.filter(pk=manual_unit.pk).exists()
    assert User.objects.filter(pk=manual_user.pk).exists()
    assert UseCase.objects.filter(pk=manual_use_case.pk).exists()


@pytest.mark.django_db
def test_clear_demo_data_keeps_manual_data_with_demo_like_prefix():
    manual_unit = BusinessUnit.objects.create(name=f"{DEMO_PREFIX} Manuell behalten")
    manual_user = User.objects.create_user(
        username="demo_manual_benutzer",
        password="Manual-User-2026!",
        business_unit=manual_unit,
    )
    manual_use_case = UseCase.objects.create(
        title=f"{DEMO_PREFIX} Manuell angelegter Use Case",
        problem_statement="Demo-aehnlicher Name, aber nicht vom Seed definiert.",
        business_unit=manual_unit,
        affected_process="Manueller Prozess",
        business_owner=manual_user,
        expected_benefit="Manueller Nutzen",
    )

    call_command("seed_demo_data")
    call_command("clear_demo_data")

    assert BusinessUnit.objects.filter(pk=manual_unit.pk).exists()
    assert User.objects.filter(pk=manual_user.pk).exists()
    assert UseCase.objects.filter(pk=manual_use_case.pk).exists()


@pytest.mark.django_db
def test_clear_demo_data_keeps_demo_user_referenced_by_manual_use_case():
    call_command("seed_demo_data")
    demo_user = User.objects.get(username="demo_ki_koordinator")
    manual_unit = BusinessUnit.objects.create(name="Manuelle Einheit mit Demo-Owner")
    manual_use_case = UseCase.objects.create(
        title="Manueller Use Case mit Demo-Owner",
        problem_statement="Nicht Teil des Demo-Datensatzes.",
        business_unit=manual_unit,
        affected_process="Manueller Prozess",
        business_owner=demo_user,
        expected_benefit="Manueller Nutzen",
    )

    call_command("clear_demo_data")

    assert User.objects.filter(pk=demo_user.pk).exists()
    assert UseCase.objects.filter(pk=manual_use_case.pk).exists()
    assert UseCase.objects.filter(title__in=demo_use_case_titles()).count() == 0
