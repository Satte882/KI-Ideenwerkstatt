from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from ki_radar.accounts.permissions import (
    GROUP_COORDINATOR,
    GROUP_TECH_ADMIN,
    is_coordinator,
)
from ki_radar.delivery.handover import recorded_handover_package
from ki_radar.governance.services import (
    current_governance_status,
    failed_required_governance_reviews,
    open_required_governance_warnings,
    required_governance_blockers,
)

from .models import ApprovalDecision, DecisionAssessment, UseCase
from .transition_policy import APPROVED_DECISION_STATUSES

PILOT_STATUS_BLOCKER = "Lifecycle-Status Prüfung"
PILOT_PACKAGE_BLOCKER = "Aktuelles Delivery Package"
PILOT_HANDOVER_BLOCKER = "Verbindliche Übergabe des aktuellen Delivery Packages"
EARLY_GO_LIVE_BLOCKER = "Der geplante Pilotzeitraum ist noch nicht beendet"


@dataclass(frozen=True)
class DecisionCheck:
    target_status: str
    state: str
    title: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return not self.blockers

    @property
    def state_label(self) -> str:
        return {
            "ready": "Entscheidungsbereit",
            "blocked": "Blockiert",
            "review": "Prüfung empfohlen",
        }[self.state]


@dataclass(frozen=True)
class ApprovalCheck:
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return not self.blockers

    @property
    def state(self) -> str:
        if self.blockers:
            return "blocked"
        return "review" if self.warnings else "ready"

    @property
    def state_label(self) -> str:
        return {
            "ready": "Freigabebereit",
            "blocked": "Freigabe blockiert",
            "review": "Prüfung empfohlen",
        }[self.state]


# These groups describe readiness only. They are retained for presentation/backwards-compatible
# callers, but are no longer automatically promoted to lifecycle hard gates.
BASE_REQUIREMENTS = {
    UseCase.Status.REVIEW: [
        "title",
        "problem_statement",
        "affected_process",
        "business_owner",
        "expected_benefit",
    ],
    UseCase.Status.PILOT: [
        "data_sources",
        "next_review_date",
        "planned_pilot_end",
    ],
    UseCase.Status.OPERATION: [
        "business_owner",
        "technical_owner",
        "one_time_cost",
        "recurring_cost",
        "support_responsibility",
        "human_oversight",
        "next_review_date",
    ],
    UseCase.Status.ENDED: ["ending_reason", "data_and_access_handling"],
}
PILOT_METRIC_REQUIREMENTS = [
    "metric_name",
    "metric_type",
    "metric_direction",
    "metric_unit",
    "metric_baseline",
    "metric_target",
    "metric_measurement_method",
]
GO_LIVE_METRIC_REQUIREMENTS = [
    "metric_actual",
    "metric_measurement_period",
    "metric_measured_at",
    "metric_evidence_url",
]

# A draft/IDEA needs only identity + accountability. The former full intake checklist is readiness.
INTAKE_REQUIREMENTS = ["title", "business_unit", "business_owner"]
APPROVAL_METRIC_REQUIREMENTS = ["metric_baseline", "metric_target"]
POSITIVE_APPROVAL_CORE_REQUIREMENTS = [
    "title",
    "problem_statement",
    "affected_process",
    "business_owner",
    "expected_benefit",
]
GO_LIVE_CORE_REQUIREMENTS = [
    "metric_name",
    "metric_direction",
    "metric_target",
    "metric_actual",
    "metric_measured_at",
]

FIELD_LABELS = {
    "affected_process": "Betroffener Prozess",
    "business_owner": "Fachlich verantwortliche Person",
    "business_unit": "Organisationseinheit",
    "data_and_access_handling": "Umgang mit Daten und Zugängen",
    "data_sources": "Datenquellen",
    "ending_reason": "Beendigungsgrund",
    "expected_benefit": "Erwarteter Nutzen",
    "human_oversight": "Menschliche Aufsicht",
    "metric_actual": "Ist-Wert",
    "metric_baseline": "Baseline-Wert",
    "metric_direction": "Optimierungsrichtung",
    "metric_evidence_url": "Messnachweis",
    "metric_measurement_method": "Messmethode",
    "metric_measurement_period": "Messzeitraum",
    "metric_measured_at": "Messdatum",
    "metric_name": "Primäre Erfolgsmetrik",
    "metric_target": "Zielwert",
    "metric_type": "Metriktyp",
    "metric_unit": "Einheit",
    "next_review_date": "Nächster Entscheidungstermin",
    "one_time_cost": "Einmalige Kosten",
    "planned_pilot_end": "Geplantes Pilotende",
    "problem_statement": "Problemstellung",
    "recurring_cost": "Laufende Kosten",
    "support_responsibility": "Support-Verantwortung",
    "technical_owner": "Technischer Owner",
    "title": "Titel",
}

APPROVAL_STATUSES = set(APPROVED_DECISION_STATUSES)
FINAL_DECISION_STATUSES = APPROVAL_STATUSES | {
    UseCase.DecisionStatus.DEFERRED,
    UseCase.DecisionStatus.NOT_PURSUED,
}


def required_fields_for_status(status: str) -> list[str]:
    return BASE_REQUIREMENTS.get(status, [])


def _combined_requirements(*groups: list[str]) -> list[str]:
    return list(dict.fromkeys(field_name for group in groups for field_name in group))


def _missing_fields(use_case: UseCase, field_names: list[str]) -> list[str]:
    missing = []
    for field_name in field_names:
        value = getattr(use_case, field_name)
        if value in (None, ""):
            missing.append(
                FIELD_LABELS.get(
                    field_name,
                    str(use_case._meta.get_field(field_name).verbose_name),
                )
            )
    return missing


def intake_blockers(use_case: UseCase) -> list[str]:
    """Only minimal draft identity is an intake hard blocker in the lean policy."""

    return _missing_fields(use_case, INTAKE_REQUIREMENTS)


def _readiness_warnings(use_case: UseCase, fields: list[str]) -> list[str]:
    return [f"Readiness offen: {label}" for label in _missing_fields(use_case, fields)]


def check_pilot_start(use_case: UseCase) -> DecisionCheck:
    blockers: list[str] = []
    warnings = _readiness_warnings(
        use_case,
        _combined_requirements(
            BASE_REQUIREMENTS[UseCase.Status.PILOT],
            PILOT_METRIC_REQUIREMENTS,
        ),
    )
    if use_case.status != UseCase.Status.REVIEW:
        blockers.append(PILOT_STATUS_BLOCKER)
    if recorded_handover_package(use_case) is None:
        blockers.append(PILOT_HANDOVER_BLOCKER)
    if use_case.decision_status not in APPROVAL_STATUSES:
        blockers.append("Positive Freigabeentscheidung")
    if not current_governance_status(use_case).has_screening:
        blockers.append("Governance-Screening")
    blockers.extend(required_governance_blockers(use_case))
    if (
        use_case.metric_baseline is not None
        and use_case.metric_target is not None
        and use_case.metric_baseline == use_case.metric_target
    ):
        warnings.append("Baseline und Zielwert sind identisch; die Nutzenhypothese prüfen.")
    if use_case.planned_pilot_end and use_case.planned_pilot_end < timezone.localdate():
        warnings.append("Das geplante Pilotende liegt bereits in der Vergangenheit.")
    state = "blocked" if blockers else ("review" if warnings else "ready")
    return DecisionCheck(
        target_status=UseCase.Status.PILOT,
        state=state,
        title="Pilot starten",
        blockers=blockers,
        warnings=warnings,
    )


def check_go_live(
    use_case: UseCase,
    *,
    allow_early_go_live_exception: bool = False,
) -> DecisionCheck:
    del allow_early_go_live_exception
    blockers: list[str] = []
    warnings: list[str] = []
    if use_case.status != UseCase.Status.PILOT:
        blockers.append("Go-live ist ausschließlich aus Pilot möglich")
    blockers.extend(_missing_fields(use_case, GO_LIVE_CORE_REQUIREMENTS))
    if use_case.pilot_start is None:
        blockers.append("Tatsächlicher Pilotbeginn")
    elif use_case.metric_measured_at and use_case.metric_measured_at < use_case.pilot_start:
        blockers.append("Messdatum muss am oder nach dem tatsächlichen Pilotbeginn liegen")
    blockers.extend(required_governance_blockers(use_case))
    if not use_case.technical_owner_id:
        blockers.append("Technischer Owner")
    if not str(use_case.support_responsibility or "").strip():
        blockers.append("Support-Verantwortung")

    warnings.extend(
        _readiness_warnings(
            use_case,
            [
                "metric_measurement_period",
                "metric_evidence_url",
                "metric_measurement_method",
                "one_time_cost",
                "recurring_cost",
                "human_oversight",
                "next_review_date",
            ],
        )
    )
    if use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED:
        warnings.append(
            "Das Pilotziel wurde nicht erreicht. Ein Go-live benötigt eine ausdrückliche Ausnahme."
        )
    if use_case.planned_pilot_end and use_case.planned_pilot_end > timezone.localdate():
        warnings.append(
            "Das geplante Pilotende ist noch nicht erreicht; Evidenzlage bewusst prüfen."
        )
    state = "blocked" if blockers else ("review" if warnings else "ready")
    return DecisionCheck(
        target_status=UseCase.Status.OPERATION,
        state=state,
        title="Produktiv setzen",
        blockers=blockers,
        warnings=warnings,
    )


def decision_check_for_status(
    use_case: UseCase,
    target_status: str,
    *,
    allow_early_go_live_exception: bool = False,
) -> DecisionCheck:
    if target_status == UseCase.Status.PILOT:
        return check_pilot_start(use_case)
    if target_status == UseCase.Status.OPERATION:
        return check_go_live(
            use_case,
            allow_early_go_live_exception=allow_early_go_live_exception,
        )
    if target_status == UseCase.Status.REVIEW:
        blockers = []
        if use_case.status != UseCase.Status.IDEA:
            blockers.append("Review kann nur aus Idee gestartet werden")
        blockers.extend(intake_blockers(use_case))
        warnings = _readiness_warnings(
            use_case,
            ["problem_statement", "affected_process", "expected_benefit"],
        )
        return DecisionCheck(
            target_status=target_status,
            state="blocked" if blockers else ("review" if warnings else "ready"),
            title=UseCase.Status(target_status).label,
            blockers=blockers,
            warnings=warnings,
        )
    return DecisionCheck(
        target_status=target_status,
        state="ready",
        title=UseCase.Status(target_status).label,
    )


def current_decision_check(use_case: UseCase) -> DecisionCheck:
    if use_case.status == UseCase.Status.IDEA:
        return decision_check_for_status(use_case, UseCase.Status.REVIEW)
    if use_case.status == UseCase.Status.REVIEW:
        return check_pilot_start(use_case)
    if use_case.status == UseCase.Status.PILOT:
        return check_go_live(use_case)
    if use_case.status == UseCase.Status.OPERATION:
        warnings = []
        today = timezone.localdate()
        if use_case.next_review_date and use_case.next_review_date < today:
            warnings.append("Die Betriebsüberprüfung ist überfällig.")
        if use_case.metric_measured_at and (today - use_case.metric_measured_at).days > 180:
            warnings.append("Die letzte Nutzenmessung ist älter als 180 Tage.")
        return DecisionCheck(
            target_status=UseCase.Status.OPERATION,
            state="review" if warnings else "ready",
            title="Betrieb fortführen",
            warnings=warnings,
        )
    return DecisionCheck(
        target_status=UseCase.Status.ENDED,
        state="ready",
        title="Beendet",
    )


def decision_due_date(use_case: UseCase) -> date | None:
    if use_case.status == UseCase.Status.PILOT:
        return use_case.planned_pilot_end or use_case.next_review_date
    return use_case.next_review_date


def decision_priority(use_case: UseCase) -> tuple[int, date, str]:
    today = timezone.localdate()
    check = current_decision_check(use_case)
    due = decision_due_date(use_case)
    if due and due < today:
        bucket = 0
    elif check.state == "blocked":
        bucket = 1
    elif due and due <= today + timedelta(days=30):
        bucket = 2
    elif check.state == "review":
        bucket = 3
    else:
        bucket = 4
    return bucket, due or date.max, use_case.short_id


def validate_target_status(
    use_case: UseCase,
    target_status: str,
    *,
    allow_early_go_live_exception: bool = False,
) -> None:
    """Read-only compatibility check; lifecycle writes belong to reviews.create_review()."""

    check = decision_check_for_status(
        use_case,
        target_status,
        allow_early_go_live_exception=allow_early_go_live_exception,
    )
    if check.blockers:
        raise ValidationError("Für den Zielstatus fehlen: " + ", ".join(check.blockers))


def validate_pilot_start_date(*, use_case: UseCase, pilot_start: date | None) -> None:
    if pilot_start is None:
        raise ValidationError("Der tatsächliche Pilotbeginn ist erforderlich.")
    if pilot_start > timezone.localdate():
        raise ValidationError("Der tatsächliche Pilotbeginn darf nicht in der Zukunft liegen.")
    package = recorded_handover_package(use_case)
    if package is None:
        raise ValidationError(
            "Der Pilot kann erst nach der verbindlichen Übergabe des aktuellen "
            "Delivery Packages gestartet werden."
        )
    if pilot_start < timezone.localdate(package.handed_over_at):
        raise ValidationError(
            "Der tatsächliche Pilotbeginn darf nicht vor der verbindlichen Übergabe liegen."
        )


@transaction.atomic
def apply_status_transition(
    *,
    use_case: UseCase,
    target_status: str,
    actor,
    pilot_start: date | None = None,
    allow_early_go_live_exception: bool = False,
    **_kwargs,
) -> UseCase:
    """Compatibility fence: direct lifecycle writes are intentionally disabled.

    The canonical command path is ``reviews.services.create_review`` so Review artifact and
    lifecycle status cannot diverge. Keeping this function as a failing compatibility surface
    makes bypasses explicit instead of silently persisting an incomplete lifecycle event.
    """

    del use_case, target_status, actor, pilot_start, allow_early_go_live_exception
    raise ValidationError(
        "Lifecycle-Statusänderungen sind ausschließlich über "
        "reviews.services.create_review zulässig."
    )


def approval_check(
    *,
    use_case: UseCase,
    target_status: str,
    actor=None,
    governance_confirmed: bool = False,
) -> ApprovalCheck:
    del governance_confirmed
    blockers: list[str] = []
    warnings: list[str] = []

    if target_status not in FINAL_DECISION_STATUSES:
        return ApprovalCheck(blockers=["Unzulässiger Entscheidungsstatus"])

    assessment = use_case.decision_assessments.first()
    if target_status in APPROVAL_STATUSES:
        if assessment is None:
            blockers.append("Aktuelle strukturierte Bewertung")
        blockers.extend(_missing_fields(use_case, POSITIVE_APPROVAL_CORE_REQUIREMENTS))
        if assessment is not None and actor and assessment.assessed_by_id == actor.id:
            blockers.append("Bewertende und entscheidende Person müssen verschieden sein")
        if actor and use_case.business_owner_id == actor.id:
            blockers.append(
                "Fachlich verantwortliche und freigebende Person müssen verschieden sein"
            )
        if not current_governance_status(use_case).has_screening:
            blockers.append("Governance-Screening")
        blockers.extend(failed_required_governance_reviews(use_case))
        warnings.extend(open_required_governance_warnings(use_case))
        warnings.extend(_readiness_warnings(use_case, APPROVAL_METRIC_REQUIREMENTS))
        if assessment is not None:
            if assessment.confidence_level == UseCase.Level.LOW:
                warnings.append("Readiness offen: Confidence ist niedrig")
            if assessment.technical_feasibility == UseCase.Level.LOW:
                warnings.append("Readiness offen: Technische Machbarkeit ist niedrig")
            if assessment.data_readiness == UseCase.Level.LOW:
                warnings.append("Readiness offen: Datenreife ist niedrig")
            if assessment.risk_complexity == UseCase.Level.HIGH:
                warnings.append("Readiness offen: Risiko und Komplexität sind hoch")
    else:
        if assessment is None:
            warnings.append("Readiness offen: Keine strukturierte Bewertung vorhanden")
        elif actor and assessment.assessed_by_id == actor.id:
            warnings.append("Hinweis: Bewertende und entscheidende Person sind identisch")

    if assessment is not None and assessment.recommendation != target_status:
        warnings.append(
            "Die Entscheidung weicht von der Empfehlung der bewertenden Person ab "
            "und sollte begründet werden."
        )

    return ApprovalCheck(blockers=blockers, warnings=warnings)


@transaction.atomic
def create_decision_assessment(*, use_case: UseCase, actor, data) -> DecisionAssessment:
    if not is_coordinator(actor):
        raise PermissionDenied
    if use_case.status != UseCase.Status.REVIEW:
        raise ValidationError(
            "Eine strukturierte Bewertung ist ausschließlich im Status Review möglich."
        )
    if use_case.decision_status == UseCase.DecisionStatus.NOT_PURSUED:
        raise ValidationError(
            "Nicht weiterverfolgt ist terminal. Ein neuer Anlauf wird als neuer Use Case erfasst."
        )
    version = (
        use_case.decision_assessments.aggregate(max_version=Max("version"))["max_version"] or 0
    ) + 1
    assessment = DecisionAssessment(
        use_case=use_case,
        assessed_by=actor,
        version=version,
        **data,
    )
    assessment.save()
    use_case.business_value = assessment.business_value
    use_case.technical_feasibility = assessment.technical_feasibility
    use_case.data_readiness = assessment.data_readiness
    use_case.risk_complexity = assessment.risk_complexity
    use_case.decision_status = UseCase.DecisionStatus.READY
    use_case._history_user = actor
    use_case.save()
    return assessment


def eligible_second_approvers(*, use_case: UseCase, first_decider):
    assessment = use_case.decision_assessments.first()
    excluded_ids = {
        user_id
        for user_id in [
            getattr(first_decider, "id", None),
            assessment.assessed_by_id if assessment else None,
            use_case.business_owner_id,
        ]
        if user_id is not None
    }
    return (
        get_user_model()
        .objects.filter(is_active=True, is_anonymized=False)
        .filter(Q(is_superuser=True) | Q(groups__name__in=[GROUP_COORDINATOR, GROUP_TECH_ADMIN]))
        .exclude(pk__in=excluded_ids)
        .distinct()
        .order_by("last_name", "first_name", "username")
    )


def can_review_conditional_decision(*, decision: ApprovalDecision, actor) -> bool:
    if not decision.is_pending_second_approval or not is_coordinator(actor):
        return False
    return (
        eligible_second_approvers(
            use_case=decision.use_case,
            first_decider=decision.decided_by,
        )
        .filter(pk=actor.pk)
        .exists()
    )


def _save_approval_decision(**kwargs) -> ApprovalDecision:
    decision = ApprovalDecision(**kwargs)
    decision.full_clean()
    decision.save()
    return decision


@transaction.atomic
def submit_approval_decision(*, use_case: UseCase, actor, data) -> ApprovalDecision:
    if not is_coordinator(actor):
        raise PermissionDenied
    target_status = data["decision_status"]
    check = approval_check(
        use_case=use_case,
        target_status=target_status,
        actor=actor,
        governance_confirmed=data.get("governance_confirmed", False),
    )
    if check.blockers:
        raise ValidationError("Freigabe blockiert: " + ", ".join(check.blockers))

    assessment = use_case.decision_assessments.first()
    if target_status == UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS:
        if not all([data.get("conditions"), data.get("condition_owner")]):
            raise ValidationError("Eine Freigabe mit Auflagen benötigt Auflage und Verantwortung.")
        if use_case.approval_decisions.filter(
            decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            finalized_at__isnull=True,
            second_approval_returned_at__isnull=True,
        ).exists():
            raise ValidationError("Es besteht bereits eine offene zweite Freigabe.")
        assignee = data.get("second_approval_assignee")
        eligible = eligible_second_approvers(use_case=use_case, first_decider=actor)
        if assignee is None or not eligible.filter(pk=assignee.pk).exists():
            raise ValidationError(
                "Für die Freigabe mit Auflagen muss eine unabhängige berechtigte Person "
                "zur Zweitprüfung benannt werden."
            )
        return _save_approval_decision(
            use_case=use_case,
            assessment=assessment,
            decided_by=actor,
            second_approval_requested_at=timezone.now(),
            **data,
        )

    decision = _save_approval_decision(
        use_case=use_case,
        assessment=assessment,
        decided_by=actor,
        finalized_at=timezone.now(),
        **data,
    )
    use_case.decision_status = target_status
    use_case._history_user = actor
    use_case.save()
    return decision


@transaction.atomic
def confirm_conditional_decision(*, decision: ApprovalDecision, actor) -> ApprovalDecision:
    if not can_review_conditional_decision(decision=decision, actor=actor):
        raise PermissionDenied(
            "Für diese unabhängige Zweitprüfung fehlt die Berechtigung oder Personentrennung."
        )
    current_assessment = decision.use_case.decision_assessments.first()
    if (
        decision.assessment_id is None
        or current_assessment is None
        or decision.assessment_id != current_assessment.id
    ):
        raise ValidationError("Seit dem Vorschlag wurde eine neue Bewertung erstellt.")

    check = approval_check(
        use_case=decision.use_case,
        target_status=decision.decision_status,
        actor=decision.decided_by,
        governance_confirmed=decision.governance_confirmed,
    )
    if check.blockers:
        raise ValidationError("Freigabe blockiert: " + ", ".join(check.blockers))

    decision.second_approved_by = actor
    decision.finalized_at = timezone.now()
    decision.full_clean()
    decision.save(update_fields=["second_approved_by", "finalized_at", "updated_at"])
    decision.use_case.decision_status = decision.decision_status
    decision.use_case._history_user = actor
    decision.use_case.save()
    return decision


@transaction.atomic
def return_conditional_decision(
    *,
    decision: ApprovalDecision,
    actor,
    reason: str,
) -> ApprovalDecision:
    if not can_review_conditional_decision(decision=decision, actor=actor):
        raise PermissionDenied(
            "Für diese unabhängige Zweitprüfung fehlt die Berechtigung oder Personentrennung."
        )
    decision.second_approval_returned_by = actor
    decision.second_approval_returned_at = timezone.now()
    decision.second_approval_return_reason = reason.strip()
    decision.save(
        update_fields=[
            "second_approval_returned_by",
            "second_approval_returned_at",
            "second_approval_return_reason",
            "updated_at",
        ]
    )
    return decision
