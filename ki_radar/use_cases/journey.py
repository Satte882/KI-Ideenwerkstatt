from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from ki_radar.accounts.permissions import (
    is_business_owner_or_coordinator,
    is_coordinator,
)
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, ValueStream
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.readiness import blocking_findings, delivery_status_snapshot
from ki_radar.delivery.services import latest_final_approval, missing_ready_fields

from .blockers import build_blocker_details
from .models import UseCase
from .permissions import can_edit_use_case
from .services import intake_blockers


@dataclass(frozen=True)
class JourneyStep:
    key: str
    label: str
    state: str
    url: str | None = None
    action_label: str = ""
    action_method: str = "get"
    reason: str = ""
    details: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class JourneyState:
    path_label: str
    steps: tuple[JourneyStep, ...]
    next_action: JourneyStep | None
    completion_message: str = ""


PROCESS_REQUIRED_FIELDS = (
    "scope_start",
    "scope_end",
    "trigger",
    "outcome",
    "current_flow",
    "roles",
    "systems",
    "data_objects",
    "bottlenecks",
    "baseline_metrics",
)

FINAL_NEGATIVE_STATUSES = {
    UseCase.DecisionStatus.DEFERRED,
    UseCase.DecisionStatus.NOT_PURSUED,
}


def _next_action(steps: list[JourneyStep]) -> JourneyStep | None:
    return next((step for step in steps if step.state in {"current", "blocked"}), None)


def _state(
    *,
    path_label: str,
    steps: list[JourneyStep],
    completion_message: str = "",
) -> JourneyState:
    return JourneyState(
        path_label=path_label,
        steps=tuple(steps),
        next_action=_next_action(steps),
        completion_message=completion_message,
    )


def _permission_reason(allowed: bool, reason: str) -> str:
    if allowed:
        return reason
    return f"{reason} Eine berechtigte Rolle muss diesen Schritt ausführen."


def _use_case_steps(use_case: UseCase, user) -> tuple[list[JourneyStep], str]:
    can_edit = can_edit_use_case(user, use_case)
    can_decide = is_coordinator(user)
    can_manage_delivery = is_business_owner_or_coordinator(user)
    final_negative = use_case.decision_status in FINAL_NEGATIVE_STATUSES

    blockers = [] if final_negative else intake_blockers(use_case)
    blocker_details = build_blocker_details(use_case, blockers)
    first_blocker = blocker_details[0] if blocker_details else None

    steps: list[JourneyStep] = []
    if blockers:
        steps.append(
            JourneyStep(
                key="use_case",
                label="Use Case",
                state="blocked",
                url=first_blocker.target_href if first_blocker and can_edit else None,
                action_label=first_blocker.action_label if first_blocker and can_edit else "",
                reason=_permission_reason(
                    can_edit,
                    "Die Intake-Angaben sind noch nicht vollständig.",
                ),
                details=tuple(blockers),
            )
        )
    else:
        steps.append(
            JourneyStep(
                key="use_case",
                label="Use Case",
                state="complete",
                url=use_case.get_absolute_url(),
                action_label="Use Case öffnen",
                reason="Die erforderlichen Intake-Angaben liegen vor.",
            )
        )

    latest_assessment = use_case.decision_assessments.first()
    latest_approval = use_case.approval_decisions.first()
    final_positive_approval = latest_final_approval(use_case)

    if final_negative and latest_assessment is None:
        steps.append(
            JourneyStep(
                key="assessment",
                label="Bewertung",
                state="optional",
                reason="Das Vorhaben wurde beendet; eine weitere Bewertung ist nicht erforderlich.",
            )
        )
    elif blockers:
        steps.append(
            JourneyStep(
                key="assessment",
                label="Bewertung",
                state="upcoming",
                reason="Die Bewertung beginnt nach einem vollständigen Intake.",
            )
        )
    elif latest_assessment is None:
        steps.append(
            JourneyStep(
                key="assessment",
                label="Bewertung",
                state="current",
                url=(
                    reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk})
                    if can_decide
                    else None
                ),
                action_label="Bewertung anlegen" if can_decide else "",
                reason=_permission_reason(
                    can_decide,
                    "Eine strukturierte, versionierte Bewertung fehlt.",
                ),
            )
        )
    else:
        steps.append(
            JourneyStep(
                key="assessment",
                label="Bewertung",
                state="complete",
                url=reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk}),
                action_label="Bewertung öffnen",
                reason=f"Bewertungsversion {latest_assessment.version} liegt vor.",
            )
        )

    if final_negative:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="complete",
                url=use_case.get_absolute_url(),
                action_label="Entscheidung öffnen",
                reason=f"Finale Entscheidung: {use_case.get_decision_status_display()}.",
            )
        )
    elif latest_assessment is None:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="upcoming",
                reason="Eine Freigabeentscheidung setzt eine Bewertung voraus.",
            )
        )
    elif latest_approval and latest_approval.is_pending_second_approval:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="blocked",
                url=use_case.get_absolute_url(),
                action_label="Zweitfreigabe öffnen",
                reason="Die Freigabe mit Auflagen benötigt eine zweite unabhängige Bestätigung.",
            )
        )
    elif final_positive_approval is not None:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="complete",
                url=use_case.get_absolute_url(),
                action_label="Freigabe öffnen",
                reason=f"Finale Entscheidung: {final_positive_approval.get_decision_status_display()}.",
            )
        )
    elif use_case.decision_status in {
        UseCase.DecisionStatus.APPROVED,
        UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    }:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="blocked",
                url=use_case.get_absolute_url(),
                action_label="Freigabe prüfen",
                reason="Der positive Entscheidungsstatus ist noch nicht durch eine finale Freigabe dokumentiert.",
            )
        )
    else:
        steps.append(
            JourneyStep(
                key="approval",
                label="Freigabe",
                state="current",
                url=(
                    reverse("use_cases:approval_decision_create", kwargs={"pk": use_case.pk})
                    if can_decide
                    else None
                ),
                action_label="Freigabe entscheiden" if can_decide else "",
                reason=_permission_reason(
                    can_decide,
                    "Die Bewertung liegt vor; eine finale Entscheidung fehlt.",
                ),
            )
        )

    package = use_case.delivery_packages.first()
    completion_message = ""
    if final_negative:
        steps.append(
            JourneyStep(
                key="delivery",
                label="Delivery",
                state="optional",
                reason="Für ein nicht weiterverfolgtes oder zurückgestelltes Vorhaben ist kein Delivery Package erforderlich.",
            )
        )
        completion_message = f"Journey beendet: {use_case.get_decision_status_display()}."
    elif final_positive_approval is None:
        steps.append(
            JourneyStep(
                key="delivery",
                label="Delivery",
                state="upcoming",
                reason="Ein Delivery Package kann erst nach einer finalen positiven Freigabe entstehen.",
            )
        )
    elif package is None:
        steps.append(
            JourneyStep(
                key="delivery",
                label="Delivery",
                state="current",
                url=(
                    reverse("delivery:package_create", kwargs={"use_case_id": use_case.pk})
                    if can_manage_delivery
                    else None
                ),
                action_label="Delivery Package erzeugen" if can_manage_delivery else "",
                action_method="post",
                reason=_permission_reason(
                    can_manage_delivery,
                    "Die finale Freigabe liegt vor; das Delivery Package fehlt.",
                ),
            )
        )
    elif package.status == DeliveryPackage.Status.HANDED_OVER:
        status_snapshot = delivery_status_snapshot(package)
        if status_snapshot.handover_complete:
            steps.append(
                JourneyStep(
                    key="delivery",
                    label="Delivery",
                    state="complete",
                    url=package.get_absolute_url(),
                    action_label="Übergabe öffnen",
                    reason=(
                        f"Delivery Package v{package.version} wurde übergeben und ist "
                        "unveränderlich."
                    ),
                )
            )
            completion_message = "Journey abgeschlossen: Das Vorhaben wurde an Delivery übergeben."
        else:
            blocker_messages = tuple(finding.message for finding in blocking_findings(package)) or (
                "Verbindlicher Übergabezeitpunkt",
            )
            steps.append(
                JourneyStep(
                    key="delivery",
                    label="Delivery",
                    state="blocked",
                    url=package.get_absolute_url(),
                    action_label="Übergabe prüfen",
                    reason=status_snapshot.label,
                    details=blocker_messages,
                )
            )
    elif package.status == DeliveryPackage.Status.READY:
        status_snapshot = delivery_status_snapshot(package)
        if status_snapshot.code == DeliveryPackage.Status.READY:
            steps.append(
                JourneyStep(
                    key="delivery",
                    label="Delivery",
                    state="current",
                    url=(
                        reverse("delivery:package_handover", kwargs={"pk": package.pk})
                        if can_decide
                        else package.get_absolute_url()
                    ),
                    action_label=(
                        "An Delivery übergeben" if can_decide else "Delivery Package öffnen"
                    ),
                    action_method="post" if can_decide else "get",
                    reason=_permission_reason(
                        can_decide,
                        (
                            "Das Delivery Package ist vollständig und bereit zur verbindlichen "
                            "Übergabe."
                        ),
                    ),
                )
            )
        else:
            steps.append(
                JourneyStep(
                    key="delivery",
                    label="Delivery",
                    state="blocked",
                    url=package.get_absolute_url(),
                    action_label="Readiness prüfen",
                    reason=status_snapshot.label,
                    details=tuple(finding.message for finding in blocking_findings(package)),
                )
            )
    else:
        missing = missing_ready_fields(package)
        steps.append(
            JourneyStep(
                key="delivery",
                label="Delivery",
                state="blocked" if missing else "current",
                url=package.get_absolute_url(),
                action_label="Delivery Package vervollständigen",
                reason=(
                    "Das Delivery Package enthält noch unvollständige Pflichtbereiche."
                    if missing
                    else "Das Delivery Package kann als bereit markiert werden."
                ),
                details=tuple(missing),
            )
        )

    return steps, completion_message


def build_use_case_journey(use_case: UseCase, user) -> JourneyState:
    try:
        origin = use_case.architecture_origin
    except ObjectDoesNotExist:
        origin = None

    steps: list[JourneyStep] = []
    path_label = "Direkter Intake"
    if origin is not None:
        path_label = f"Aus Value Stream „{origin.stage.value_stream.name}“ abgeleitet"
        steps.append(
            JourneyStep(
                key="value_stream",
                label="Value Stream",
                state="complete",
                url=origin.stage.value_stream.get_absolute_url(),
                action_label="Value Stream öffnen",
                reason=f"Herkunft: Phase „{origin.stage.name}“.",
            )
        )
        if origin.process_analysis is not None:
            steps.append(
                JourneyStep(
                    key="process",
                    label="Prozessanalyse",
                    state="complete",
                    url=origin.process_analysis.get_absolute_url(),
                    action_label="Prozessanalyse öffnen",
                    reason="Der relevante Detailprozess ist dokumentiert.",
                )
            )
        else:
            steps.append(
                JourneyStep(
                    key="process",
                    label="Prozessanalyse",
                    state="optional",
                    reason="Der Use Case wurde direkt aus einer Value-Stream-Phase abgeleitet.",
                )
            )
        if origin.solution_option is not None:
            steps.append(
                JourneyStep(
                    key="solution",
                    label="Lösungsoption",
                    state="complete",
                    url=origin.process_analysis.get_absolute_url()
                    if origin.process_analysis
                    else origin.stage.value_stream.get_absolute_url(),
                    action_label="Lösungsoption öffnen",
                    reason=f"Bevorzugte Option: {origin.solution_option.name}.",
                )
            )
        else:
            steps.append(
                JourneyStep(
                    key="solution",
                    label="Lösungsoption",
                    state="optional",
                    reason="Für die direkte Ableitung aus der Phase wurde keine Lösungsoption verknüpft.",
                )
            )

    tail, completion_message = _use_case_steps(use_case, user)
    steps.extend(tail)
    return _state(
        path_label=path_label,
        steps=steps,
        completion_message=completion_message,
    )


def _missing_process_fields(process_analysis: ProcessAnalysis) -> list[str]:
    labels = {field.name: str(field.verbose_name) for field in process_analysis._meta.fields}
    return [
        labels[field_name]
        for field_name in PROCESS_REQUIRED_FIELDS
        if not str(getattr(process_analysis, field_name, "")).strip()
    ]


def build_process_analysis_journey(process_analysis: ProcessAnalysis, user) -> JourneyState:
    origin = process_analysis.use_case_origins.select_related("use_case").first()
    if origin is not None:
        return build_use_case_journey(origin.use_case, user)

    can_manage = is_business_owner_or_coordinator(user)
    value_stream = process_analysis.stage.value_stream
    steps = [
        JourneyStep(
            key="value_stream",
            label="Value Stream",
            state="complete",
            url=value_stream.get_absolute_url(),
            action_label="Value Stream öffnen",
            reason=f"Phase „{process_analysis.stage.name}“ ist eingeordnet.",
        )
    ]

    missing = _missing_process_fields(process_analysis)
    if missing:
        steps.append(
            JourneyStep(
                key="process",
                label="Prozessanalyse",
                state="blocked",
                url=(
                    reverse(
                        "architecture:process_analysis_update",
                        kwargs={"pk": process_analysis.pk},
                    )
                    if can_manage
                    else None
                ),
                action_label="Prozessanalyse vervollständigen" if can_manage else "",
                reason=_permission_reason(
                    can_manage,
                    "Für eine belastbare Lösungswahl fehlen Prozessinformationen.",
                ),
                details=tuple(missing),
            )
        )
        steps.extend(
            [
                JourneyStep(
                    key="solution",
                    label="Lösungsoption",
                    state="upcoming",
                    reason="Lösungsoptionen folgen nach einer vollständigen Prozessanalyse.",
                ),
                JourneyStep(key="use_case", label="Use Case", state="upcoming"),
                JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
                JourneyStep(key="approval", label="Freigabe", state="upcoming"),
                JourneyStep(key="delivery", label="Delivery", state="upcoming"),
            ]
        )
        return _state(path_label="Systematische Discovery", steps=steps)

    steps.append(
        JourneyStep(
            key="process",
            label="Prozessanalyse",
            state="complete",
            url=process_analysis.get_absolute_url(),
            action_label="Prozessanalyse öffnen",
            reason="Die entscheidungsrelevanten Prozessinformationen liegen vor.",
        )
    )

    preferred = process_analysis.solution_options.filter(
        recommendation=SolutionOption.Recommendation.PREFERRED
    ).first()
    if preferred is None:
        steps.append(
            JourneyStep(
                key="solution",
                label="Lösungsoption",
                state="current",
                url=(
                    reverse(
                        "architecture:solution_option_create",
                        kwargs={"process_pk": process_analysis.pk},
                    )
                    if can_manage
                    else None
                ),
                action_label="Lösungsoptionen vergleichen" if can_manage else "",
                reason=_permission_reason(
                    can_manage,
                    "Es ist noch keine Lösungsoption ausdrücklich bevorzugt.",
                ),
            )
        )
        steps.extend(
            [
                JourneyStep(key="use_case", label="Use Case", state="upcoming"),
                JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
                JourneyStep(key="approval", label="Freigabe", state="upcoming"),
                JourneyStep(key="delivery", label="Delivery", state="upcoming"),
            ]
        )
        return _state(path_label="Systematische Discovery", steps=steps)

    steps.append(
        JourneyStep(
            key="solution",
            label="Lösungsoption",
            state="complete",
            url=process_analysis.get_absolute_url(),
            action_label="Lösungsoption öffnen",
            reason=f"Bevorzugte Option: {preferred.name}.",
        )
    )

    if not preferred.starts_ai_use_case:
        steps.extend(
            [
                JourneyStep(
                    key="use_case",
                    label="Use Case",
                    state="optional",
                    reason="Die bevorzugte Option ist keine KI-Initiative; ein KI-Use-Case wird bewusst nicht angelegt.",
                ),
                JourneyStep(key="assessment", label="Bewertung", state="optional"),
                JourneyStep(key="approval", label="Freigabe", state="optional"),
                JourneyStep(key="delivery", label="Delivery", state="optional"),
            ]
        )
        return _state(
            path_label="Systematische Discovery",
            steps=steps,
            completion_message="Analyse abgeschlossen: Eine einfachere Nicht-KI-Lösung wurde bevorzugt.",
        )

    can_create_use_case = is_business_owner_or_coordinator(user)
    steps.append(
        JourneyStep(
            key="use_case",
            label="Use Case",
            state="current",
            url=(
                reverse(
                    "architecture:solution_option_start_use_case",
                    kwargs={"pk": preferred.pk},
                )
                if can_create_use_case
                else None
            ),
            action_label="Als Use Case prüfen" if can_create_use_case else "",
            reason=_permission_reason(
                can_create_use_case,
                "Die bevorzugte KI-Lösungsoption kann in den Intake überführt werden.",
            ),
        )
    )
    steps.extend(
        [
            JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
            JourneyStep(key="approval", label="Freigabe", state="upcoming"),
            JourneyStep(key="delivery", label="Delivery", state="upcoming"),
        ]
    )
    return _state(path_label="Systematische Discovery", steps=steps)


def build_value_stream_journey(value_stream: ValueStream, user) -> JourneyState:
    can_manage = is_business_owner_or_coordinator(user)
    stages = list(value_stream.stages.all())
    analyses = list(
        ProcessAnalysis.objects.filter(stage__value_stream=value_stream)
        .select_related("stage__value_stream")
        .prefetch_related("solution_options", "use_case_origins__use_case")
    )

    for analysis in analyses:
        preferred = analysis.solution_options.filter(
            recommendation=SolutionOption.Recommendation.PREFERRED
        ).first()
        if (
            _missing_process_fields(analysis)
            or preferred is None
            or not analysis.use_case_origins.exists()
        ):
            return build_process_analysis_journey(analysis, user)
    if analyses:
        return build_process_analysis_journey(analyses[0], user)

    steps: list[JourneyStep] = []
    if not stages:
        steps.append(
            JourneyStep(
                key="value_stream",
                label="Value Stream",
                state="current",
                url=(
                    reverse("architecture:stage_create", kwargs={"stream_pk": value_stream.pk})
                    if can_manage
                    else None
                ),
                action_label="Erste Phase ergänzen" if can_manage else "",
                reason=_permission_reason(
                    can_manage,
                    "Der Value Stream besitzt noch keine geordneten End-to-End-Phasen.",
                ),
            )
        )
        steps.extend(
            [
                JourneyStep(key="process", label="Prozessanalyse", state="upcoming"),
                JourneyStep(key="solution", label="Lösungsoption", state="upcoming"),
                JourneyStep(key="use_case", label="Use Case", state="upcoming"),
                JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
                JourneyStep(key="approval", label="Freigabe", state="upcoming"),
                JourneyStep(key="delivery", label="Delivery", state="upcoming"),
            ]
        )
        return _state(path_label="Systematische Discovery", steps=steps)

    first_stage = stages[0]
    steps.extend(
        [
            JourneyStep(
                key="value_stream",
                label="Value Stream",
                state="complete",
                url=value_stream.get_absolute_url(),
                action_label="Value Stream öffnen",
                reason=f"{len(stages)} End-to-End-Phasen sind erfasst.",
            ),
            JourneyStep(
                key="process",
                label="Prozessanalyse",
                state="current",
                url=(
                    reverse(
                        "architecture:process_analysis_create",
                        kwargs={"stage_pk": first_stage.pk},
                    )
                    if can_manage
                    else None
                ),
                action_label="Relevanten Prozess analysieren" if can_manage else "",
                reason=_permission_reason(
                    can_manage,
                    "Für die relevanten Phasen liegt noch keine Detailanalyse vor.",
                ),
            ),
            JourneyStep(key="solution", label="Lösungsoption", state="upcoming"),
            JourneyStep(key="use_case", label="Use Case", state="upcoming"),
            JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
            JourneyStep(key="approval", label="Freigabe", state="upcoming"),
            JourneyStep(key="delivery", label="Delivery", state="upcoming"),
        ]
    )
    return _state(path_label="Systematische Discovery", steps=steps)


def build_delivery_package_journey(package: DeliveryPackage, user) -> JourneyState:
    return build_use_case_journey(package.use_case, user)
