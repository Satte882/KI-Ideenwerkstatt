from __future__ import annotations

from dataclasses import replace

from django.urls import reverse

from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, ValueStream

from . import journey as legacy
from . import workflow

JourneyState = workflow.JourneyState
JourneyStep = workflow.JourneyStep
ORIGINAL_BUILD_PROCESS = workflow.build_process_analysis_journey
ORIGINAL_BUILD_VALUE_STREAM = workflow.build_value_stream_journey
FOCUS_STAGE_REASON = "Wähle bewusst die Phase aus, deren Prozess im Detail analysiert werden soll."


def _state(
    *,
    path_label: str,
    steps: list[JourneyStep],
    completion_message: str = "",
) -> JourneyState:
    return JourneyState(
        path_label=path_label,
        steps=tuple(steps),
        next_action=next(
            (step for step in steps if step.state in {"current", "blocked"}),
            None,
        ),
        completion_message=completion_message,
    )


def _upcoming_step(step: JourneyStep, reason: str) -> JourneyStep:
    return JourneyStep(
        key=step.key,
        label=step.label,
        state="upcoming",
        action_method=step.action_method,
        reason=reason,
    )


def _guide_phase_completion(
    value_stream: ValueStream,
    journey: JourneyState,
) -> JourneyState:
    steps: list[JourneyStep] = []
    for step in journey.steps:
        if step.key == "value_stream":
            steps.append(
                JourneyStep(
                    key="value_stream",
                    label="Value Stream",
                    state="current",
                    url=reverse(
                        "architecture:stage_create",
                        kwargs={"stream_pk": value_stream.pk},
                    ),
                    action_label="Phase ergänzen",
                    reason=(
                        "Der Value Stream ist noch im Entwurf. Ergänze die groben "
                        "End-to-End-Phasen und setze ihn anschließend auf Aktiv."
                    ),
                )
            )
        elif step.key == "focus":
            steps.append(step)
        else:
            steps.append(
                _upcoming_step(
                    step,
                    "Die Prozessdetailanalyse beginnt erst nach Abschluss der Phasenerfassung.",
                )
            )
    return _state(path_label=journey.path_label, steps=steps)


def _guide_focus_stage_selection(
    value_stream: ValueStream,
    journey: JourneyState,
) -> JourneyState:
    steps: list[JourneyStep] = []
    for step in journey.steps:
        if step.key != "process":
            steps.append(step)
            continue
        steps.append(
            JourneyStep(
                key="process",
                label="Prozessanalyse",
                state="current",
                url=f"{value_stream.get_absolute_url()}#end-to-end-phasen",
                action_label="Fokusphase auswählen",
                reason=FOCUS_STAGE_REASON,
            )
        )
    return _state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=journey.completion_message,
    )


def _guide_solution_choice(
    process_analysis: ProcessAnalysis,
    journey: JourneyState,
) -> JourneyState:
    options = list(process_analysis.solution_options.all())
    if any(option.recommendation == SolutionOption.Recommendation.PREFERRED for option in options):
        steps = [
            replace(step, action_label="Bevorzugte Option als Use Case prüfen")
            if step.key == "use_case" and step.state == "current"
            else step
            for step in journey.steps
        ]
        return _state(
            path_label=journey.path_label,
            steps=steps,
            completion_message=journey.completion_message,
        )

    solution_step = next(
        (step for step in journey.steps if step.key == "solution" and step.state == "current"),
        None,
    )
    if solution_step is None:
        return journey

    if not options:
        guided_solution = replace(
            solution_step,
            url=reverse(
                "architecture:solution_option_create",
                kwargs={"process_pk": process_analysis.pk},
            ),
            action_label="Erste Lösungsoption ergänzen",
            reason=(
                "Noch keine Lösungsoption ist dokumentiert. Erfasse zuerst eine "
                "organisatorische, regelbasierte oder technische Alternative."
            ),
        )
    else:
        option_count = len(options)
        guided_solution = replace(
            solution_step,
            url=reverse(
                "architecture:solution_option_compare",
                kwargs={"pk": process_analysis.pk},
            ),
            action_label="Lösungsoptionen vergleichen",
            reason=(
                f"{option_count} Lösungsoption"
                f"{'en liegen' if option_count != 1 else ' liegt'} vor; "
                "eine bevorzugte Option ist noch nicht festgelegt."
            ),
        )

    steps = [guided_solution if step.key == "solution" else step for step in journey.steps]
    return _state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=journey.completion_message,
    )


def build_value_stream_journey(value_stream: ValueStream, user) -> JourneyState:
    journey = ORIGINAL_BUILD_VALUE_STREAM(value_stream, user)
    has_stages = value_stream.stages.exists()
    has_analysis = ProcessAnalysis.objects.filter(stage__value_stream=value_stream).exists()

    if has_stages and not has_analysis and value_stream.status == ValueStream.Status.DRAFT:
        return _guide_phase_completion(value_stream, journey)

    if (
        has_stages
        and not has_analysis
        and value_stream.status == ValueStream.Status.ACTIVE
        and any(step.key == "process" and step.state == "current" for step in journey.steps)
    ):
        return _guide_focus_stage_selection(value_stream, journey)

    return journey


def build_process_analysis_journey(
    process_analysis: ProcessAnalysis,
    user,
) -> JourneyState:
    journey = ORIGINAL_BUILD_PROCESS(process_analysis, user)
    return _guide_solution_choice(process_analysis, journey)


def install() -> None:
    workflow.build_value_stream_journey = build_value_stream_journey
    workflow.build_process_analysis_journey = build_process_analysis_journey
    legacy.build_value_stream_journey = build_value_stream_journey
    legacy.build_process_analysis_journey = build_process_analysis_journey
