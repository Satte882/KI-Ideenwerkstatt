from __future__ import annotations

from dataclasses import replace

from ki_radar.delivery.handover import recorded_handover_package

from . import outcome_workspace
from .models import UseCase

_original_build_outcome = None


def build_outcome_workspace_journey(use_case: UseCase, user):
    if _original_build_outcome is None:
        raise RuntimeError("Lean outcome projection is not installed.")
    journey = _original_build_outcome(use_case, user)

    recorded_handover = recorded_handover_package(use_case)
    end_recorded = False
    if use_case.status == UseCase.Status.ENDED:
        end_recorded = use_case.reviews.filter(
            decision="end",
            previous_status__in=(UseCase.Status.PILOT, UseCase.Status.OPERATION),
            new_status=UseCase.Status.ENDED,
        ).exists()

    if recorded_handover is None and not end_recorded:
        return journey

    closure_details = []
    if end_recorded:
        if not str(use_case.ending_reason or "").strip():
            closure_details.append("Readiness offen: Beendigungsgrund")
        if not str(use_case.data_and_access_handling or "").strip():
            closure_details.append("Readiness offen: Umgang mit Daten und Zugängen")

    steps = []
    for step in journey.steps:
        if step.key == "handover" and recorded_handover is not None:
            steps.append(
                replace(
                    step,
                    state="complete",
                    url=recorded_handover.get_absolute_url(),
                    action_label="Übergabe öffnen",
                    reason=(
                        f"Delivery Package v{recorded_handover.version} wurde verbindlich "
                        "übergeben."
                    ),
                    details=(),
                )
            )
        elif step.key == "closure" and end_recorded:
            steps.append(
                replace(
                    step,
                    state="complete",
                    action_label="Abschluss öffnen",
                    reason=(
                        "Der Use Case ist fachlich beendet. Offene Abschlussinformationen "
                        "bleiben als Readiness sichtbar und ändern den Lifecycle nicht."
                    ),
                    details=tuple(closure_details),
                )
            )
        else:
            steps.append(step)

    completion_message = (
        "Lebenszyklus abgeschlossen: Das Vorhaben ist fachlich beendet."
        if end_recorded
        else journey.completion_message
    )
    return outcome_workspace._state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=completion_message,
    )


def install() -> None:
    global _original_build_outcome
    if outcome_workspace.build_outcome_workspace_journey is build_outcome_workspace_journey:
        return
    _original_build_outcome = outcome_workspace.build_outcome_workspace_journey
    outcome_workspace.build_outcome_workspace_journey = build_outcome_workspace_journey
