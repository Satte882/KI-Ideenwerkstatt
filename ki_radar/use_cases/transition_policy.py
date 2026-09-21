from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.delivery.handover import recorded_handover_package
from ki_radar.governance.services import current_governance_status, required_governance_blockers

from .models import UseCase
from .permissions import can_end_use_case, can_start_pilot


@dataclass(frozen=True)
class TransitionRule:
    sources: frozenset[str]
    target: str | None
    changes_status: bool


COMMAND_RULES: dict[str, TransitionRule] = {
    "start_review": TransitionRule(frozenset({UseCase.Status.IDEA}), UseCase.Status.REVIEW, True),
    "start_pilot": TransitionRule(frozenset({UseCase.Status.REVIEW}), UseCase.Status.PILOT, True),
    "go_live": TransitionRule(frozenset({UseCase.Status.PILOT}), UseCase.Status.OPERATION, True),
    "end": TransitionRule(
        frozenset({UseCase.Status.PILOT, UseCase.Status.OPERATION}),
        UseCase.Status.ENDED,
        True,
    ),
    "continue": TransitionRule(
        frozenset({UseCase.Status.REVIEW, UseCase.Status.PILOT, UseCase.Status.OPERATION}),
        None,
        False,
    ),
    "pause": TransitionRule(
        frozenset({UseCase.Status.REVIEW, UseCase.Status.PILOT, UseCase.Status.OPERATION}),
        None,
        False,
    ),
    "rework": TransitionRule(
        frozenset({UseCase.Status.REVIEW, UseCase.Status.PILOT, UseCase.Status.OPERATION}),
        None,
        False,
    ),
}

APPROVED_DECISION_STATUSES = {
    UseCase.DecisionStatus.APPROVED,
    UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
}


def _text(value) -> str:
    return str(value or "").strip()


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"1", "true", "yes", "on"}


def validate_transition_shape(*, use_case: UseCase, decision: str, target_status: str) -> None:
    if decision == "return":
        raise ValidationError(
            "Lifecycle-Rückstufungen sind nicht mehr vorgesehen. "
            "Rework bleibt in der erreichten Phase."
        )
    rule = COMMAND_RULES.get(decision)
    if rule is None:
        raise ValidationError("Unbekannte Lifecycle-/Review-Entscheidung.")
    if use_case.status not in rule.sources:
        allowed = ", ".join(UseCase.Status(value).label for value in sorted(rule.sources))
        raise ValidationError(
            f"{decision} ist aus dem Status {use_case.get_status_display()} nicht zulässig. "
            f"Erlaubt: {allowed}."
        )
    expected_target = rule.target if rule.changes_status else use_case.status
    if target_status != expected_target:
        raise ValidationError(
            f"Die Entscheidung {decision} erfordert den Zielstatus "
            f"{UseCase.Status(expected_target).label}."
        )


def validate_actor(*, use_case: UseCase, decision: str, actor) -> None:
    if decision in {"start_review", "go_live", "continue", "pause", "rework"}:
        if not is_coordinator(actor):
            raise PermissionDenied(
                "Für diese Entscheidung ist die Koordinator-Berechtigung erforderlich."
            )
        return
    if decision == "start_pilot":
        if not can_start_pilot(actor, use_case):
            raise PermissionDenied(
                "Nur ein KI-Koordinator oder der zuständige Business Owner darf den Pilot starten."
            )
        return
    if decision == "end" and not can_end_use_case(actor, use_case):
        raise PermissionDenied(
            "Nur ein KI-Koordinator oder der zuständige Business Owner darf den Use Case beenden."
        )


def validate_pilot_start(
    *,
    use_case: UseCase,
    pilot_start: date | None,
) -> None:
    blockers: list[str] = []
    if use_case.decision_status not in APPROVED_DECISION_STATUSES:
        blockers.append("finale positive Freigabe")
    package = recorded_handover_package(use_case)
    if package is None:
        blockers.append("verbindliche Übergabe des aktuellen Delivery Packages")
    governance = current_governance_status(use_case)
    if not governance.has_screening:
        blockers.append("Governance-Screening")
    blockers.extend(required_governance_blockers(use_case))
    if blockers:
        raise ValidationError("Pilotstart blockiert: " + "; ".join(blockers))

    if pilot_start is None:
        raise ValidationError("Der tatsächliche Pilotbeginn ist erforderlich.")
    today = timezone.localdate()
    if pilot_start > today:
        raise ValidationError("Der tatsächliche Pilotbeginn darf nicht in der Zukunft liegen.")
    handover_date = timezone.localdate(package.handed_over_at)
    if pilot_start < handover_date:
        raise ValidationError(
            "Der tatsächliche Pilotbeginn darf nicht vor der verbindlichen Übergabe liegen."
        )


def validate_go_live(
    *,
    use_case: UseCase,
    evidence: Mapping | None,
    go_live_exception_confirmed: bool,
    rationale: str,
) -> None:
    blockers: list[str] = []
    for field_name, label in (
        ("metric_name", "Primäre Erfolgsmetrik"),
        ("metric_direction", "Optimierungsrichtung"),
        ("metric_target", "Zielwert"),
        ("metric_actual", "Ist-Wert"),
        ("metric_measured_at", "Messdatum"),
    ):
        if getattr(use_case, field_name) in (None, ""):
            blockers.append(label)
    if use_case.pilot_start is None:
        blockers.append("Tatsächlicher Pilotbeginn")
    elif use_case.metric_measured_at and use_case.metric_measured_at < use_case.pilot_start:
        blockers.append("Messdatum muss am oder nach dem tatsächlichen Pilotbeginn liegen")

    blockers.extend(required_governance_blockers(use_case))

    data = evidence or {}
    if _text(data.get("ml_score_failed_mandatory_checks")):
        blockers.append("Mindestens eine ausdrücklich zwingende ML-Prüfung ist fehlgeschlagen")
    if not _bool(data.get("scale_rollback_tested")):
        blockers.append("Rollback oder Deaktivierung muss praktisch möglich/getestet sein")
    if not use_case.technical_owner_id:
        blockers.append("Technical Owner")
    if not _text(use_case.support_responsibility):
        blockers.append("Support-Verantwortung")

    if blockers:
        raise ValidationError("Go-live blockiert: " + "; ".join(blockers))

    if use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED:
        if not go_live_exception_confirmed:
            raise ValidationError(
                "Ein Go-live bei verfehltem Pilotziel benötigt eine ausdrücklich "
                "bestätigte Ausnahme."
            )
        if not _text(rationale):
            raise ValidationError(
                "Die Go-live-Ausnahme benötigt eine kurze Entscheidungsbegründung."
            )


def validate_review_command(
    *,
    use_case: UseCase,
    decision: str,
    target_status: str,
    actor,
    pilot_start: date | None = None,
    scale_evidence: Mapping | None = None,
    go_live_exception_confirmed: bool = False,
    rationale: str = "",
) -> None:
    validate_transition_shape(
        use_case=use_case,
        decision=decision,
        target_status=target_status,
    )
    validate_actor(use_case=use_case, decision=decision, actor=actor)
    if decision == "start_pilot":
        validate_pilot_start(use_case=use_case, pilot_start=pilot_start)
    elif decision == "go_live":
        validate_go_live(
            use_case=use_case,
            evidence=scale_evidence,
            go_live_exception_confirmed=go_live_exception_confirmed,
            rationale=rationale,
        )
