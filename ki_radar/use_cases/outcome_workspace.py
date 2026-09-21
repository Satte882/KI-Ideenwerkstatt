from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.readiness import blocking_findings, delivery_status_snapshot
from ki_radar.delivery.services import (
    current_delivery_package,
    current_handed_over_package,
)
from ki_radar.reviews.models import Review

from .models import UseCase
from .permissions import can_start_pilot
from .services import check_pilot_start
from .workflow import (
    JourneyState,
    JourneyStep,
    _state,
    build_use_case_journey,
    pilot_start_url,
)

OUTCOME_STAGES = (
    ("handover", "Übergabe", "handover"),
    ("pilot", "Pilot", "pilot"),
    ("effect", "Wirkung", "measurement"),
    ("decision", "Ergebnisentscheidung", "outcome_decision"),
    ("operation", "Betrieb", "operation"),
    ("closure", "Abschluss", "closure"),
)
OUTCOME_STAGE_KEYS = {stage for stage, _label, _step_key in OUTCOME_STAGES}
MEASUREMENT_REQUIRED_FIELDS = (
    ("metric_actual", "Ist-Wert"),
    ("metric_measurement_period", "Messzeitraum"),
    ("metric_measured_at", "Messdatum"),
    ("metric_evidence_url", "Messnachweis"),
)


def normalize_outcome_stage(value: str | None) -> str:
    return value if value in OUTCOME_STAGE_KEYS else "pilot"


def outcome_workspace_url(
    stage: str,
    *,
    use_case: UseCase | None = None,
) -> str:
    query = {"stage": normalize_outcome_stage(stage)}
    if use_case is not None:
        query["use_case"] = str(use_case.pk)
    return f"{reverse('reporting:outcome_workspace')}?{urlencode(query)}"


def _measurement_missing(use_case: UseCase) -> tuple[str, ...]:
    return tuple(
        label
        for field_name, label in MEASUREMENT_REQUIRED_FIELDS
        if getattr(use_case, field_name) in (None, "")
    )


def _measurement_fields_complete(use_case: UseCase) -> bool:
    return not _measurement_missing(use_case)


def _measurement_complete(use_case: UseCase) -> bool:
    if not _measurement_fields_complete(use_case) or use_case.pilot_start is None:
        return False
    return use_case.metric_measured_at >= use_case.pilot_start


def _measurement_predates_pilot(use_case: UseCase) -> bool:
    return bool(
        _measurement_fields_complete(use_case)
        and use_case.pilot_start is not None
        and use_case.metric_measured_at < use_case.pilot_start
    )


def _has_measurement_data(use_case: UseCase) -> bool:
    return any(
        getattr(use_case, field_name) not in (None, "")
        for field_name, _label in MEASUREMENT_REQUIRED_FIELDS
    )


def _has_review(
    use_case: UseCase,
    *,
    decision: str,
    previous_statuses: tuple[str, ...],
    new_status: str,
) -> bool:
    reviews = use_case.reviews.filter(
        decision=decision,
        previous_status__in=previous_statuses,
        new_status=new_status,
    )
    if use_case.pilot_start is not None:
        reviews = reviews.filter(review_date__gte=use_case.pilot_start)
    return reviews.exists()


def _handover_step(
    package: DeliveryPackage | None,
    *,
    handed_over: bool,
    lifecycle_advanced: bool,
) -> JourneyStep:
    if package is None:
        if lifecycle_advanced:
            return JourneyStep(
                key="handover",
                label="Übergabe",
                state="blocked",
                reason=(
                    "Dateninkonsistenz: Der Lifecycle ist bereits fortgeschritten, aber es "
                    "existiert kein aktuelles Delivery Package mit verbindlicher Übergabe."
                ),
                details=("Delivery Package", "Übergabezeitpunkt"),
            )
        return JourneyStep(
            key="handover",
            label="Übergabe",
            state="upcoming",
            reason=("Die verbindliche Übergabe beginnt nach einem vollständigen Delivery Package."),
        )
    if handed_over:
        return JourneyStep(
            key="handover",
            label="Übergabe",
            state="complete",
            url=package.get_absolute_url(),
            action_label="Übergabe öffnen",
            reason=f"Delivery Package v{package.version} wurde verbindlich übergeben.",
        )
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        status_snapshot = delivery_status_snapshot(package)
        details = tuple(finding.message for finding in blocking_findings(package)) or (
            "Verbindlicher Übergabezeitpunkt",
        )
        return JourneyStep(
            key="handover",
            label="Übergabe",
            state="blocked",
            url=package.get_absolute_url(),
            action_label="Übergabe prüfen",
            reason=status_snapshot.label,
            details=details,
        )
    if lifecycle_advanced:
        return JourneyStep(
            key="handover",
            label="Übergabe",
            state="blocked",
            url=package.get_absolute_url(),
            action_label="Delivery Package prüfen",
            reason=(
                "Dateninkonsistenz: Der Lifecycle ist bereits fortgeschritten, obwohl die "
                "aktuelle Package-Version noch nicht verbindlich übergeben wurde."
            ),
            details=("Aktuelle Package-Version", "verbindliche Übergabe"),
        )
    status_snapshot = delivery_status_snapshot(package)
    ready_and_valid = (
        package.status == DeliveryPackage.Status.READY
        and status_snapshot.code == DeliveryPackage.Status.READY
    )
    return JourneyStep(
        key="handover",
        label="Übergabe",
        state="current" if ready_and_valid else "blocked",
        url=package.get_absolute_url(),
        action_label="Delivery Package öffnen" if ready_and_valid else "Readiness prüfen",
        reason=(
            "Das Package ist bereit; die Übergabe an das externe Delivery-System steht aus."
            if ready_and_valid
            else (
                status_snapshot.label
                if package.status == DeliveryPackage.Status.READY
                else "Das Delivery Package muss vor der Übergabe vervollständigt werden."
            )
        ),
        details=(
            tuple(finding.message for finding in blocking_findings(package))
            if package.status == DeliveryPackage.Status.READY and not ready_and_valid
            else ()
        ),
    )


def _pilot_step(
    use_case: UseCase,
    *,
    handed_over: bool,
    pilot_started: bool,
    pilot_complete: bool,
    lifecycle_advanced: bool,
    user,
) -> JourneyStep:
    url = outcome_workspace_url("pilot", use_case=use_case)
    if not handed_over:
        return JourneyStep(
            key="pilot",
            label="Pilot",
            state="blocked" if lifecycle_advanced else "upcoming",
            reason=(
                "Dateninkonsistenz: Pilot- oder Folgedaten liegen vor, obwohl die "
                "verbindliche Übergabe der aktuellen Package-Version fehlt."
                if lifecycle_advanced
                else "Die Pilotbeobachtung beginnt erst nach der verbindlichen Übergabe."
            ),
        )
    if pilot_complete:
        return JourneyStep(
            key="pilot",
            label="Pilot",
            state="complete",
            url=url,
            action_label="Pilot öffnen",
            reason=("Der Pilot ist fachlich abgeschlossen; die Folgeentscheidung ist vorbereitet."),
        )
    if pilot_started:
        if use_case.status != UseCase.Status.PILOT:
            return JourneyStep(
                key="pilot",
                label="Pilot",
                state="blocked",
                url=url,
                action_label="Pilot prüfen",
                reason=(
                    "Dateninkonsistenz: Ein Pilotstart ist dokumentiert, aber der "
                    "Lifecycle-Status oder die Nachweise belegen keinen laufenden oder "
                    "abgeschlossenen Pilot."
                ),
            )
        return JourneyStep(
            key="pilot",
            label="Pilot",
            state="current",
            url=url,
            action_label="Pilot öffnen",
            reason=(
                "Der Pilot läuft; die Wirkungsmessung ist noch nicht vollständig abgeschlossen."
            ),
        )
    if use_case.status in {
        UseCase.Status.PILOT,
        UseCase.Status.OPERATION,
        UseCase.Status.ENDED,
    }:
        return JourneyStep(
            key="pilot",
            label="Pilot",
            state="blocked",
            reason=(
                "Dateninkonsistenz: Der Lifecycle-Status setzt einen gestarteten Pilot "
                "voraus, aber ein verbindlicher Pilotbeginn fehlt."
            ),
            details=("Pilotbeginn",),
        )
    check = check_pilot_start(use_case)
    allowed = can_start_pilot(user, use_case)
    reason = "Die Übergabe ist erfolgt; der tatsächliche Pilotbeginn muss bestätigt werden."
    if not allowed:
        reason += " Nur ein KI-Koordinator oder der zuständige Business Owner darf starten."
    return JourneyStep(
        key="pilot",
        label="Pilot",
        state="blocked" if check.blockers else "current",
        url=pilot_start_url(use_case) if allowed else None,
        action_label="Pilot starten" if allowed else "",
        reason=reason,
        details=tuple(check.blockers),
    )


def _measurement_step(
    use_case: UseCase,
    *,
    handed_over: bool,
    pilot_started: bool,
    pilot_complete: bool,
    measurement_complete: bool,
    end_recorded: bool,
) -> JourneyStep:
    edit_url = reverse("use_cases:edit", kwargs={"pk": use_case.pk})
    missing = _measurement_missing(use_case)
    has_data = _has_measurement_data(use_case)
    if not handed_over or not pilot_started:
        lifecycle_requires_pilot = (
            use_case.status
            in {
                UseCase.Status.PILOT,
                UseCase.Status.OPERATION,
                UseCase.Status.ENDED,
            }
            or end_recorded
        )
        return JourneyStep(
            key="measurement",
            label="Wirkungsmessung",
            state="blocked" if lifecycle_requires_pilot else "upcoming",
            reason=(
                "Dateninkonsistenz: Der Lifecycle ist bereits fortgeschritten, obwohl "
                "Übergabe oder Pilotbeginn fehlen."
                if lifecycle_requires_pilot
                else (
                    "Vorhandene Messwerte schließen keinen Pilot ab, solange kein "
                    "verbindlicher Pilotbeginn dokumentiert ist."
                    if has_data
                    else "Die Wirkungsmessung folgt nach Übergabe und gestartetem Pilot."
                )
            ),
            details=("Übergabe", "Pilotbeginn") if lifecycle_requires_pilot else (),
        )
    if _measurement_predates_pilot(use_case):
        return JourneyStep(
            key="measurement",
            label="Wirkungsmessung",
            state="upcoming",
            url=f"{edit_url}?highlight=metric_measured_at",
            action_label="Messung für aktuellen Pilot aktualisieren",
            reason=(
                "Die vorhandene Messung stammt aus der Zeit vor dem aktuellen "
                "Pilotbeginn und schließt diesen Pilot nicht ab."
            ),
            details=("Messdatum ab Pilotbeginn",),
        )
    if measurement_complete:
        return JourneyStep(
            key="measurement",
            label="Wirkungsmessung",
            state="complete",
            url=outcome_workspace_url("effect", use_case=use_case),
            action_label="Wirkung öffnen",
            reason=(
                f"{use_case.metric_result_label}; Messwert und vollständiger Nachweis liegen vor."
            ),
        )
    if end_recorded:
        return JourneyStep(
            key="measurement",
            label="Wirkungsmessung",
            state="optional",
            url=outcome_workspace_url("effect", use_case=use_case),
            action_label="Wirkung öffnen",
            reason=(
                "Der Use Case wurde beendet, ohne in den produktiven Betrieb überführt zu werden."
            ),
            details=missing,
        )
    if pilot_complete:
        first_missing_field = next(
            field_name
            for field_name, _label in MEASUREMENT_REQUIRED_FIELDS
            if getattr(use_case, field_name) in (None, "")
        )
        return JourneyStep(
            key="measurement",
            label="Wirkungsmessung",
            state="blocked",
            url=f"{edit_url}?highlight={first_missing_field}",
            action_label="Wirkungsmessung vervollständigen",
            reason=(
                "Der Pilot ist abgeschlossen, aber die Wirkungsmessung ist noch unvollständig."
            ),
            details=missing,
        )
    return JourneyStep(
        key="measurement",
        label="Wirkungsmessung",
        state="upcoming",
        url=f"{edit_url}?highlight=metric_actual",
        action_label="Wirkungsmessung vorbereiten",
        reason=("Der Pilot läuft; die vollständige Messung wird zum Review-Zeitpunkt bestätigt."),
        details=missing,
    )


def _outcome_decision_step(
    use_case: UseCase,
    *,
    handed_over: bool,
    pilot_started: bool,
    measurement_complete: bool,
    go_live_recorded: bool,
    end_recorded: bool,
) -> JourneyStep:
    url = outcome_workspace_url("decision", use_case=use_case)
    if not handed_over or not pilot_started:
        advanced = (
            go_live_recorded
            or end_recorded
            or use_case.status
            in {
                UseCase.Status.OPERATION,
                UseCase.Status.ENDED,
            }
        )
        return JourneyStep(
            key="outcome_decision",
            label="Ergebnisentscheidung",
            state="blocked" if advanced else "upcoming",
            reason=(
                "Dateninkonsistenz: Eine Folgeentscheidung ist dokumentiert oder im "
                "Status abgebildet, obwohl Übergabe oder Pilotbeginn fehlen."
                if advanced
                else ("Eine Folgeentscheidung setzt Übergabe, Pilot und belastbare Evidenz voraus.")
            ),
        )
    if end_recorded:
        ended = use_case.status == UseCase.Status.ENDED
        return JourneyStep(
            key="outcome_decision",
            label="Ergebnisentscheidung",
            state="complete" if ended else "blocked",
            url=url,
            action_label="Ergebnisentscheidung öffnen",
            reason=(
                "Die Beendigungsentscheidung ist im Lifecycle-Review dokumentiert."
                if ended
                else (
                    "Dateninkonsistenz: Eine Beendigungsentscheidung liegt vor, "
                    "der Status ist nicht Beendet."
                )
            ),
        )
    if go_live_recorded:
        valid_status = use_case.status in {
            UseCase.Status.OPERATION,
            UseCase.Status.ENDED,
        }
        valid = measurement_complete and valid_status
        return JourneyStep(
            key="outcome_decision",
            label="Ergebnisentscheidung",
            state="complete" if valid else "blocked",
            url=url,
            action_label="Ergebnisentscheidung öffnen",
            reason=(
                "Die Go-live-Entscheidung ist mit vollständiger Messgrundlage dokumentiert."
                if valid
                else (
                    "Dateninkonsistenz: Die Go-live-Entscheidung passt nicht zu "
                    "Messung oder Status."
                )
            ),
            details=() if valid else _measurement_missing(use_case),
        )
    if use_case.status in {UseCase.Status.OPERATION, UseCase.Status.ENDED}:
        return JourneyStep(
            key="outcome_decision",
            label="Ergebnisentscheidung",
            state="blocked",
            url=url,
            action_label="Ergebnisentscheidung prüfen",
            reason=(
                "Dateninkonsistenz: Der Lifecycle-Status ist bereits fortgeschritten, "
                "aber ein passendes Go-live- oder Abschlussreview fehlt."
            ),
        )
    if measurement_complete:
        return JourneyStep(
            key="outcome_decision",
            label="Ergebnisentscheidung",
            state="current",
            url=url,
            action_label="Ergebnisentscheidung prüfen",
            reason=(
                "Die vollständige Messgrundlage liegt vor; jetzt steht die Folgeentscheidung an."
            ),
        )
    return JourneyStep(
        key="outcome_decision",
        label="Ergebnisentscheidung",
        state="upcoming",
        reason=("Eine belastbare Folgeentscheidung setzt die vollständige Wirkungsmessung voraus."),
    )


def _operation_step(
    use_case: UseCase,
    *,
    handed_over: bool,
    pilot_started: bool,
    measurement_complete: bool,
    go_live_recorded: bool,
    end_recorded: bool,
) -> JourneyStep:
    url = outcome_workspace_url("operation", use_case=use_case)
    if go_live_recorded:
        prerequisites_complete = handed_over and pilot_started and measurement_complete
        valid_status = use_case.status in {
            UseCase.Status.OPERATION,
            UseCase.Status.ENDED,
        }
        if not prerequisites_complete or not valid_status:
            return JourneyStep(
                key="operation",
                label="Betrieb",
                state="blocked",
                url=url,
                action_label="Betriebskontext prüfen",
                reason=(
                    "Dateninkonsistenz: Der Go-live ist dokumentiert, aber Status "
                    "oder zwingende Voraussetzungen sind nicht vollständig."
                ),
                details=_measurement_missing(use_case),
            )
        ended = use_case.status == UseCase.Status.ENDED
        return JourneyStep(
            key="operation",
            label="Betrieb",
            state="complete" if ended else "current",
            url=url,
            action_label="Betriebskontext öffnen",
            reason=(
                "Der produktive Betrieb wurde beendet."
                if ended
                else (
                    "Das Vorhaben befindet sich nach dokumentiertem Go-live im produktiven Betrieb."
                )
            ),
        )
    if use_case.status == UseCase.Status.OPERATION:
        return JourneyStep(
            key="operation",
            label="Betrieb",
            state="blocked",
            url=url,
            action_label="Betriebskontext prüfen",
            reason=(
                "Dateninkonsistenz: Der Status steht auf Betrieb, aber ein "
                "dokumentiertes Go-live-Review fehlt."
            ),
        )
    if use_case.status == UseCase.Status.ENDED and end_recorded:
        return JourneyStep(
            key="operation",
            label="Betrieb",
            state="optional",
            reason=(
                "Der Use Case wurde beendet, ohne einen dokumentierten Go-live zu durchlaufen."
            ),
        )
    if use_case.status == UseCase.Status.ENDED:
        return JourneyStep(
            key="operation",
            label="Betrieb",
            state="blocked",
            reason=("Dateninkonsistenz: Der Use Case ist beendet, aber das Abschlussreview fehlt."),
        )
    return JourneyStep(
        key="operation",
        label="Betrieb",
        state="upcoming",
        reason=(
            "Betrieb wird erst nach einer dokumentierten positiven Ergebnisentscheidung relevant."
        ),
    )


def _closure_step(
    use_case: UseCase,
    *,
    handed_over: bool,
    pilot_started: bool,
    end_recorded: bool,
) -> JourneyStep:
    if use_case.status != UseCase.Status.ENDED:
        return JourneyStep(
            key="closure",
            label="Abschluss",
            state="upcoming",
            reason="Abschluss oder Stilllegung ist kein aktueller Schritt.",
        )
    valid = handed_over and pilot_started and end_recorded
    return JourneyStep(
        key="closure",
        label="Abschluss",
        state="complete" if valid else "blocked",
        url=outcome_workspace_url("closure", use_case=use_case),
        action_label="Abschluss öffnen" if valid else "Abschluss prüfen",
        reason=(
            "Das Abschlussreview und die Beendigung sind vollständig dokumentiert."
            if valid
            else (
                "Dateninkonsistenz: Status Beendet ohne vollständige Übergabe-, "
                "Pilot- oder Review-Kette."
            )
        ),
    )


def build_outcome_workspace_journey(
    use_case: UseCase,
    user,
) -> JourneyState:
    """Extend the existing journey; do not create a second status engine."""

    selection_journey = build_use_case_journey(use_case, user)
    package = current_delivery_package(use_case)
    handed_over = current_handed_over_package(use_case) is not None
    measurement_complete = _measurement_complete(use_case)
    go_live_recorded = _has_review(
        use_case,
        decision=Review.Decision.GO_LIVE,
        previous_statuses=(UseCase.Status.PILOT,),
        new_status=UseCase.Status.OPERATION,
    )
    end_recorded = _has_review(
        use_case,
        decision=Review.Decision.END,
        previous_statuses=(UseCase.Status.PILOT, UseCase.Status.OPERATION),
        new_status=UseCase.Status.ENDED,
    )
    pilot_started = bool(use_case.pilot_start)
    pilot_complete = bool(
        pilot_started
        and (measurement_complete or go_live_recorded or end_recorded or use_case.actual_end_date)
    )
    lifecycle_advanced = bool(
        use_case.status
        in {
            UseCase.Status.PILOT,
            UseCase.Status.OPERATION,
            UseCase.Status.ENDED,
        }
        or pilot_started
        or go_live_recorded
        or end_recorded
        or use_case.actual_end_date
    )

    outcome_steps = [
        _handover_step(
            package,
            handed_over=handed_over,
            lifecycle_advanced=lifecycle_advanced,
        ),
        _pilot_step(
            use_case,
            handed_over=handed_over,
            pilot_started=pilot_started,
            pilot_complete=pilot_complete,
            lifecycle_advanced=lifecycle_advanced,
            user=user,
        ),
        _measurement_step(
            use_case,
            handed_over=handed_over,
            pilot_started=pilot_started,
            pilot_complete=pilot_complete,
            measurement_complete=measurement_complete,
            end_recorded=end_recorded,
        ),
        _outcome_decision_step(
            use_case,
            handed_over=handed_over,
            pilot_started=pilot_started,
            measurement_complete=measurement_complete,
            go_live_recorded=go_live_recorded,
            end_recorded=end_recorded,
        ),
        _operation_step(
            use_case,
            handed_over=handed_over,
            pilot_started=pilot_started,
            measurement_complete=measurement_complete,
            go_live_recorded=go_live_recorded,
            end_recorded=end_recorded,
        ),
        _closure_step(
            use_case,
            handed_over=handed_over,
            pilot_started=pilot_started,
            end_recorded=end_recorded,
        ),
    ]
    current_steps = [step for step in outcome_steps if step.state == "current"]
    if len(current_steps) > 1:
        raise RuntimeError("Outcome journey must expose at most one current phase.")

    closure_complete = outcome_steps[-1].state == "complete"
    completion_message = (
        "Lebenszyklus abgeschlossen: Das Vorhaben ist beendet." if closure_complete else ""
    )
    return _state(
        path_label=f"{use_case.short_id} · Wirkung & Betrieb",
        steps=[*selection_journey.steps, *outcome_steps],
        completion_message=completion_message,
    )
