from __future__ import annotations

from dataclasses import replace

from django.urls import reverse

from . import journey as legacy
from . import workflow

JourneyState = workflow.JourneyState
JourneyStep = workflow.JourneyStep

_original_build_use_case = None


def _state(journey: JourneyState, steps: list[JourneyStep]) -> JourneyState:
    return JourneyState(
        path_label=journey.path_label,
        steps=tuple(steps),
        next_action=next(
            (step for step in steps if step.state in {"current", "blocked"}),
            None,
        ),
        completion_message=journey.completion_message,
    )


def _normalize_second_approval_action(use_case, journey: JourneyState) -> JourneyState:
    approval = use_case.approval_decisions.first()
    if approval is None or not approval.is_pending_second_approval:
        return journey

    steps: list[JourneyStep] = []
    changed = False
    for step in journey.steps:
        if step.key == "approval" and step.state == "blocked":
            steps.append(
                replace(
                    step,
                    url=reverse(
                        "use_cases:second_approval_review",
                        kwargs={"decision_id": approval.pk},
                    ),
                    action_label="Zweitprüfung öffnen",
                    action_method="get",
                )
            )
            changed = True
        else:
            steps.append(step)

    return _state(journey, steps) if changed else journey


def build_use_case_journey(use_case, user) -> JourneyState:
    if _original_build_use_case is None:
        raise RuntimeError("Primary actions are not installed.")
    journey = _original_build_use_case(use_case, user)
    return _normalize_second_approval_action(use_case, journey)


def install() -> None:
    global _original_build_use_case
    if workflow.build_use_case_journey is build_use_case_journey:
        return
    _original_build_use_case = workflow.build_use_case_journey
    workflow.build_use_case_journey = build_use_case_journey
    legacy.build_use_case_journey = build_use_case_journey
