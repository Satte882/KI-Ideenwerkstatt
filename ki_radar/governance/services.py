from dataclasses import dataclass

from django.db import transaction

from ki_radar.use_cases.models import UseCase

from .models import GovernanceAssessment, GovernanceReview


@dataclass(frozen=True)
class ReviewDefinition:
    review_type: str
    label: str
    short_label: str
    responsible_role: str
    required_field: str
    completed_field: str
    rationale_field: str

    @property
    def key(self) -> str:
        return self.review_type


@dataclass(frozen=True)
class GovernanceReviewState:
    definition: ReviewDefinition
    required: bool
    review: GovernanceReview | None
    legacy_completed: bool = False

    @property
    def completed(self) -> bool:
        if not self.required:
            return True
        if self.review is not None:
            return self.review.is_completed
        return self.legacy_completed

    @property
    def failed(self) -> bool:
        return bool(
            self.required
            and self.review is not None
            and self.review.status == GovernanceReview.Status.COMPLETED
            and self.review.result == GovernanceReview.Result.FAILED
        )

    @property
    def conditionally_passed(self) -> bool:
        return bool(
            self.required
            and self.review is not None
            and self.review.status == GovernanceReview.Status.COMPLETED
            and self.review.result == GovernanceReview.Result.PASSED_WITH_CONDITIONS
        )

    @property
    def blocker(self) -> str:
        if not self.required or self.completed:
            return ""
        if self.review is None or self.review.status != GovernanceReview.Status.COMPLETED:
            return f"{self.definition.label} ist noch offen"
        if self.review.result == GovernanceReview.Result.FAILED:
            return f"{self.definition.label} wurde nicht bestanden"
        return f"{self.definition.label} besitzt kein erfolgreiches Ergebnis"


@dataclass(frozen=True)
class GovernanceStatus:
    screening: GovernanceAssessment | None
    reviews: tuple[GovernanceReviewState, ...]

    @property
    def has_screening(self) -> bool:
        return self.screening is not None

    @property
    def required_reviews(self) -> tuple[GovernanceReviewState, ...]:
        return tuple(review for review in self.reviews if review.required)

    @property
    def incomplete_required_reviews(self) -> tuple[GovernanceReviewState, ...]:
        return tuple(review for review in self.required_reviews if not review.completed)


REVIEW_DEFINITIONS = {
    GovernanceReview.ReviewType.PRIVACY: ReviewDefinition(
        review_type=GovernanceReview.ReviewType.PRIVACY,
        label="Datenschutzprüfung",
        short_label="Datenschutz",
        responsible_role="Datenschutz",
        required_field="privacy_review_required",
        completed_field="privacy_review_completed",
        rationale_field="privacy_review_rationale",
    ),
    GovernanceReview.ReviewType.SECURITY: ReviewDefinition(
        review_type=GovernanceReview.ReviewType.SECURITY,
        label="Informationssicherheitsprüfung",
        short_label="Security",
        responsible_role="Informationssicherheit",
        required_field="security_review_required",
        completed_field="security_review_completed",
        rationale_field="security_review_rationale",
    ),
    GovernanceReview.ReviewType.LEGAL: ReviewDefinition(
        review_type=GovernanceReview.ReviewType.LEGAL,
        label="Rechtsprüfung",
        short_label="Recht",
        responsible_role="Recht / Compliance",
        required_field="legal_review_required",
        completed_field="legal_review_completed",
        rationale_field="legal_review_rationale",
    ),
}
REVIEW_ORDER = tuple(REVIEW_DEFINITIONS)


def review_definition(review_type: str) -> ReviewDefinition:
    return REVIEW_DEFINITIONS[review_type]


def latest_review_for_screening(
    *,
    use_case: UseCase,
    review_type: str,
    screening: GovernanceAssessment,
) -> GovernanceReview | None:
    return (
        use_case.governance_reviews.filter(
            review_type=review_type,
            screening=screening,
        )
        .select_related("reviewer", "screening")
        .first()
    )


def review_history(*, use_case: UseCase, review_type: str):
    return use_case.governance_reviews.filter(review_type=review_type).select_related(
        "reviewer", "screening"
    )


def governance_review_evidence(use_case: UseCase) -> tuple[GovernanceReview, ...]:
    """Return Governance-owned formal-review evidence in stable snapshot order."""

    return tuple(
        use_case.governance_reviews.select_related("screening", "reviewer").order_by(
            "review_type", "-created_at"
        )
    )


def current_governance_status(use_case: UseCase) -> GovernanceStatus:
    """Return the Governance-owned current screening/review state for a Use Case.

    The current screening and its review artifacts are the canonical source. The mirrored
    ``UseCase.*_review_required/completed`` fields are consulted only for pre-artifact legacy
    records, keeping that compatibility fallback inside the Governance boundary.
    """

    screening = use_case.governance_assessments.select_related("reviewer").first()
    if screening is None:
        return GovernanceStatus(
            screening=None,
            reviews=tuple(
                GovernanceReviewState(definition=definition, required=False, review=None)
                for definition in REVIEW_DEFINITIONS.values()
            ),
        )

    artifacts: dict[str, GovernanceReview] = {}
    for review in (
        use_case.governance_reviews.filter(screening=screening)
        .select_related("reviewer", "screening")
        .order_by("-created_at", "-reviewed_at")
    ):
        artifacts.setdefault(review.review_type, review)
    legacy_screening = not artifacts

    states = []
    for definition in REVIEW_DEFINITIONS.values():
        required = bool(getattr(screening, definition.required_field))
        if legacy_screening and not required:
            required = bool(getattr(use_case, definition.required_field))
        review = artifacts.get(definition.review_type)
        legacy_completed = bool(
            legacy_screening
            and required
            and review is None
            and getattr(use_case, definition.completed_field)
        )
        states.append(
            GovernanceReviewState(
                definition=definition,
                required=required,
                review=review,
                legacy_completed=legacy_completed,
            )
        )
    return GovernanceStatus(screening=screening, reviews=tuple(states))


def required_governance_blockers(use_case: UseCase) -> list[str]:
    return [
        review.blocker
        for review in current_governance_status(use_case).required_reviews
        if review.blocker
    ]


def failed_required_governance_reviews(use_case: UseCase) -> list[str]:
    return [
        review.blocker
        for review in current_governance_status(use_case).required_reviews
        if review.failed and review.blocker
    ]


def open_required_governance_warnings(use_case: UseCase) -> list[str]:
    return [
        f"Readiness offen: {review.blocker}"
        for review in current_governance_status(use_case).required_reviews
        if review.blocker and not review.failed
    ]


@transaction.atomic
def create_screening_review_artifacts(
    *,
    assessment: GovernanceAssessment,
    actor,
) -> tuple[GovernanceReview, ...]:
    """Create one explicit formal-review status artifact per review type and screening."""
    artifacts = []
    for definition in REVIEW_DEFINITIONS.values():
        required = getattr(assessment, definition.required_field)
        artifact = GovernanceReview(
            use_case=assessment.use_case,
            screening=assessment,
            review_type=definition.review_type,
            status=(
                GovernanceReview.Status.OPEN if required else GovernanceReview.Status.NOT_RELEVANT
            ),
            reviewed_at=assessment.assessment_date,
            reviewer=actor,
            responsible_role=definition.responsible_role,
            result="",
            rationale=assessment.review_rationale(definition.review_type),
        )
        artifact.full_clean()
        artifact._history_user = actor
        artifact.save()
        artifacts.append(artifact)
    return tuple(artifacts)


def sync_completion_from_review(
    *,
    use_case: UseCase,
    review: GovernanceReview,
    actor,
) -> None:
    definition = review_definition(review.review_type)
    setattr(use_case, definition.completed_field, review.is_completed)
    use_case._history_user = actor
    use_case.save(update_fields=[definition.completed_field, "updated_at"])
