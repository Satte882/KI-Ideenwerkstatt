from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import floor

METHOD_VERSION = "1.7.0"

WEIGHTS = {
    "business_value": 0.24,
    "handoff_friction": 0.16,
    "context_proximity": 0.16,
    "ai_leverage": 0.20,
    "recurrence": 0.14,
    "data_readiness": 0.10,
}

BOUNDARY_WEIGHTS = {
    "judgment_stakes": 0.55,
    "specialist_accountability": 0.45,
}

TASK_CRITERIA = (*WEIGHTS.keys(), *BOUNDARY_WEIGHTS.keys())

RECOMMENDATION_LABELS = {
    "prepare-only": "Vorbereiten, nicht freigeben",
    "own": "Übernehmen + pilotieren",
    "own-with-approval": "Übernehmen + Fachfreigabe",
    "explore": "Gezielt explorieren",
    "keep-handoff": "Handoff vorerst beibehalten",
}

RECOMMENDATION_RATIONALES = {
    "prepare-only": (
        "Hoher fachlicher oder regulatorischer Verantwortungsanteil. Die Rolle kann "
        "Analyse und Vorbereitung übernehmen; Entscheidung und Freigabe bleiben beim Spezialisten."
    ),
    "own": (
        "Hoher Erweiterungsnutzen bei überschaubarer Verantwortungsgrenze. Die Aufgabe "
        "ist ein guter Kandidat für eine direkte Rollenerweiterung innerhalb "
        "definierter Leitplanken."
    ),
    "own-with-approval": (
        "Hoher Erweiterungsnutzen, aber relevante fachliche Verantwortung. Durchführung "
        "kann in die Rolle wandern; Freigabe bleibt beim benannten Spezialisten."
    ),
    "explore": (
        "Das Potenzial ist noch nicht eindeutig. Mit realen Fällen testen, wo die Grenze "
        "zwischen eigener Durchführung, KI-Unterstützung und Spezialisten-Handoff liegt."
    ),
    "keep-handoff": (
        "Der erwartete Nutzen einer Aufgabenverschiebung ist aktuell zu gering oder die "
        "Voraussetzungen fehlen. Erst Prozessfriktion, Datenlage oder KI-Eignung verbessern."
    ),
}


@dataclass(frozen=True)
class TaskValidation:
    complete: bool
    missing: tuple[str, ...]
    invalid: tuple[str, ...]


@dataclass(frozen=True)
class WorkDesignResult:
    potential_score: int
    boundary_score: int
    recommendation: str
    recommendation_label: str
    rationale: str
    approval_required: bool
    ai_mode: str
    design_pattern: str
    control_point: str


def _js_round(value: float) -> int:
    """Match JavaScript Math.round for the non-negative TASKSHIFT score domain."""

    return floor(value + 0.5)


def validate_task(criteria: Mapping[str, object] | None) -> TaskValidation:
    values = criteria or {}
    missing: list[str] = []
    invalid: list[str] = []

    for key in TASK_CRITERIA:
        value = values.get(key)
        if value is None or value == "":
            missing.append(key)
            continue
        if isinstance(value, bool):
            invalid.append(key)
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            invalid.append(key)
            continue
        if numeric < 0 or numeric > 4 or not numeric.is_integer():
            invalid.append(key)

    return TaskValidation(
        complete=not missing and not invalid,
        missing=tuple(missing),
        invalid=tuple(invalid),
    )


def _require_complete(criteria: Mapping[str, object]) -> None:
    validation = validate_task(criteria)
    if not validation.complete:
        fields = ", ".join((*validation.missing, *validation.invalid))
        raise ValueError(f"Unvollständige oder ungültige TASKSHIFT-Bewertung: {fields}")


def expansion_potential(criteria: Mapping[str, object]) -> int:
    _require_complete(criteria)
    weighted = sum(float(criteria[key]) * weight for key, weight in WEIGHTS.items())
    return _js_round((weighted / 4) * 100)


def human_boundary(criteria: Mapping[str, object]) -> int:
    _require_complete(criteria)
    weighted = sum(float(criteria[key]) * weight for key, weight in BOUNDARY_WEIGHTS.items())
    return _js_round((weighted / 4) * 100)


def recommendation_for(*, potential_score: int, boundary_score: int) -> str:
    if boundary_score >= 75 and potential_score >= 55:
        return "prepare-only"
    if potential_score >= 70 and boundary_score < 40:
        return "own"
    if potential_score >= 70:
        return "own-with-approval"
    if potential_score >= 50:
        return "explore"
    return "keep-handoff"


def ai_mode(criteria: Mapping[str, object], *, boundary_score: int) -> str:
    ai = int(criteria["ai_leverage"])
    recurrence = int(criteria["recurrence"])
    data = int(criteria["data_readiness"])

    if data <= 1 or ai <= 1:
        return "Exploration"
    if boundary_score >= 60:
        return "Collaboration"
    if ai >= 3 and recurrence >= 3:
        return "Delegation"
    if recurrence <= 1:
        return "Asking"
    return "Collaboration"


def design_pattern(criteria: Mapping[str, object]) -> str:
    friction = int(criteria["handoff_friction"])
    recurrence = int(criteria["recurrence"])
    ai = int(criteria["ai_leverage"])
    proximity = int(criteria["context_proximity"])

    if friction >= 3 and recurrence >= 3 and proximity >= 2:
        return "AI-Powered Process Redesign"
    if ai >= 4 and recurrence <= 2:
        return "AI-First Possibility"
    return "Persona Acceleration"


def control_point(boundary_score: int) -> str:
    if boundary_score >= 75:
        return (
            "Verpflichtender menschlicher Freigabepunkt; KI darf vorbereiten, "
            "aber nicht final freigeben."
        )
    if boundary_score >= 40:
        return (
            "Definierter Review- oder Freigabepunkt bleibt Teil des Arbeitsablaufs; "
            "Ausnahmen werden eskaliert."
        )
    return "Ausführung innerhalb dokumentierter Leitplanken; Ausnahmen werden eskaliert."


def score_task(criteria: Mapping[str, object]) -> WorkDesignResult:
    _require_complete(criteria)
    potential = expansion_potential(criteria)
    boundary = human_boundary(criteria)
    recommendation = recommendation_for(
        potential_score=potential,
        boundary_score=boundary,
    )
    return WorkDesignResult(
        potential_score=potential,
        boundary_score=boundary,
        recommendation=recommendation,
        recommendation_label=RECOMMENDATION_LABELS[recommendation],
        rationale=RECOMMENDATION_RATIONALES[recommendation],
        approval_required=recommendation in {"prepare-only", "own-with-approval"},
        ai_mode=ai_mode(criteria, boundary_score=boundary),
        design_pattern=design_pattern(criteria),
        control_point=control_point(boundary),
    )


def build_solution_source_snapshot(task) -> dict[str, object]:
    validation = validate_task(task.criteria)
    if not validation.complete:
        raise ValueError(
            "Nur vollständig bewertete Aufgaben können in den Lösungsraum überführt werden."
        )

    result = score_task(task.criteria)
    assessment = task.assessment
    process_analysis = assessment.process_analysis

    return {
        "schema": "taskshift.solution_origin.v1",
        "method_version": assessment.method_version,
        "assessment_id": str(assessment.pk),
        "assessment_version": assessment.version,
        "process_analysis_id": str(process_analysis.pk),
        "process_version": assessment.process_version,
        "role_name": assessment.role_name,
        "business_outcome": assessment.business_outcome,
        "task_id": str(task.pk),
        "task_updated_at": task.updated_at.isoformat(),
        "task_name": task.name,
        "source_area": task.source_area,
        "target_work_split": task.target_work_split,
        "approval_role": task.approval_role,
        "criteria": {key: int(task.criteria[key]) for key in TASK_CRITERIA},
        "potential_score": result.potential_score,
        "boundary_score": result.boundary_score,
        "recommendation": result.recommendation,
        "recommendation_label": result.recommendation_label,
        "approval_required": result.approval_required,
        "ai_mode": result.ai_mode,
        "design_pattern": result.design_pattern,
        "control_point": result.control_point,
    }
