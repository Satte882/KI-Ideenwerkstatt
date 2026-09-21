from __future__ import annotations

from dataclasses import replace

from django.urls import reverse

from ki_radar.accounts.permissions import is_business_owner, is_coordinator
from ki_radar.delivery.lean_services import delivery_enforcement_findings
from ki_radar.delivery.models import DeliveryPackage

from . import journey as legacy
from . import workflow
from .models import UseCase
from .permissions import can_start_pilot
from .services import check_pilot_start

JourneyState = workflow.JourneyState
JourneyStep = workflow.JourneyStep

_original_build_use_case = None


def _state(
    journey: JourneyState,
    steps: list[JourneyStep],
    completion_message: str | None = None,
):
    return JourneyState(
        path_label=journey.path_label,
        steps=tuple(steps),
        next_action=next((step for step in steps if step.state in {"current", "blocked"}), None),
        completion_message=(
            journey.completion_message if completion_message is None else completion_message
        ),
    )


def _can_transition_delivery(user, use_case: UseCase) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            is_coordinator(user)
            or (is_business_owner(user) and use_case.business_owner_id == user.id)
        )
    )


def _expose_early_negative_decision(
    use_case: UseCase,
    user,
    journey: JourneyState,
) -> JourneyState:
    if (
        use_case.status != UseCase.Status.REVIEW
        or use_case.decision_assessments.exists()
        or use_case.decision_status
        in {UseCase.DecisionStatus.DEFERRED, UseCase.DecisionStatus.NOT_PURSUED}
        or not is_coordinator(user)
    ):
        return journey

    steps: list[JourneyStep] = []
    changed = False
    for step in journey.steps:
        if step.key == "approval" and step.state == "upcoming":
            steps.append(
                replace(
                    step,
                    state="current",
                    url=reverse(
                        "use_cases:approval_decision_create",
                        kwargs={"pk": use_case.pk},
                    ),
                    action_label="Zurückstellen / nicht weiterverfolgen",
                    reason=(
                        "Eine strukturierte Bewertung ist für positive Freigaben erforderlich. "
                        "Eine negative Portfolioentscheidung darf bereits jetzt getroffen werden."
                    ),
                )
            )
            changed = True
        else:
            steps.append(step)
    return _state(journey, steps) if changed else journey


def _normalize_delivery(use_case: UseCase, user, journey: JourneyState) -> JourneyState:
    package = use_case.delivery_packages.first()
    if package is None:
        return journey

    enforcement = delivery_enforcement_findings(package)
    steps: list[JourneyStep] = []
    changed = False
    for step in journey.steps:
        if step.key != "delivery":
            steps.append(step)
            continue

        if package.status == DeliveryPackage.Status.HANDED_OVER and package.handed_over_at:
            steps.append(
                replace(
                    step,
                    state="complete",
                    url=package.get_absolute_url(),
                    action_label="Übergabe öffnen",
                    action_method="get",
                    reason=(
                        f"Delivery Package v{package.version} wurde verbindlich übergeben. "
                        "Offene Readiness-Hinweise bleiben sichtbar und blockieren "
                        "den Meilenstein nicht."
                    ),
                    details=(),
                )
            )
            changed = True
            continue

        if enforcement:
            steps.append(
                replace(
                    step,
                    state="blocked",
                    url=package.get_absolute_url(),
                    action_label="Fachlichen Blocker öffnen",
                    action_method="get",
                    reason=(
                        "Mindestens eine Delivery-Sektion wurde ausdrücklich fachlich blockiert."
                    ),
                    details=tuple(finding.message for finding in enforcement),
                )
            )
            changed = True
            continue

        allowed = _can_transition_delivery(user, use_case)
        if package.status == DeliveryPackage.Status.READY:
            technical_owner = package.technical_owner
            if technical_owner is None or not technical_owner.is_active:
                steps.append(
                    replace(
                        step,
                        state="blocked",
                        url=package.get_absolute_url(),
                        action_label="Technical Owner prüfen",
                        action_method="get",
                        reason=(
                            "Vor der verbindlichen Übergabe muss ein aktiver "
                            "Technical Owner benannt sein."
                        ),
                        details=("Aktiver Technical Owner",),
                    )
                )
                changed = True
                continue
            steps.append(
                replace(
                    step,
                    state="current",
                    url=(
                        reverse("delivery:package_handover", kwargs={"pk": package.pk})
                        if allowed
                        else package.get_absolute_url()
                    ),
                    action_label="An Delivery übergeben" if allowed else "Delivery Package öffnen",
                    action_method="post" if allowed else "get",
                    reason=(
                        "Das Package ist als bereit markiert. Offene Readiness-Hinweise "
                        "verhindern die verbindliche Übergabe nicht; ein aktiver "
                        "Technical Owner bleibt erforderlich."
                    ),
                    details=(),
                )
            )
        else:
            steps.append(
                replace(
                    step,
                    state="current",
                    url=(
                        reverse("delivery:package_mark_ready", kwargs={"pk": package.pk})
                        if allowed
                        else package.get_absolute_url()
                    ),
                    action_label="Als bereit markieren" if allowed else "Delivery Package öffnen",
                    action_method="post" if allowed else "get",
                    reason=(
                        "Readiness-Hinweise sind offen. Sie bleiben sichtbar und blockieren "
                        "die weitere Bearbeitung nicht."
                    ),
                    details=(),
                )
            )
        changed = True

    return _state(journey, steps) if changed else journey


def _ensure_pilot_start(use_case: UseCase, user, journey: JourneyState) -> JourneyState:
    if use_case.status != UseCase.Status.REVIEW:
        return journey
    if any(step.key == "pilot_start" for step in journey.steps):
        return journey
    package = use_case.delivery_packages.first()
    if (
        package is None
        or package.status != DeliveryPackage.Status.HANDED_OVER
        or package.handed_over_at is None
    ):
        return journey

    check = check_pilot_start(use_case)
    allowed = can_start_pilot(user, use_case)
    step = JourneyStep(
        key="pilot_start",
        label="Pilot starten",
        state="blocked" if check.blockers else "current",
        url=workflow.pilot_start_url(use_case) if allowed else None,
        action_label="Pilot starten" if allowed else "",
        reason=(
            "Die Übergabe ist erfolgt. Nur die verbleibenden echten Pilotstart-Invarianten "
            "können diese Aktion noch blockieren."
        ),
        details=tuple(check.blockers or check.warnings),
    )
    return _state(journey, [*journey.steps, step], completion_message="")


def _normalize_deferred(use_case: UseCase, journey: JourneyState) -> JourneyState:
    if use_case.decision_status != UseCase.DecisionStatus.DEFERRED:
        return journey
    return _state(
        journey,
        list(journey.steps),
        completion_message=(
            "Zurückgestellt: Der Use Case bleibt geparkt und kann durch eine neue "
            "Bewertung reaktiviert werden."
        ),
    )


def build_use_case_journey(use_case: UseCase, user) -> JourneyState:
    if _original_build_use_case is None:
        raise RuntimeError("Lean journey projection is not installed.")
    journey = _original_build_use_case(use_case, user)
    journey = _expose_early_negative_decision(use_case, user, journey)
    journey = _normalize_delivery(use_case, user, journey)
    journey = _ensure_pilot_start(use_case, user, journey)
    return _normalize_deferred(use_case, journey)


def install() -> None:
    global _original_build_use_case
    if workflow.build_use_case_journey is build_use_case_journey:
        return
    _original_build_use_case = workflow.build_use_case_journey
    workflow.build_use_case_journey = build_use_case_journey
    legacy.build_use_case_journey = build_use_case_journey
