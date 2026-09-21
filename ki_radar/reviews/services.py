from django.db import transaction
from django.utils import timezone

from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.scale_readiness import (
    SCALE_READINESS_SCHEMA_VERSION,
    build_scale_readiness_snapshot,
    evaluate_scale_readiness,
    extract_scale_evidence,
)
from ki_radar.use_cases.transition_policy import validate_review_command

from .models import EarlyGoLiveException, Review

DECISION_TARGETS = {
    Review.Decision.START_REVIEW: UseCase.Status.REVIEW,
    Review.Decision.START_PILOT: UseCase.Status.PILOT,
    Review.Decision.GO_LIVE: UseCase.Status.OPERATION,
    Review.Decision.END: UseCase.Status.ENDED,
}
SCALE_SNAPSHOT_DECISIONS = {
    Review.Decision.GO_LIVE,
    Review.Decision.CONTINUE,
    Review.Decision.REWORK,
    Review.Decision.END,
}
EARLY_EXCEPTION_FIELDS = (
    "early_go_live_exception_confirmed",
    "early_go_live_original_pilot_end",
    "early_go_live_evidence_basis",
    "early_go_live_unobserved_risks",
    "early_go_live_mitigation_measures",
)


def _optional_early_exception_data(review_data: dict) -> dict:
    return {field_name: review_data.pop(field_name, None) for field_name in EARLY_EXCEPTION_FIELDS}


def _apply_use_case_command(
    *,
    use_case: UseCase,
    actor,
    decision: str,
    target_status: str,
    pilot_start,
    next_review_date,
) -> None:
    if decision == Review.Decision.START_PILOT:
        use_case.pilot_start = pilot_start
    if decision == Review.Decision.END and not use_case.actual_end_date:
        use_case.actual_end_date = timezone.localdate()
    if target_status != use_case.status:
        use_case.status = target_status
    if next_review_date is not None:
        use_case.next_review_date = next_review_date
    use_case._history_user = actor
    use_case.save()


@transaction.atomic
def create_review(*, use_case, actor, data) -> Review:
    """Canonical write path for lifecycle commands and non-transition reviews.

    Status and Review artifact are persisted in the same transaction. Readiness evidence is
    snapshotted for transparency, but only the enforcement policy may block a command.
    """

    use_case = UseCase.objects.select_for_update().get(pk=use_case.pk)
    previous_status = use_case.status
    review_data = data.copy()
    pilot_start = review_data.pop("pilot_start", None)
    scale_evidence = extract_scale_evidence(review_data)
    early_exception_data = _optional_early_exception_data(review_data)

    decision = review_data.get("decision")
    target_status = review_data.get("new_status")

    validate_review_command(
        use_case=use_case,
        decision=decision,
        target_status=target_status,
        actor=actor,
        pilot_start=pilot_start,
        scale_evidence=scale_evidence,
        go_live_exception_confirmed=bool(review_data.get("go_live_exception_confirmed")),
        rationale=review_data.get("rationale", ""),
    )

    for field in [
        "ending_reason",
        "data_and_access_handling",
        "replacement_solution",
        "final_assessment",
        "lessons_learned",
    ]:
        value = review_data.pop(field, "")
        if value:
            setattr(use_case, field, value)

    scale_result = None
    snapshot = {}
    if previous_status == UseCase.Status.PILOT and decision in SCALE_SNAPSHOT_DECISIONS:
        scale_result = evaluate_scale_readiness(use_case, scale_evidence)
        snapshot = build_scale_readiness_snapshot(use_case, scale_evidence, scale_result)

    review = Review(
        use_case=use_case,
        reviewer=actor,
        previous_status=previous_status,
        scale_readiness_schema_version=SCALE_READINESS_SCHEMA_VERSION,
        scale_readiness_snapshot=snapshot,
        **review_data,
    )
    review._history_user = actor
    review.save()

    _apply_use_case_command(
        use_case=use_case,
        actor=actor,
        decision=decision,
        target_status=target_status,
        pilot_start=pilot_start,
        next_review_date=review_data.get("next_review_date"),
    )

    # The former early-Go-live exception is no longer a hard gate. Preserve an explicit
    # voluntary acknowledgement if users still submit it, without requiring extra fields.
    if early_exception_data.get("early_go_live_exception_confirmed"):
        original_end = (
            early_exception_data.get("early_go_live_original_pilot_end")
            or use_case.planned_pilot_end
            or review.review_date
        )
        EarlyGoLiveException.objects.create(
            review=review,
            original_planned_pilot_end=original_end,
            decision_date=review.review_date,
            reason=review.rationale or "Vorzeitige Produktivsetzung bewusst entschieden.",
            evidence_basis=early_exception_data.get("early_go_live_evidence_basis") or "",
            unobserved_risks=early_exception_data.get("early_go_live_unobserved_risks") or "",
            mitigation_measures=early_exception_data.get("early_go_live_mitigation_measures") or "",
            confirmed_by=actor,
            confirmed_by_label=actor.get_display_name(),
            confirmed_role="KI-Koordinator",
        )

    return review
