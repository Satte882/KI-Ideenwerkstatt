import pytest
from django.core.exceptions import ValidationError

from ki_radar.accelerator.role_default_guard import (
    validate_business_owner_suggestion,
    validate_role_default_submission,
    validate_second_approver_suggestion,
)
from ki_radar.accelerator.role_defaults import resolve_use_case_business_owner
from ki_radar.accounts.models import User
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


def _value_stream(*, business_unit, owner):
    return ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )


def _use_case(*, business_unit, owner):
    return UseCase.objects.create(
        title="Block-9-Guard",
        problem_statement="Rollen-Vorschläge müssen vor dem Speichern erneut geprüft werden.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        business_owner=owner,
        expected_benefit="Manipulierte oder veraltete Rollenwerte werden verhindert.",
    )


def test_business_owner_guard_accepts_current_cross_role_suggestion(business_unit, owner):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)

    resolution = validate_business_owner_suggestion(
        submitted_user_id=owner.pk,
        value_stream=value_stream,
    )

    assert resolution is not None
    assert resolution.user_id == owner.pk


def test_business_owner_guard_rejects_manipulated_person_id(
    business_unit,
    owner,
    other_owner,
):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)

    with pytest.raises(ValidationError):
        validate_business_owner_suggestion(
            submitted_user_id=other_owner.pk,
            value_stream=value_stream,
        )


def test_business_owner_guard_reloads_changed_source(business_unit, owner, other_owner):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)
    assert resolve_use_case_business_owner(value_stream=value_stream).user_id == owner.pk

    ValueStream.objects.filter(pk=value_stream.pk).update(owner=other_owner)

    with pytest.raises(ValidationError):
        validate_business_owner_suggestion(
            submitted_user_id=owner.pk,
            value_stream=value_stream,
        )


def test_business_owner_guard_rejects_candidate_that_became_ineligible(business_unit, owner):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)
    User.objects.filter(pk=owner.pk).update(is_active=False)

    with pytest.raises(ValidationError):
        validate_business_owner_suggestion(
            submitted_user_id=owner.pk,
            value_stream=value_stream,
        )


def test_generic_guard_never_overwrites_existing_target(business_unit, owner, other_owner):
    value_stream = _value_stream(business_unit=business_unit, owner=other_owner)

    with pytest.raises(ValidationError):
        validate_role_default_submission(
            submitted_user_id=other_owner.pk,
            resolution_factory=lambda: resolve_use_case_business_owner(value_stream=value_stream),
            existing_user_id=owner.pk,
        )


def test_generic_guard_rejects_open_resolution(owner):
    with pytest.raises(ValidationError):
        validate_role_default_submission(
            submitted_user_id=owner.pk,
            resolution_factory=resolve_use_case_business_owner,
        )


def test_second_approver_guard_reuses_current_eligibility(
    business_unit,
    owner,
    coordinator,
    technical_admin,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)

    accepted = validate_second_approver_suggestion(
        submitted_user_id=technical_admin.pk,
        use_case=use_case,
        first_decider=coordinator,
    )
    assert accepted is not None
    assert accepted.user_id == technical_admin.pk

    User.objects.filter(pk=technical_admin.pk).update(is_active=False)

    with pytest.raises(ValidationError):
        validate_second_approver_suggestion(
            submitted_user_id=technical_admin.pk,
            use_case=use_case,
            first_decider=coordinator,
        )
