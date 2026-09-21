from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .models import UseCase
from .services import (
    EARLY_GO_LIVE_BLOCKER,
    approval_check,
    check_go_live,
    check_pilot_start,
    current_decision_check,
    intake_blockers,
)

if TYPE_CHECKING:
    from .journey import JourneyState


@dataclass(frozen=True)
class WorkCheck:
    title: str
    state: str
    state_label: str
    blockers: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class StatusDimension:
    key: str
    title: str
    label: str
    state: str
    explanation: str


@dataclass(frozen=True)
class UseCaseStatusDimensions:
    process: StatusDimension
    assessment: StatusDimension
    approval: StatusDimension
    measurement: StatusDimension
    lifecycle: StatusDimension
    next_lifecycle_decision: str

    @property
    def items(self) -> tuple[StatusDimension, ...]:
        return (
            self.process,
            self.assessment,
            self.approval,
            self.measurement,
            self.lifecycle,
        )


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _requirements_open_text(count: int) -> str:
    if count == 1:
        return "Für die Produktivsetzung ist noch eine Voraussetzung offen."
    return f"Für die Produktivsetzung sind noch {count} Voraussetzungen offen."


def _from_lifecycle_check(use_case: UseCase) -> WorkCheck:
    check = current_decision_check(use_case)
    return WorkCheck(
        title=check.title,
        state=check.state,
        state_label=check.state_label,
        blockers=list(check.blockers),
        warnings=list(check.warnings),
    )


def current_work_check(use_case: UseCase) -> WorkCheck:
    final_decision = use_case.approval_decisions.filter(finalized_at__isnull=False).first()
    if final_decision is not None:
        if final_decision.decision_status in {
            UseCase.DecisionStatus.DEFERRED,
            UseCase.DecisionStatus.NOT_PURSUED,
        }:
            return WorkCheck(
                title="Finale Entscheidung",
                state="blocked",
                state_label=final_decision.get_decision_status_display(),
                blockers=[],
                warnings=[],
            )
        if use_case.status in {UseCase.Status.IDEA, UseCase.Status.REVIEW}:
            check = check_pilot_start(use_case)
            return WorkCheck(
                title=check.title,
                state=check.state,
                state_label=(
                    "Pilotstart blockiert" if check.blockers else "Bereit für den Pilotstart"
                ),
                blockers=list(check.blockers),
                warnings=list(check.warnings),
            )
        return _from_lifecycle_check(use_case)

    pending = use_case.approval_decisions.filter(finalized_at__isnull=True).first()
    if pending is not None:
        return WorkCheck(
            title="Zweitfreigabe abschließen",
            state="blocked",
            state_label="Zweitfreigabe offen",
            blockers=["Unabhängige zweite Freigabe"],
            warnings=[],
        )

    assessment = use_case.decision_assessments.first()
    if assessment is None:
        blockers = intake_blockers(use_case)
        if blockers:
            return WorkCheck(
                title="Bewertung vorbereiten",
                state="blocked",
                state_label="Bewertung blockiert",
                blockers=blockers,
                warnings=[],
            )
        return WorkCheck(
            title="Bewertung anlegen",
            state="ready",
            state_label="Bewertungsbereit",
            blockers=[],
            warnings=[],
        )

    check = approval_check(
        use_case=use_case,
        target_status=assessment.recommendation,
        governance_confirmed=True,
    )
    blockers = list(check.blockers)
    if use_case.coordinator_id is None:
        blockers.append("KI-Koordination nicht zugewiesen")
    positive_recommendation = assessment.recommendation in {
        UseCase.DecisionStatus.APPROVED,
        UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    }
    return WorkCheck(
        title=(
            "Freigabe vorbereiten"
            if blockers and positive_recommendation
            else "Portfolioentscheidung vorbereiten"
            if blockers
            else "Portfolioentscheidung treffen"
        ),
        state="blocked" if blockers else ("review" if check.warnings else "ready"),
        state_label=(
            "Freigabe blockiert"
            if blockers and positive_recommendation
            else "Entscheidung blockiert"
            if blockers
            else "Entscheidung möglich"
        ),
        blockers=blockers,
        warnings=list(check.warnings),
    )


def _process_dimension(journey: JourneyState) -> StatusDimension:
    action = journey.next_action
    if action is not None:
        return StatusDimension(
            key="process",
            title="Arbeitsphase",
            label=action.label,
            state="blocked" if action.state == "blocked" else "review",
            explanation=action.reason or "Dieser Schritt ist als Nächstes zu bearbeiten.",
        )
    return StatusDimension(
        key="process",
        title="Arbeitsphase",
        label="Abgeschlossen",
        state="ready",
        explanation=journey.completion_message
        or "Für diesen Pfad ist kein weiterer Pflichtschritt offen.",
    )


def _assessment_dimension(use_case: UseCase) -> StatusDimension:
    assessment = use_case.decision_assessments.first()
    if assessment is not None:
        return StatusDimension(
            key="assessment",
            title="Assessment",
            label=f"Bewertung v{assessment.version} vorhanden",
            state="ready",
            explanation=(
                f"Confidence: {assessment.confidence_label}. "
                "Eine neue Version ersetzt die bestehende Bewertung nicht rückwirkend."
            ),
        )

    blockers = intake_blockers(use_case)
    if blockers:
        return StatusDimension(
            key="assessment",
            title="Assessment",
            label="Bewertung blockiert",
            state="blocked",
            explanation=f"Vor der Bewertung fehlt: {blockers[0]}.",
        )
    return StatusDimension(
        key="assessment",
        title="Assessment",
        label="Bewertungsbereit",
        state="review",
        explanation="Der Intake ist vollständig; eine strukturierte Bewertung steht noch aus.",
    )


def _approval_dimension(use_case: UseCase) -> StatusDimension:
    work_check = current_work_check(use_case)
    final_decision = use_case.approval_decisions.filter(finalized_at__isnull=False).first()
    if final_decision is not None:
        positive = final_decision.decision_status in {
            UseCase.DecisionStatus.APPROVED,
            UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        }
        return StatusDimension(
            key="approval",
            title="Freigabe",
            label=final_decision.get_decision_status_display(),
            state="ready" if positive else "blocked",
            explanation="Die verbindliche Entscheidung ist versioniert und abgeschlossen.",
        )

    pending = use_case.approval_decisions.filter(finalized_at__isnull=True).first()
    if pending is not None:
        return StatusDimension(
            key="approval",
            title="Freigabe",
            label="Zweitfreigabe offen",
            state="blocked",
            explanation="Die vorgeschlagene Freigabe ist noch nicht final bestätigt.",
        )

    if use_case.decision_assessments.first() is None:
        return StatusDimension(
            key="approval",
            title="Freigabe",
            label="Bewertung erforderlich",
            state="review",
            explanation=(
                "Eine Freigabeentscheidung ist erst nach einer strukturierten Bewertung möglich."
            ),
        )

    return StatusDimension(
        key="approval",
        title="Entscheidung",
        label=work_check.state_label,
        state=work_check.state,
        explanation=(
            f"Nächster offener Punkt: {work_check.blockers[0]}."
            if work_check.blockers
            else "Bewertung und fachliche Voraussetzungen liegen für die Entscheidung vor."
        ),
    )


def _measurement_dimension(use_case: UseCase) -> StatusDimension:
    result = use_case.metric_result
    state = {
        UseCase.MetricResult.ACHIEVED: "ready",
        UseCase.MetricResult.NOT_ACHIEVED: "blocked",
        UseCase.MetricResult.NOT_MEASURED: "review",
        UseCase.MetricResult.NOT_DEFINED: "blocked",
    }[result]
    if use_case.metric_result_label.startswith("Metrik definiert ·"):
        explanation = (
            "Die Messlogik ist angelegt; noch offene Baseline- oder Zielwerte bleiben sichtbar."
        )
    else:
        explanation = {
            UseCase.MetricResult.ACHIEVED: "Der gemessene Ist-Wert erfüllt das definierte Ziel.",
            UseCase.MetricResult.NOT_ACHIEVED: (
                "Der gemessene Ist-Wert verfehlt das definierte Ziel."
            ),
            UseCase.MetricResult.NOT_MEASURED: (
                "Ziel und Messlogik sind definiert; ein Ist-Wert fehlt."
            ),
            UseCase.MetricResult.NOT_DEFINED: (
                "Eine vollständige Erfolgsmetrik ist noch nicht definiert."
            ),
        }[result]
    return StatusDimension(
        key="measurement",
        title="Messung",
        label=use_case.metric_result_label,
        state=state,
        explanation=explanation,
    )


def _lifecycle_dimension(use_case: UseCase) -> StatusDimension:
    state = {
        UseCase.Status.IDEA: "review",
        UseCase.Status.REVIEW: "review",
        UseCase.Status.PILOT: "review",
        UseCase.Status.OPERATION: "ready",
        UseCase.Status.ENDED: "ready",
    }[use_case.status]
    explanations = {
        UseCase.Status.IDEA: "Der Use Case befindet sich in Erfassung und fachlicher Klärung.",
        UseCase.Status.REVIEW: "Bewertung, Freigabe und Übergabe werden vorbereitet.",
        UseCase.Status.PILOT: ("Der Use Case wird unter definierten Pilotbedingungen erprobt."),
        UseCase.Status.OPERATION: "Der Use Case befindet sich im geregelten Betrieb.",
        UseCase.Status.ENDED: (
            "Der Lifecycle ist beendet; Abschluss und Datenbehandlung bleiben nachvollziehbar."
        ),
    }
    return StatusDimension(
        key="lifecycle",
        title="Lifecycle",
        label=use_case.get_status_display(),
        state=state,
        explanation=explanations[use_case.status],
    )


def _next_lifecycle_decision(use_case: UseCase) -> str:
    if use_case.status == UseCase.Status.IDEA:
        work_check = current_work_check(use_case)
        if work_check.blockers:
            return f"Vor der Bewertung fehlt: {work_check.blockers[0]}."
        if use_case.decision_assessments.exists():
            return "Nächste Aktion: verbindliche Freigabeentscheidung vorbereiten."
        return "Nächste Aktion: strukturierte Bewertung anlegen."

    if use_case.status == UseCase.Status.REVIEW:
        work_check = current_work_check(use_case)
        if work_check.blockers:
            return f"{work_check.title} blockiert: {work_check.blockers[0]}."
        return f"Nächste Aktion: {work_check.title.lower()}."

    if use_case.status == UseCase.Status.PILOT:
        check = check_go_live(use_case)
        temporal_requirement_open = EARLY_GO_LIVE_BLOCKER in check.blockers
        actionable_count = len(check.blockers) - int(temporal_requirement_open)
        if temporal_requirement_open and use_case.planned_pilot_end:
            pilot_message = f"Pilot läuft planmäßig bis {_format_date(use_case.planned_pilot_end)}."
            if actionable_count:
                return f"{pilot_message} {_requirements_open_text(actionable_count)}"
            return (
                f"{pilot_message} Danach kann die Produktivsetzung entschieden werden; "
                "eine vorzeitige Ausnahme ist möglich."
            )
        if check.blockers:
            return _requirements_open_text(len(check.blockers))
        if use_case.planned_pilot_end:
            return (
                "Go-live-Entscheidung zum geplanten Pilotende am "
                f"{_format_date(use_case.planned_pilot_end)}."
            )
        return "Für die Go-live-Entscheidung fehlt das geplante Pilotende."

    if use_case.status == UseCase.Status.OPERATION:
        if use_case.next_review_date:
            return f"Nächste Betriebsentscheidung am {_format_date(use_case.next_review_date)}."
        return "Für den Betrieb fehlt der nächste Entscheidungstermin."

    return "Keine weitere Lifecycle-Entscheidung vorgesehen."


def build_use_case_status_dimensions(
    use_case: UseCase,
    journey: JourneyState,
) -> UseCaseStatusDimensions:
    return UseCaseStatusDimensions(
        process=_process_dimension(journey),
        assessment=_assessment_dimension(use_case),
        approval=_approval_dimension(use_case),
        measurement=_measurement_dimension(use_case),
        lifecycle=_lifecycle_dimension(use_case),
        next_lifecycle_decision=_next_lifecycle_decision(use_case),
    )
