from types import SimpleNamespace

import pytest
from django.utils import timezone

from ki_radar.delivery.handover import recorded_handover_package
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.governance.services import (
    create_screening_review_artifacts,
    current_governance_status,
    required_governance_blockers,
)
from ki_radar.use_cases.governance_status import build_governance_statuses
from ki_radar.use_cases.models import UseCase


class _Packages:
    def __init__(self, package):
        self.package = package

    def order_by(self, *_args):
        return self

    def first(self):
        return self.package


def _handover_use_case(package):
    return SimpleNamespace(delivery_packages=_Packages(package))


def _use_case(*, owner, business_unit, **overrides):
    values = {
        "title": "Issue 420",
        "problem_statement": "Ownership-Grenzen sollen eindeutig sein.",
        "business_unit": business_unit,
        "affected_process": "Use-Case-Steuerung",
        "submitter": owner,
        "business_owner": owner,
        "expected_benefit": "Keine parallele fachliche Wahrheit.",
    }
    values.update(overrides)
    return UseCase.objects.create(**values)


@pytest.mark.parametrize(
    ("status", "handed_over_at", "expected"),
    [
        (DeliveryPackage.Status.DRAFT, None, False),
        (DeliveryPackage.Status.READY, timezone.now(), False),
        (DeliveryPackage.Status.HANDED_OVER, None, False),
        (DeliveryPackage.Status.HANDED_OVER, timezone.now(), True),
    ],
)
def test_delivery_owned_recorded_handover_contract_is_persisted_milestone(
    status,
    handed_over_at,
    expected,
):
    package = SimpleNamespace(status=status, handed_over_at=handed_over_at)

    result = recorded_handover_package(_handover_use_case(package))

    assert (result is package) is expected


@pytest.mark.django_db
def test_governance_screening_wins_over_mirrored_use_case_flags(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(
        owner=owner,
        business_unit=business_unit,
        privacy_review_required=True,
        privacy_review_completed=True,
    )
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Issue 420",
        privacy_review_required=False,
        result=GovernanceAssessment.Result.NO_FLAGS,
    )
    create_screening_review_artifacts(assessment=screening, actor=coordinator)

    state = current_governance_status(use_case)
    privacy = next(item for item in state.reviews if item.definition.key == "privacy")

    assert state.screening == screening
    assert privacy.required is False
    assert privacy.completed is True
    assert required_governance_blockers(use_case) == []


@pytest.mark.django_db
def test_governance_consumers_use_screening_and_artifact_instead_of_mirror_flags(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(owner=owner, business_unit=business_unit)
    screening = GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Issue 420",
        privacy_review_required=True,
        result=GovernanceAssessment.Result.PRIVACY,
    )
    create_screening_review_artifacts(assessment=screening, actor=coordinator)

    state = current_governance_status(use_case)
    privacy = next(item for item in state.reviews if item.definition.key == "privacy")
    projected = next(
        item for item in build_governance_statuses(use_case) if item.kind.key == "privacy"
    )

    assert use_case.privacy_review_required is False
    assert privacy.required is True
    assert privacy.completed is False
    assert required_governance_blockers(use_case) == ["Datenschutzprüfung ist noch offen"]
    assert projected.state == "open"


@pytest.mark.django_db
def test_governance_legacy_flags_are_fallback_only_without_review_artifacts(
    owner,
    coordinator,
    business_unit,
):
    use_case = _use_case(
        owner=owner,
        business_unit=business_unit,
        privacy_review_required=True,
        privacy_review_completed=True,
    )
    GovernanceAssessment.objects.create(
        use_case=use_case,
        assessment_date=timezone.localdate(),
        reviewer=coordinator,
        basis_version="Legacy",
        result=GovernanceAssessment.Result.NO_FLAGS,
    )

    state = current_governance_status(use_case)
    privacy = next(item for item in state.reviews if item.definition.key == "privacy")

    assert privacy.required is True
    assert privacy.review is None
    assert privacy.legacy_completed is True
    assert privacy.completed is True
