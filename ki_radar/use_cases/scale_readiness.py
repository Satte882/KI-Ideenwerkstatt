from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from ki_radar.delivery.handover import current_handed_over_package
from ki_radar.governance.services import (
    current_governance_status,
    governance_review_evidence,
)

from .models import UseCase

SCALE_READINESS_SCHEMA_VERSION = 1

SCALE_EVIDENCE_FIELDS = (
    "scale_tailoring_level",
    "scale_pilot_validation_confirmed",
    "scale_production_version",
    "scale_rollback_tested",
    "scale_technical_monitoring_ready",
    "scale_ai_quality_monitoring_ready",
    "scale_incident_process_ready",
    "scale_extended_controls_completed",
    "scale_evidence_url",
    "ml_score_data",
    "ml_score_model",
    "ml_score_infrastructure",
    "ml_score_monitoring",
    "ml_score_minimum",
    "ml_score_version",
    "ml_score_date",
    "ml_score_evidence_url",
    "ml_score_open_core_checks",
    "ml_score_failed_mandatory_checks",
)

ML_SCORE_FIELDS = (
    ("ml_score_data", "Data", "data"),
    ("ml_score_model", "Model", "quality"),
    ("ml_score_infrastructure", "Infrastructure", "deployment"),
    ("ml_score_monitoring", "Monitoring", "monitoring"),
)

TAILORING_ORDER = {"A": 1, "B": 2, "C": 3}


@dataclass(frozen=True)
class ScaleReadinessFinding:
    code: str
    dimension: str
    severity: str
    message: str


@dataclass(frozen=True)
class ScaleReadinessDimension:
    key: str
    label: str
    state: str
    findings: tuple[ScaleReadinessFinding, ...]


@dataclass(frozen=True)
class ScaleReadinessResult:
    state: str
    dimensions: tuple[ScaleReadinessDimension, ...]
    findings: tuple[ScaleReadinessFinding, ...]
    final_ml_score: Decimal | None
    tailoring_level: str

    @property
    def blockers(self) -> tuple[ScaleReadinessFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "blocker")

    @property
    def conditions(self) -> tuple[ScaleReadinessFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "condition")

    @property
    def state_label(self) -> str:
        return {
            "ready": "GO · Bereit",
            "conditional": "CONDITIONAL GO · Bereit mit Auflagen",
            "not_ready": "NO-GO · Nicht bereit",
        }[self.state]


def extract_scale_evidence(data: dict) -> dict:
    return {name: data.pop(name, None) for name in SCALE_EVIDENCE_FIELDS}


def scale_evidence_from_mapping(data: Mapping | None) -> dict:
    if not data:
        return {}
    return {name: data.get(name) for name in SCALE_EVIDENCE_FIELDS}


def _text(value) -> str:
    return str(value or "").strip()


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"1", "true", "yes", "on"}


def _decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _iso(value) -> str:
    if value is None:
        return ""
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


def _display_name(user) -> str:
    if user is None:
        return ""
    display_name = getattr(user, "get_display_name", None)
    return display_name() if callable(display_name) else str(user)


def _add(
    findings: list[ScaleReadinessFinding],
    code: str,
    dimension: str,
    severity: str,
    message: str,
) -> None:
    findings.append(
        ScaleReadinessFinding(
            code=code,
            dimension=dimension,
            severity=severity,
            message=message,
        )
    )


def _minimum_tailoring(use_case: UseCase) -> str:
    assessment = current_governance_status(use_case).screening
    if assessment and any(
        getattr(assessment, field_name)
        for field_name in (
            "personal_data",
            "employee_data",
            "automated_person_assessment",
            "influences_person_decisions",
            "biometric_data",
            "safety_critical",
            "regulated_product",
            "health_safety_rights_impact",
        )
    ):
        return "C"
    return "A"


def _add_governance_findings(
    use_case: UseCase,
    findings: list[ScaleReadinessFinding],
) -> None:
    governance = current_governance_status(use_case)
    for state in governance.required_reviews:
        prefix = f"GOVERNANCE_{state.definition.review_type.upper()}"
        label = state.definition.short_label
        if not state.completed:
            if state.failed:
                _add(
                    findings,
                    f"{prefix}_FAILED",
                    "responsibility",
                    "blocker",
                    f"{label} wurde nicht bestanden.",
                )
            else:
                _add(
                    findings,
                    f"{prefix}_OPEN",
                    "responsibility",
                    "blocker",
                    f"{label} ist als erforderliche formale Prüfung noch offen.",
                )
            continue
        if state.conditionally_passed:
            _add(
                findings,
                f"{prefix}_CONDITIONAL",
                "responsibility",
                "condition",
                f"{label} ist nur mit dokumentierten Auflagen freigegeben.",
            )


def _evaluate_tailoring(
    use_case: UseCase,
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> str:
    tailoring = _text(data.get("scale_tailoring_level")).upper()
    minimum = _minimum_tailoring(use_case)
    if tailoring not in TAILORING_ORDER:
        _add(
            findings,
            "TAILORING_MISSING",
            "responsibility",
            "blocker",
            "Tailoring-Stufe A, B oder C muss für die Scale-Entscheidung festgelegt sein.",
        )
        return ""
    if TAILORING_ORDER[tailoring] < TAILORING_ORDER[minimum]:
        _add(
            findings,
            "TAILORING_TOO_LOW",
            "responsibility",
            "blocker",
            (
                f"Die gewählte Tailoring-Stufe {tailoring} unterschreitet die aus dem "
                f"Governance-Kontext erforderliche Mindeststufe {minimum}."
            ),
        )
    return tailoring


def _evaluate_pilot(
    use_case: UseCase,
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> None:
    if use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED:
        _add(
            findings,
            "PILOT_TARGET_NOT_ACHIEVED",
            "pilot",
            "condition",
            "Das definierte Pilotziel wurde nicht erreicht.",
        )
    if not _bool(data.get("scale_pilot_validation_confirmed")):
        _add(
            findings,
            "PILOT_VALIDATION_NOT_CONFIRMED",
            "pilot",
            "blocker",
            (
                "Pilotumfang, Repräsentativität sowie relevante Fehler- und Ausnahmefälle "
                "müssen für den geplanten Produktivscope bestätigt sein."
            ),
        )


def _evaluate_ml_score(
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> Decimal | None:
    ml_scores: list[Decimal] = []
    for field_name, label, dimension in ML_SCORE_FIELDS:
        value = _decimal(data.get(field_name))
        code_name = field_name.removeprefix("ml_score_").upper()
        if value is None:
            _add(
                findings,
                f"ML_SCORE_{code_name}_MISSING",
                dimension,
                "blocker",
                f"Der aktuelle ML-Test-Score für {label} fehlt.",
            )
        elif not Decimal("0") <= value <= Decimal("7"):
            _add(
                findings,
                f"ML_SCORE_{code_name}_INVALID",
                dimension,
                "blocker",
                f"Der ML-Test-Score für {label} muss zwischen 0 und 7 liegen.",
            )
        else:
            ml_scores.append(value)

    final_score = min(ml_scores) if len(ml_scores) == len(ML_SCORE_FIELDS) else None
    minimum = _decimal(data.get("ml_score_minimum"))
    if minimum is None:
        _add(
            findings,
            "ML_SCORE_MINIMUM_MISSING",
            "quality",
            "blocker",
            "Der projektspezifische ML-Test-Score-Mindestwert fehlt.",
        )
    elif not Decimal("0") <= minimum <= Decimal("7"):
        _add(
            findings,
            "ML_SCORE_MINIMUM_INVALID",
            "quality",
            "blocker",
            ("Der projektspezifische ML-Test-Score-Mindestwert muss zwischen 0 und 7 liegen."),
        )
    elif final_score is not None and final_score < minimum:
        _add(
            findings,
            "ML_SCORE_BELOW_MINIMUM",
            "quality",
            "blocker",
            (
                f"Der ML-Test-Score {final_score} unterschreitet den "
                f"projektspezifischen Mindestwert {minimum}."
            ),
        )

    required_text = (
        ("ml_score_version", "ML_SCORE_VERSION_MISSING", "Version der aktuellen Erhebung fehlt."),
        (
            "ml_score_evidence_url",
            "ML_SCORE_EVIDENCE_MISSING",
            "Nachweisreferenz der aktuellen ML-Test-Score-Erhebung fehlt.",
        ),
    )
    for field_name, code, message in required_text:
        if not _text(data.get(field_name)):
            _add(findings, code, "quality", "blocker", message)
    if not data.get("ml_score_date"):
        _add(
            findings,
            "ML_SCORE_DATE_MISSING",
            "quality",
            "blocker",
            "Datum der aktuellen ML-Test-Score-Erhebung fehlt.",
        )
    if _text(data.get("ml_score_failed_mandatory_checks")):
        _add(
            findings,
            "ML_SCORE_MANDATORY_CHECK_FAILED",
            "quality",
            "blocker",
            "Mindestens eine zwingende ML-Test-Score-Einzelprüfung ist nicht erfüllt.",
        )
    if _text(data.get("ml_score_open_core_checks")):
        _add(
            findings,
            "ML_SCORE_CORE_CHECKS_OPEN",
            "quality",
            "condition",
            "Im ML-Test-Score bestehen noch dokumentierte offene Kernprüfungen.",
        )
    return final_score


def _evaluate_deployment(
    use_case: UseCase,
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> None:
    if current_handed_over_package(use_case) is None:
        _add(
            findings,
            "DELIVERY_HANDOVER_MISSING",
            "deployment",
            "blocker",
            "Das aktuelle Delivery Package ist nicht verbindlich übergeben.",
        )
    if not _text(data.get("scale_production_version")):
        _add(
            findings,
            "PRODUCTION_VERSION_MISSING",
            "deployment",
            "blocker",
            "Die freigegebene Produktivversion ist nicht eindeutig identifiziert.",
        )
    if not _bool(data.get("scale_rollback_tested")):
        _add(
            findings,
            "ROLLBACK_NOT_TESTED",
            "deployment",
            "blocker",
            "Rollback oder Deaktivierung wurde nicht praktisch getestet.",
        )


def _evaluate_operations(
    tailoring: str,
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> None:
    operation_rules = (
        (
            "scale_evidence_url",
            "OPERATIONS_EVIDENCE_MISSING",
            "Nachweisreferenz für Release-, Monitoring- und Betriebsfähigkeit fehlt.",
        ),
        (
            "scale_technical_monitoring_ready",
            "TECHNICAL_MONITORING_MISSING",
            "Technisches Monitoring und Alarmierung sind nicht nachgewiesen.",
        ),
        (
            "scale_ai_quality_monitoring_ready",
            "AI_QUALITY_MONITORING_MISSING",
            "AI-/fachliches Qualitätsmonitoring ist nicht nachgewiesen.",
        ),
    )
    for field_name, code, message in operation_rules:
        value = (
            _text(data.get(field_name))
            if field_name.endswith("_url")
            else _bool(data.get(field_name))
        )
        if not value:
            _add(findings, code, "monitoring", "blocker", message)

    if tailoring in {"B", "C"} and not _bool(data.get("scale_incident_process_ready")):
        _add(
            findings,
            "INCIDENT_PROCESS_MISSING",
            "monitoring",
            "blocker",
            ("Incident- und Eskalationsprozess ist für dieses Tailoring nicht nachgewiesen."),
        )


def _evaluate_responsibility(
    use_case: UseCase,
    tailoring: str,
    data: dict,
    findings: list[ScaleReadinessFinding],
) -> None:
    responsibility_rules = (
        (bool(use_case.business_owner_id), "BUSINESS_OWNER_MISSING", "Business Owner fehlt."),
        (bool(use_case.technical_owner_id), "TECHNICAL_OWNER_MISSING", "Technical Owner fehlt."),
        (
            bool(_text(use_case.support_responsibility)),
            "SUPPORT_RESPONSIBILITY_MISSING",
            "Betriebs- und Supportverantwortung ist nicht geklärt.",
        ),
        (
            bool(_text(use_case.human_oversight)),
            "HUMAN_OVERSIGHT_MISSING",
            "Human Oversight ist nicht geklärt.",
        ),
    )
    for present, code, message in responsibility_rules:
        if not present:
            _add(findings, code, "responsibility", "blocker", message)

    _add_governance_findings(use_case, findings)
    if tailoring == "C" and not _bool(data.get("scale_extended_controls_completed")):
        _add(
            findings,
            "EXTENDED_CONTROLS_MISSING",
            "responsibility",
            "blocker",
            (
                "Die zusätzlichen Nachweise für Tailoring C "
                "(z. B. unabhängiges Review, Recovery/Security und Abschaltverfahren) "
                "sind nicht vollständig bestätigt."
            ),
        )


def evaluate_scale_readiness(
    use_case: UseCase,
    evidence: Mapping | None = None,
) -> ScaleReadinessResult:
    data = scale_evidence_from_mapping(evidence)
    findings: list[ScaleReadinessFinding] = []

    tailoring = _evaluate_tailoring(use_case, data, findings)
    _evaluate_pilot(use_case, data, findings)
    final_ml_score = _evaluate_ml_score(data, findings)
    _evaluate_deployment(use_case, data, findings)
    _evaluate_operations(tailoring, data, findings)
    _evaluate_responsibility(use_case, tailoring, data, findings)

    dimension_labels = (
        ("pilot", "Pilot-Evidenz / Wirkung"),
        ("data", "Daten & Wissen"),
        ("quality", "AI-/Systemqualität"),
        ("deployment", "Deployment & technische Robustheit"),
        ("monitoring", "Monitoring & Betrieb"),
        ("responsibility", "Verantwortung, Governance & Restrisiko"),
    )
    dimensions: list[ScaleReadinessDimension] = []
    for key, label in dimension_labels:
        dimension_findings = tuple(item for item in findings if item.dimension == key)
        if any(item.severity == "blocker" for item in dimension_findings):
            state = "not_ready"
        elif any(item.severity == "condition" for item in dimension_findings):
            state = "conditional"
        else:
            state = "ready"
        dimensions.append(
            ScaleReadinessDimension(
                key=key,
                label=label,
                state=state,
                findings=dimension_findings,
            )
        )

    if any(item.severity == "blocker" for item in findings):
        state = "not_ready"
    elif any(item.severity == "condition" for item in findings):
        state = "conditional"
    else:
        state = "ready"

    return ScaleReadinessResult(
        state=state,
        dimensions=tuple(dimensions),
        findings=tuple(findings),
        final_ml_score=final_ml_score,
        tailoring_level=tailoring,
    )


def build_scale_readiness_snapshot(
    use_case: UseCase,
    evidence: Mapping | None,
    result: ScaleReadinessResult,
) -> dict:
    data = scale_evidence_from_mapping(evidence)
    package = current_handed_over_package(use_case)
    governance_reviews = [
        {
            "id": review.pk,
            "type": review.review_type,
            "status": review.status,
            "result": review.result,
            "reviewed_at": _iso(review.reviewed_at),
            "evidence_url": review.evidence_url,
        }
        for review in governance_review_evidence(use_case)
    ]
    return {
        "schema_version": SCALE_READINESS_SCHEMA_VERSION,
        "captured_at": timezone.now().isoformat(),
        "state": result.state,
        "tailoring_level": result.tailoring_level,
        "dimensions": [
            {
                "key": dimension.key,
                "label": dimension.label,
                "state": dimension.state,
            }
            for dimension in result.dimensions
        ],
        "pilot": {
            "use_case_id": str(use_case.pk),
            "pilot_start": _iso(use_case.pilot_start),
            "metric_result": use_case.metric_result,
            "metric_measured_at": _iso(use_case.metric_measured_at),
            "metric_evidence_url": use_case.metric_evidence_url,
            "validation_confirmed": _bool(data.get("scale_pilot_validation_confirmed")),
        },
        "delivery": {
            "package_id": str(package.pk) if package else "",
            "package_version": package.version if package else None,
            "handed_over_at": _iso(package.handed_over_at) if package else "",
            "production_version": _text(data.get("scale_production_version")),
            "operations_evidence_url": _text(data.get("scale_evidence_url")),
        },
        "ml_test_score": {
            "data": str(_decimal(data.get("ml_score_data")) or ""),
            "model": str(_decimal(data.get("ml_score_model")) or ""),
            "infrastructure": str(_decimal(data.get("ml_score_infrastructure")) or ""),
            "monitoring": str(_decimal(data.get("ml_score_monitoring")) or ""),
            "final": str(result.final_ml_score or ""),
            "minimum": str(_decimal(data.get("ml_score_minimum")) or ""),
            "version": _text(data.get("ml_score_version")),
            "date": _iso(data.get("ml_score_date")),
            "evidence_url": _text(data.get("ml_score_evidence_url")),
            "open_core_checks": _text(data.get("ml_score_open_core_checks")),
            "failed_mandatory_checks": _text(data.get("ml_score_failed_mandatory_checks")),
        },
        "operations": {
            "rollback_tested": _bool(data.get("scale_rollback_tested")),
            "technical_monitoring_ready": _bool(data.get("scale_technical_monitoring_ready")),
            "ai_quality_monitoring_ready": _bool(data.get("scale_ai_quality_monitoring_ready")),
            "incident_process_ready": _bool(data.get("scale_incident_process_ready")),
            "extended_controls_completed": _bool(data.get("scale_extended_controls_completed")),
        },
        "governance_reviews": governance_reviews,
        "roles": {
            "business_owner_id": str(use_case.business_owner_id or ""),
            "business_owner": _display_name(use_case.business_owner),
            "technical_owner_id": str(use_case.technical_owner_id or ""),
            "technical_owner": _display_name(use_case.technical_owner),
        },
        "findings": [
            {
                "code": finding.code,
                "dimension": finding.dimension,
                "severity": finding.severity,
                "message": finding.message,
            }
            for finding in result.findings
        ],
    }


_original_apply_status_transition = None


def _apply_status_transition_with_scale_readiness(
    *,
    use_case: UseCase,
    target_status: str,
    actor,
    pilot_start=None,
    allow_early_go_live_exception: bool = False,
    scale_evidence: Mapping | None = None,
):
    if _original_apply_status_transition is None:
        raise RuntimeError("Scale Readiness enforcement is not installed.")

    if target_status == UseCase.Status.OPERATION and use_case.status == UseCase.Status.PILOT:
        result = evaluate_scale_readiness(use_case, scale_evidence)
        if result.blockers:
            raise ValidationError(
                "Scale Readiness blockiert: "
                + "; ".join(finding.message for finding in result.blockers)
            )

    return _original_apply_status_transition(
        use_case=use_case,
        target_status=target_status,
        actor=actor,
        pilot_start=pilot_start,
        allow_early_go_live_exception=allow_early_go_live_exception,
    )


def install() -> None:
    global _original_apply_status_transition

    from . import services

    if services.apply_status_transition is _apply_status_transition_with_scale_readiness:
        return
    _original_apply_status_transition = services.apply_status_transition
    services.apply_status_transition = _apply_status_transition_with_scale_readiness
