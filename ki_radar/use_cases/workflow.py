from __future__ import annotations

from urllib.parse import urlencode

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus, get_value_stream_focus
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.architecture.strategic_exploration import (
    has_strategic_exploration,
    strategic_binding_basis,
)
from ki_radar.delivery.actions import primary_delivery_action
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.permissions import can_transition_package

from . import journey as legacy
from .permissions import can_start_pilot
from .services import check_pilot_start

JourneyState = legacy.JourneyState
JourneyStep = legacy.JourneyStep
LEGACY_BUILD_USE_CASE = legacy.build_use_case_journey
LEGACY_BUILD_PROCESS = legacy.build_process_analysis_journey
LEGACY_BUILD_VALUE_STREAM = legacy.build_value_stream_journey


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


def _focus_step(value_stream: ValueStream, *, terminal_as_complete: bool = False) -> JourneyStep:
    focus = get_value_stream_focus(value_stream)
    edit_url = reverse("architecture:value_stream_update", kwargs={"pk": value_stream.pk})
    if focus is None:
        return JourneyStep(
            key="focus",
            label="Fokus & Priorisierung",
            state="blocked",
            url=edit_url,
            action_label="Screening ergänzen",
            reason=(
                "Der Value Stream wurde noch nicht anhand einheitlicher Fokus-Kriterien bewertet."
            ),
            details=("Fachdomäne", "Business Capability", "Impact, Potenzial, Daten und Aufwand"),
        )
    if focus.missing_screening_fields:
        return JourneyStep(
            key="focus",
            label="Fokus & Priorisierung",
            state="blocked",
            url=edit_url,
            action_label="Screening vervollständigen",
            reason="Die Fokusentscheidung ist noch nicht belastbar dokumentiert.",
            details=focus.missing_screening_fields,
        )
    if focus.status == ValueStreamFocus.Status.SELECTED:
        return JourneyStep(
            key="focus",
            label="Fokus & Priorisierung",
            state="complete",
            url=value_stream.get_absolute_url(),
            action_label="Fokusentscheidung öffnen",
            reason="Der Value Stream wurde für einen Deep Dive ausgewählt.",
        )
    if focus.status == ValueStreamFocus.Status.CANDIDATE:
        return JourneyStep(
            key="focus",
            label="Fokus & Priorisierung",
            state="current",
            url=edit_url,
            action_label="Fokusentscheidung treffen",
            reason="Das Screening ist vollständig; die Auswahlentscheidung steht noch aus.",
        )
    if focus.is_terminal:
        return JourneyStep(
            key="focus",
            label="Fokus & Priorisierung",
            state="complete" if terminal_as_complete else "optional",
            url=value_stream.get_absolute_url(),
            action_label="Fokusentscheidung öffnen",
            reason=f"Fokusentscheidung: {focus.get_status_display()}.",
        )
    return JourneyStep(
        key="focus",
        label="Fokus & Priorisierung",
        state="current",
        url=edit_url,
        action_label="Value Stream bewerten",
        reason="Impact, Potenzial, Datenzugänglichkeit und Veränderungsaufwand bewerten.",
    )


def _insert_focus(journey: JourneyState, focus_step: JourneyStep) -> JourneyState:
    steps = [step for step in journey.steps if step.key != "focus"]
    insert_at = next(
        (index + 1 for index, step in enumerate(steps) if step.key == "value_stream"),
        0,
    )
    steps.insert(insert_at, focus_step)
    return _state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=journey.completion_message,
    )


def pilot_start_url(use_case) -> str:
    query = urlencode({"action": "pilot_start"})
    return f"{reverse('reviews:create', kwargs={'use_case_id': use_case.pk})}?{query}"


def _append_pilot_start(journey: JourneyState, use_case, user) -> JourneyState:
    if use_case.status != use_case.Status.REVIEW:
        return journey
    delivery_step = next((step for step in journey.steps if step.key == "delivery"), None)
    if delivery_step is None or delivery_step.state != "complete":
        return journey

    check = check_pilot_start(use_case)
    allowed = can_start_pilot(user, use_case)
    reason = "Die Übergabe ist erfolgt; der tatsächliche Pilotbeginn muss bestätigt werden."
    if not allowed:
        reason += " Nur ein KI-Koordinator oder der zuständige Business Owner darf starten."
    step = JourneyStep(
        key="pilot_start",
        label="Pilot starten",
        state="blocked" if check.blockers else "current",
        url=pilot_start_url(use_case) if allowed else None,
        action_label="Pilot starten" if allowed else "",
        reason=reason,
        details=tuple(check.blockers),
    )
    return _state(
        path_label=journey.path_label,
        steps=[*journey.steps, step],
        completion_message="",
    )


def _focus_terminal_journey(value_stream: ValueStream, focus: ValueStreamFocus) -> JourneyState:
    stages = list(value_stream.stages.all())
    steps = [
        JourneyStep(
            key="value_stream",
            label="Value Stream",
            state="complete" if stages else "current",
            url=value_stream.get_absolute_url(),
            reason=(
                f"{len(stages)} End-to-End-Phasen sind erfasst."
                if stages
                else "Die End-to-End-Phasen sind noch nicht erfasst."
            ),
        ),
        _focus_step(value_stream, terminal_as_complete=True),
        JourneyStep(
            key="process",
            label="Prozessanalyse",
            state="optional",
            reason="Für einen nicht ausgewählten Value Stream ist kein Deep Dive erforderlich.",
        ),
        JourneyStep(key="solution", label="Lösungsoption", state="optional"),
        JourneyStep(key="use_case", label="Use Case", state="optional"),
        JourneyStep(key="assessment", label="Bewertung", state="optional"),
        JourneyStep(key="approval", label="Freigabe", state="optional"),
        JourneyStep(key="delivery", label="Delivery", state="optional"),
    ]
    return _state(
        path_label="Systematische Discovery",
        steps=steps,
        completion_message=f"Discovery beendet: {focus.get_status_display()}.",
    )


def build_value_stream_journey(value_stream: ValueStream, user) -> JourneyState:
    focus = get_value_stream_focus(value_stream)
    if focus is not None and focus.is_terminal:
        return _focus_terminal_journey(value_stream, focus)

    if focus is None or not focus.is_selected:
        for process in ProcessAnalysis.objects.filter(stage__value_stream=value_stream):
            if has_strategic_exploration(process):
                return build_process_analysis_journey(process, user)

    legacy_journey = LEGACY_BUILD_VALUE_STREAM(value_stream, user)
    focus_step = _focus_step(value_stream)
    if focus is None or not focus.is_selected:
        steps = []
        for step in legacy_journey.steps:
            if step.key == "value_stream":
                steps.append(step)
                steps.append(focus_step)
                continue
            steps.append(
                JourneyStep(
                    key=step.key,
                    label=step.label,
                    state="upcoming",
                    action_method=step.action_method,
                    reason="Der Deep Dive beginnt erst nach der Auswahl des Value Streams.",
                )
            )
        if not any(step.key == "focus" for step in steps):
            steps.insert(1 if steps else 0, focus_step)
        return _state(path_label="Systematische Discovery", steps=steps)
    return _insert_focus(legacy_journey, focus_step)


def build_process_analysis_journey(process_analysis: ProcessAnalysis, user) -> JourneyState:
    value_stream = process_analysis.stage.value_stream
    focus = get_value_stream_focus(value_stream)
    if focus is not None and focus.is_terminal:
        return _focus_terminal_journey(value_stream, focus)
    if (focus is None or not focus.is_selected) and has_strategic_exploration(process_analysis):
        return _strategic_draft_journey(process_analysis, user)
    legacy_journey = LEGACY_BUILD_PROCESS(process_analysis, user)
    focus_step = _focus_step(value_stream)
    if focus is None or not focus.is_selected:
        steps = []
        for step in legacy_journey.steps:
            if step.key == "value_stream":
                steps.append(step)
                steps.append(focus_step)
            else:
                steps.append(
                    JourneyStep(
                        key=step.key,
                        label=step.label,
                        state="upcoming",
                        action_method=step.action_method,
                        reason="Der Deep Dive ist bis zur Fokusentscheidung zurückgestellt.",
                    )
                )
        return _state(path_label="Systematische Discovery", steps=steps)
    return _insert_focus(legacy_journey, focus_step)


def _strategic_draft_journey(process, user) -> JourneyState:
    decision = process.solution_selection_decisions.select_related("selected_option").first()
    if decision is not None:
        can_edit = can_edit_value_stream(user, process.stage.value_stream)
        comparison_url = reverse("architecture:solution_option_compare", args=[process.pk])
        stale = decision.outcome_review_required
        if not stale and decision.selected_option.starts_ai_use_case:
            origin = process.use_case_origins.select_related("use_case").first()
            if origin:
                return build_use_case_journey(origin.use_case, user)
        if stale or decision.selected_option.starts_ai_use_case:
            return _state(
                path_label="Strategische Auswahl",
                steps=[
                    JourneyStep(
                        key="solution",
                        label="Lösungsentscheidung",
                        state="blocked" if stale else "current",
                        url=comparison_url if can_edit else None,
                        action_label="Auswahl erneut prüfen" if stale else "KI-Handoff fortsetzen",
                        reason="Entscheidungsgrundlage erneut prüfen."
                        if stale
                        else "KI-Use-Case ableiten.",
                    )
                ],
            )
        try:
            review_current = not process.initiative.impact_review.review_required
        except ObjectDoesNotExist:
            review_current = False
        completed = process.initiative.status in {"completed", "cancelled"} and review_current
        return _state(
            path_label="Strategische Non-KI-Umsetzung",
            steps=[
                JourneyStep(
                    key="solution",
                    label="Lösungsentscheidung",
                    state="complete",
                    url=comparison_url,
                    reason="Non-KI bewusst ausgewählt; Umsetzung extern.",
                ),
                JourneyStep(
                    key="impact",
                    label="Gemeinsame Wirkungsprüfung",
                    state="complete" if completed else "current",
                    url=reverse("use_cases:initiative_impact", args=[process.initiative_id])
                    if can_edit
                    else process.initiative.get_absolute_url(),
                    action_label="Externen Umsetzungs- und Wirkungsstand prüfen"
                    if can_edit
                    else "",
                    reason="Prozesswirkung, Geschäftsergebnis und Attribution getrennt beurteilen.",
                ),
            ],
            completion_message="Vorhaben mit dokumentiertem Wirkungsstand beendet."
            if completed
            else "",
        )
    binding = strategic_binding_basis(process)
    can_edit = can_edit_value_stream(user, process.stage.value_stream)
    has_options = process.solution_options.filter(retirement__isnull=True).exists()
    comparison_url = reverse("architecture:solution_option_compare", args=[process.pk])
    return _state(
        path_label="Strategische Exploration",
        steps=[
            JourneyStep(
                key="value_stream",
                label="Untersuchungsrahmen",
                state="complete",
                url=process.stage.value_stream.get_absolute_url(),
                reason="Menschlicher strategischer Scope dokumentiert; keine Screeningbestätigung.",
            ),
            JourneyStep(
                key="process",
                label="Prozessentwurf",
                state="complete" if has_options else "current",
                url=reverse("architecture:process_analysis_update", args=[process.pk])
                if can_edit
                else None,
                action_label="Prozessentwurf bearbeiten" if can_edit else "",
                reason="Ist-Daten dürfen unbekannt bleiben. Der Entwurf erteilt keine Freigabe.",
            ),
            JourneyStep(
                key="solution",
                label="Optionsentwürfe",
                state="current" if has_options else "upcoming",
                url=(
                    comparison_url
                    if has_options
                    else reverse("architecture:solution_option_create", args=[process.pk])
                )
                if can_edit
                else None,
                action_label=(
                    "Optionsentwürfe vergleichen" if has_options else "Optionsentwurf anlegen"
                )
                if can_edit
                else "",
                reason="Unverbindlich weiterarbeiten; Evidenz, Aufwand und Wirkung bleiben offen.",
            ),
            JourneyStep(
                key="focus",
                label="Bindende Auswahl",
                state="upcoming" if binding else "blocked",
                url=comparison_url if can_edit else None,
                action_label="Auswahlvoraussetzungen prüfen" if can_edit else "",
                reason=(
                    "Bestätigten strategischen Rahmen, Vergleich und offene Screeningfragen prüfen."
                    if binding
                    else "Vor Auswahl Outcome-, Phasen- und Strategiepfadbezug bestätigen."
                ),
            ),
        ],
    )


def _normalize_concrete_links(journey: JourneyState, use_case) -> JourneyState:
    steps: list[JourneyStep] = []
    for step in journey.steps:
        url = step.url
        action_label = step.action_label
        if step.key == "use_case" and step.state == "complete":
            url = use_case.get_absolute_url()
            action_label = action_label or "Use Case öffnen"
        elif step.key == "assessment" and step.state == "complete":
            url = f"{use_case.get_absolute_url()}#assessment"
            action_label = "Bewertung ansehen"
        elif step.key == "approval" and step.state == "complete":
            url = f"{use_case.get_absolute_url()}#decision-history"
            action_label = "Freigabe ansehen"
        steps.append(
            JourneyStep(
                key=step.key,
                label=step.label,
                state=step.state,
                url=url,
                action_label=action_label,
                action_method=step.action_method,
                reason=step.reason,
                details=step.details,
            )
        )
    return _state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=journey.completion_message,
    )


def _apply_delivery_action(journey: JourneyState, use_case, user) -> JourneyState:
    package = use_case.delivery_packages.first()
    if package is None or package.status != DeliveryPackage.Status.DRAFT:
        return journey

    primary = primary_delivery_action(package, user)
    steps: list[JourneyStep] = []
    for step in journey.steps:
        if step.key != "delivery":
            steps.append(step)
            continue
        if primary is not None:
            if primary.url:
                url = primary.url
                action_label = primary.action_label
                reason = primary.message
            else:
                url = package.get_absolute_url()
                action_label = "Readiness öffnen"
                reason = (
                    f"{primary.message} Zuständig: {primary.responsible_role} - "
                    f"{primary.responsible_person}."
                )
            steps.append(
                JourneyStep(
                    key="delivery",
                    label="Delivery",
                    state="blocked",
                    url=url,
                    action_label=action_label,
                    reason=reason,
                    details=(),
                )
            )
            continue
        transition_allowed = can_transition_package(user)
        steps.append(
            JourneyStep(
                key="delivery",
                label="Delivery",
                state="current",
                url=(
                    reverse("delivery:package_mark_ready", kwargs={"pk": package.pk})
                    if transition_allowed
                    else package.get_absolute_url()
                ),
                action_label="Als bereit markieren" if transition_allowed else "Readiness öffnen",
                action_method="post" if transition_allowed else "get",
                reason=(
                    (
                        "Alle Pflichtinhalte und Bestätigungen liegen vor. "
                        "Das Package kann als bereit markiert werden."
                    )
                    if transition_allowed
                    else (
                        "Alle Pflichtinhalte und Bestätigungen liegen vor; "
                        "ein KI-Koordinator kann das Package als bereit markieren."
                    )
                ),
            )
        )
    return _state(
        path_label=journey.path_label,
        steps=steps,
        completion_message=journey.completion_message,
    )


def build_use_case_journey(use_case, user) -> JourneyState:
    legacy_journey = LEGACY_BUILD_USE_CASE(use_case, user)
    try:
        origin = use_case.architecture_origin
    except ObjectDoesNotExist:
        origin = None
    if origin is None:
        steps = [
            JourneyStep(
                key="value_stream",
                label="Discovery",
                state="optional",
                reason="Der Use Case wurde direkt erfasst.",
            ),
            JourneyStep(
                key="focus",
                label="Fokus & Priorisierung",
                state="optional",
                reason="Direkter Intake ohne vorgelagertes Value-Stream-Screening.",
            ),
            *legacy_journey.steps,
        ]
        journey = _state(
            path_label=legacy_journey.path_label,
            steps=steps,
            completion_message=legacy_journey.completion_message,
        )
    else:
        journey = _insert_focus(
            legacy_journey,
            _focus_step(origin.stage.value_stream),
        )
    journey = _normalize_concrete_links(journey, use_case)
    journey = _apply_delivery_action(journey, use_case, user)
    return _append_pilot_start(journey, use_case, user)


def build_delivery_package_journey(package: DeliveryPackage, user) -> JourneyState:
    return build_use_case_journey(package.use_case, user)


def install() -> None:
    legacy.build_value_stream_journey = build_value_stream_journey
    legacy.build_process_analysis_journey = build_process_analysis_journey
    legacy.build_use_case_journey = build_use_case_journey
    legacy.build_delivery_package_journey = build_delivery_package_journey
