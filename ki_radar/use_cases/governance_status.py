from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.urls import reverse

from ki_radar.governance.models import GovernanceReview
from ki_radar.governance.services import (
    REVIEW_DEFINITIONS,
    GovernanceReviewState,
    ReviewDefinition,
    current_governance_status,
)

from .models import UseCase


@dataclass(frozen=True)
class ReviewKind:
    """Presentation metadata sourced from the Governance-owned definition."""

    key: str
    label: str
    completed_field: str


def _kind(definition: ReviewDefinition) -> ReviewKind:
    return ReviewKind(
        key=definition.review_type,
        label=definition.short_label,
        completed_field=definition.completed_field,
    )


@dataclass(frozen=True)
class GovernanceReviewStatus:
    kind: ReviewKind
    state: str
    label: str
    badge_class: str
    actor: str | None
    changed_at: date | datetime | None
    changed_at_has_time: bool
    attribution_note: str
    result: str = ""
    rationale: str = ""
    target_url: str = ""

    @property
    def editable(self) -> bool:
        return False


def _display_name(user, *, fallback: str) -> str:
    if user is None:
        return fallback
    return user.get_display_name()


def _latest_completion_change(use_case: UseCase, field_name: str):
    records = list(
        use_case.history.select_related("history_user").order_by("history_date", "history_id")
    )
    latest_change = None
    previous_value = False
    for record in records:
        current_value = getattr(record, field_name)
        if current_value != previous_value:
            latest_change = record
        previous_value = current_value
    return latest_change


def _artifact_status(
    use_case: UseCase,
    state: GovernanceReviewState,
) -> GovernanceReviewStatus | None:
    artifact = state.review
    if artifact is None:
        return None

    definition = state.definition
    kind = _kind(definition)
    target_url = reverse(
        "governance:review",
        kwargs={"use_case_id": use_case.pk, "review_type": definition.review_type},
    )
    common = {
        "kind": kind,
        "actor": _display_name(artifact.reviewer, fallback="unbekannt"),
        "changed_at": artifact.created_at,
        "changed_at_has_time": True,
        "rationale": artifact.rationale,
        "target_url": target_url,
    }
    if artifact.status == GovernanceReview.Status.NOT_RELEVANT:
        return GovernanceReviewStatus(
            state="not_required",
            label="Nicht relevant",
            badge_class="text-bg-light border text-dark",
            attribution_note="Begründete Nicht-Relevanz",
            **common,
        )
    if artifact.status == GovernanceReview.Status.OPEN:
        return GovernanceReviewStatus(
            state="open",
            label="Offen",
            badge_class="text-bg-warning",
            attribution_note="Durch Screening als erforderlich geöffnet",
            **common,
        )

    passed = artifact.result in {
        GovernanceReview.Result.PASSED,
        GovernanceReview.Result.PASSED_WITH_CONDITIONS,
    }
    return GovernanceReviewStatus(
        state="completed",
        label="Abgeschlossen",
        badge_class="text-bg-success" if passed else "text-bg-danger",
        attribution_note="Formales Prüfartefakt",
        result=artifact.get_result_display(),
        **common,
    )


def build_governance_statuses(use_case: UseCase) -> tuple[GovernanceReviewStatus, ...]:
    governance = current_governance_status(use_case) if use_case.pk else None
    assessment = governance.screening if governance is not None else None
    states = governance.reviews if governance is not None else ()

    if not states:
        states = tuple(
            GovernanceReviewState(definition=definition, required=False, review=None)
            for definition in REVIEW_DEFINITIONS.values()
        )

    statuses = []
    for state in states:
        definition = state.definition
        kind = _kind(definition)
        review_url = (
            reverse(
                "governance:review",
                kwargs={
                    "use_case_id": use_case.pk,
                    "review_type": definition.review_type,
                },
            )
            if use_case.pk
            else ""
        )
        if assessment is None:
            statuses.append(
                GovernanceReviewStatus(
                    kind=kind,
                    state="not_assessed",
                    label="Noch nicht bewertet",
                    badge_class="text-bg-secondary",
                    actor=None,
                    changed_at=None,
                    changed_at_has_time=False,
                    attribution_note="Noch kein Governance-Screening vorhanden.",
                    target_url=(
                        reverse("governance:create", kwargs={"use_case_id": use_case.pk})
                        if use_case.pk
                        else ""
                    ),
                )
            )
            continue

        artifact_status = _artifact_status(use_case, state)
        if artifact_status is not None:
            statuses.append(artifact_status)
            continue

        if not state.required:
            statuses.append(
                GovernanceReviewStatus(
                    kind=kind,
                    state="not_required",
                    label="Nicht relevant",
                    badge_class="text-bg-light border text-dark",
                    actor=_display_name(assessment.reviewer, fallback="unbekannt"),
                    changed_at=assessment.assessment_date,
                    changed_at_has_time=False,
                    attribution_note="Maßgebliches Governance-Screening",
                    rationale=assessment.review_rationale(definition.review_type),
                    target_url=review_url,
                )
            )
            continue

        completion_change = _latest_completion_change(use_case, definition.completed_field)
        if state.completed:
            statuses.append(
                GovernanceReviewStatus(
                    kind=kind,
                    state="completed",
                    label="Abgeschlossen",
                    badge_class="text-bg-success",
                    actor=_display_name(
                        completion_change.history_user if completion_change else None,
                        fallback="System",
                    ),
                    changed_at=(
                        completion_change.history_date
                        if completion_change
                        else assessment.assessment_date
                    ),
                    changed_at_has_time=completion_change is not None,
                    attribution_note="Legacy-Abschlussstatus ohne separates Prüfartefakt",
                    target_url=review_url,
                )
            )
            continue

        statuses.append(
            GovernanceReviewStatus(
                kind=kind,
                state="open",
                label="Offen",
                badge_class="text-bg-warning",
                actor=_display_name(assessment.reviewer, fallback="unbekannt"),
                changed_at=assessment.assessment_date,
                changed_at_has_time=False,
                attribution_note="Als erforderlich bewertet",
                rationale=assessment.review_rationale(definition.review_type),
                target_url=review_url,
            )
        )
    return tuple(statuses)
