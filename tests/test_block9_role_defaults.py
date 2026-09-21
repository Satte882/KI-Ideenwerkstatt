import pytest
from django.contrib.auth.models import Group

from ki_radar.accelerator.role_defaults import (
    EXISTING,
    INELIGIBLE,
    OPEN,
    PREFILL,
    ROLE_ONLY,
    SUGGESTION,
    resolve_delivery_review_roles,
    resolve_delivery_technical_owner,
    resolve_second_approver,
    resolve_use_case_business_owner,
    resolve_use_case_coordinator,
)
from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.architecture.models import ValueStream
from ki_radar.delivery.models import DeliveryPackage, DeliverySectionReview
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


def _use_case(*, business_unit, owner, technical_owner=None, coordinator=None):
    return UseCase.objects.create(
        title="Block-9-Testfall",
        problem_statement="Ein reproduzierbarer Testfall benötigt eine klarere Bearbeitung.",
        business_unit=business_unit,
        affected_process="Testprozess",
        business_owner=owner,
        technical_owner=technical_owner,
        coordinator=coordinator,
        expected_benefit="Weniger manuelle Bearbeitung",
    )


def _coordinator_user(*, username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def test_existing_business_owner_is_revalidated_from_database(business_unit, owner):
    use_case = _use_case(business_unit=business_unit, owner=owner)

    initial = resolve_use_case_business_owner(use_case=use_case)
    assert initial.state == EXISTING
    assert initial.user_id == owner.pk

    User.objects.filter(pk=owner.pk).update(is_active=False)

    refreshed = resolve_use_case_business_owner(use_case=use_case)
    assert refreshed.state == INELIGIBLE
    assert refreshed.user_id == owner.pk


def test_value_stream_owner_is_cross_role_suggestion(business_unit, owner):
    value_stream = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )

    resolution = resolve_use_case_business_owner(value_stream=value_stream)

    assert resolution.state == SUGGESTION
    assert resolution.user_id == owner.pk
    assert resolution.source_kind == "value_stream"
    assert "Cross-Role" in resolution.reason


def test_business_owner_without_source_stays_open():
    resolution = resolve_use_case_business_owner()

    assert resolution.state == OPEN
    assert resolution.user_id is None


def test_existing_coordinator_is_revalidated(business_unit, owner, coordinator):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        coordinator=coordinator,
    )

    assert resolve_use_case_coordinator(use_case=use_case).state == EXISTING

    User.objects.filter(pk=coordinator.pk).update(is_anonymized=True)

    assert resolve_use_case_coordinator(use_case=use_case).state == INELIGIBLE


def test_delivery_technical_owner_uses_same_role_source(business_unit, owner, reader):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        technical_owner=reader,
    )

    resolution = resolve_delivery_technical_owner(use_case=use_case)

    assert resolution.state == PREFILL
    assert resolution.user_id == reader.pk
    assert resolution.source_kind == "use_case"


def test_unique_independent_second_approver_is_only_a_suggestion(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    candidate = _coordinator_user(username="second", business_unit=business_unit)

    resolution = resolve_second_approver(
        use_case=use_case,
        first_decider=coordinator,
    )

    assert resolution.state == SUGGESTION
    assert resolution.user_id == candidate.pk
    assert use_case.approval_decisions.count() == 0


def test_multiple_second_approvers_do_not_create_person_preference(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    _coordinator_user(username="second-a", business_unit=business_unit)
    _coordinator_user(username="second-b", business_unit=business_unit)

    resolution = resolve_second_approver(
        use_case=use_case,
        first_decider=coordinator,
    )

    assert resolution.state == OPEN
    assert resolution.user_id is None
    assert "Mehrere" in resolution.reason


def test_assigned_second_approver_is_revalidated(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    assigned = _coordinator_user(username="assigned", business_unit=business_unit)

    initial = resolve_second_approver(
        use_case=use_case,
        first_decider=coordinator,
        assigned=assigned,
    )
    assert initial.state == EXISTING

    User.objects.filter(pk=assigned.pk).update(is_active=False)

    refreshed = resolve_second_approver(
        use_case=use_case,
        first_decider=coordinator,
        assigned=assigned,
    )
    assert refreshed.state == INELIGIBLE


def test_delivery_review_resolves_assigned_roles_without_confirming(
    business_unit,
    owner,
    reader,
):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        technical_owner=reader,
    )
    package = DeliveryPackage(
        use_case=use_case,
        technical_owner=reader,
        version=1,
    )
    review = DeliverySectionReview(
        delivery_package=package,
        section_key=DeliverySectionReview.Section.SOLUTION_DIRECTION,
    )

    resolutions = resolve_delivery_review_roles(package=package, review=review)

    assert [item.role for item in resolutions] == ["business", "technical"]
    assert all(item.resolution.state == SUGGESTION for item in resolutions)
    assert review.business_confirmed_at is None
    assert review.technical_confirmed_at is None


def test_delivery_review_falls_back_to_role_only_when_owner_turns_ineligible(
    business_unit,
    owner,
    reader,
):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        technical_owner=reader,
    )
    package = DeliveryPackage(
        use_case=use_case,
        technical_owner=reader,
        version=1,
    )
    review = DeliverySectionReview(
        delivery_package=package,
        section_key=DeliverySectionReview.Section.SOLUTION_DIRECTION,
    )

    User.objects.filter(pk=reader.pk).update(is_active=False)

    resolutions = resolve_delivery_review_roles(package=package, review=review)
    by_role = {item.role: item.resolution for item in resolutions}

    assert by_role["business"].state == SUGGESTION
    assert by_role["technical"].state == ROLE_ONLY
