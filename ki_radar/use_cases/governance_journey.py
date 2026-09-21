from __future__ import annotations

from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.services import current_governance_status

from . import journey as legacy
from . import workflow
from .models import UseCase

JourneyState = workflow.JourneyState
JourneyStep = workflow.JourneyStep

_original_build_use_case = None


def _state(
    journey: JourneyState,
    steps: list[JourneyStep],
    *,
    completion_message: str | None = None,
) -> JourneyState:
    return JourneyState(
        path_label=journey.path_label,
        steps=tuple(steps),
        next_action=next((step for step in steps if step.state in {"current", "blocked"}), None),
        completion_message=(
            journey.completion_message if completion_message is None else completion_message
        ),
    )


def _governance_step(use_case: UseCase, user) -> JourneyStep:
    final_decision = use_case.approval_decisions.filter(finalized_at__isnull=False).first()
    if final_decision is not None and final_decision.decision_status in {
        UseCase.DecisionStatus.DEFERRED,
        UseCase.DecisionStatus.NOT_PURSUED,
    }:
        return JourneyStep(
            key="governance",
            label="Governance",
            state="optional",
            reason="Negative Entscheidungen benötigen bewusst kein Governance-Gate.",
        )

    assessment = use_case.decision_assessments.first()
    if assessment is None:
        return JourneyStep(
            key="governance",
            label="Governance",
            state="upcoming",
            reason=(
                "Governance kann nach der strukturierten Bewertung risikobasiert ergänzt werden."
            ),
        )

    governance = current_governance_status(use_case)
    if not governance.has_screening:
        allowed = is_coordinator(user)
        return JourneyStep(
            key="governance",
            label="Governance",
            state="current",
            url=(
                reverse("governance:create", kwargs={"use_case_id": use_case.pk})
                if allowed
                else None
            ),
            action_label="Governance-Screening durchführen" if allowed else "",
            reason=(
                "Das Screening fehlt. Es ist für eine positive Freigabe erforderlich; "
                "eine negative Portfolioentscheidung bleibt trotzdem möglich."
            ),
        )

    incomplete_reviews = governance.incomplete_required_reviews
    if incomplete_reviews:
        first = incomplete_reviews[0]
        allowed = is_coordinator(user)
        return JourneyStep(
            key="governance",
            label="Governance",
            state="current",
            url=(
                reverse(
                    "governance:review",
                    kwargs={
                        "use_case_id": use_case.pk,
                        "review_type": first.definition.review_type,
                    },
                )
                if allowed
                else None
            ),
            action_label=f"{first.definition.label} durchführen" if allowed else "",
            reason=(
                "Erforderliche Fachprüfungen sind noch nicht erfolgreich abgeschlossen. "
                "Delivery-Vorbereitung kann parallel laufen; vor dem tatsächlichen Pilotstart "
                "müssen sie abgeschlossen sein."
            ),
            details=tuple(item.definition.label for item in incomplete_reviews),
        )

    reason = (
        "Governance-Screening und alle erforderlichen Fachprüfungen sind abgeschlossen."
        if governance.required_reviews
        else "Das Governance-Screening hat keine zusätzlichen Fachprüfungen abgeleitet."
    )
    return JourneyStep(
        key="governance",
        label="Governance",
        state="complete",
        url=f"{use_case.get_absolute_url()}#governance-evidence",
        action_label="Governance öffnen",
        reason=reason,
    )


def _completion_message(use_case: UseCase, journey: JourneyState) -> str:
    if use_case.status == UseCase.Status.ENDED:
        return "Journey abgeschlossen: Das Vorhaben wurde fachlich beendet."
    package = use_case.delivery_packages.first()
    if package is None or package.status != DeliveryPackage.Status.HANDED_OVER:
        return journey.completion_message
    return ""


def _insert_governance(
    use_case: UseCase,
    user,
    journey: JourneyState,
) -> JourneyState:
    governance_step = _governance_step(use_case, user)
    steps: list[JourneyStep] = []
    inserted = False
    for step in journey.steps:
        if step.key == "approval" and not inserted:
            steps.append(governance_step)
            inserted = True
        # Governance is now an independent readiness/risk projection. Positive Approval itself
        # enforces the screening; negative decisions deliberately do not. Do not rewrite the
        # Approval step to upcoming here.
        steps.append(step)
    if not inserted:
        steps.append(governance_step)
    return _state(
        journey,
        steps,
        completion_message=_completion_message(use_case, journey),
    )


def build_use_case_journey(use_case: UseCase, user) -> JourneyState:
    if _original_build_use_case is None:
        raise RuntimeError("Governance journey is not installed.")
    journey = _original_build_use_case(use_case, user)
    return _insert_governance(use_case, user, journey)


def install() -> None:
    global _original_build_use_case
    if workflow.build_use_case_journey is build_use_case_journey:
        return
    _original_build_use_case = workflow.build_use_case_journey
    workflow.build_use_case_journey = build_use_case_journey
    legacy.build_use_case_journey = build_use_case_journey
