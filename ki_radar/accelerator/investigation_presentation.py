from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .investigation_models import InvestigationRun, InvestigationStep

_FIELD_LABELS = {
    "approval_hours": "Freigabedauer (Stunden)",
    "approver_available": "Freigeber verfügbar",
    "queue_retries": "Queue-Wiederholungen",
    "missing_info": "fehlende Informationen",
    "total_eligible": "Gesamtzahl freigabepflichtiger Vorgänge",
    "escalations": "Eskalationen",
    "period": "Zeitraum",
}

_TOOL_LABELS = {
    "read_source": "Quelle geprüft",
    "search_sources": "Quellen nach relevanten Belegen durchsucht",
    "profile_csv": "Datengrundlage geprüft",
    "compare_groups": "Gruppenvergleich reproduzierbar berechnet",
}

_INLINE_TOOL_LABELS = {
    "read_source": "Quellenprüfung",
    "search_sources": "Quellensuche",
    "profile_csv": "Datenprüfung",
    "compare_groups": "Gruppenvergleich",
}

_PROGRESS_LABELS = {
    InvestigationStep.ProgressKind.NONE: "Kein neuer entscheidungsrelevanter Befund",
    InvestigationStep.ProgressKind.EVIDENCE: "Neuer Beleg",
    InvestigationStep.ProgressKind.REFUTATION: "Alternative Erklärung geschwächt",
    InvestigationStep.ProgressKind.CONTRADICTION: "Widerspruch entdeckt",
    InvestigationStep.ProgressKind.COVERAGE: "Weitere Evidenz abgedeckt",
}


def humanize_investigation_text(value: object) -> str:
    text = str(value or "").strip()
    for field_name, label in _FIELD_LABELS.items():
        text = re.sub(rf"\b{re.escape(field_name)}\b", label, text)
    for tool_name, label in _INLINE_TOOL_LABELS.items():
        text = re.sub(rf"\b{re.escape(tool_name)}\b", label, text)
    return text


def _count_population_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return None


def population_summary(population: object) -> str:
    if not isinstance(population, Mapping) or not population:
        return ""

    parts: list[str] = []
    rows_total = _count_population_value(population.get("rows_total"))
    included = _count_population_value(population.get("included_rows"))
    aggregated = _count_population_value(population.get("aggregated_rows"))
    matched = _count_population_value(population.get("filter_matched_rows"))

    if rows_total is not None:
        parts.append(f"{rows_total} Datensätze")
    if included is not None and included != rows_total:
        parts.append(f"{included} einbezogen")
    if matched is not None and matched not in {rows_total, included}:
        parts.append(f"{matched} nach Filter")
    if aggregated is not None and aggregated not in {rows_total, included, matched}:
        parts.append(f"{aggregated} ausgewertet")

    return " · ".join(parts) or "Datenbasis dokumentiert"


def _hypothesis_status(item: Mapping[str, Any]) -> tuple[str, str]:
    status = str(item.get("status") or "open")
    if status == "supported":
        return "Durch aktuelle Evidenz gestützt", "ready"
    if status == "refuted" and item.get("counterevidence_refs"):
        return "Gegenbeleg vorhanden", "review"
    if status == "refuted":
        return "Durch aktuelle Evidenz nicht gestützt", "review"
    if status == "conflicting":
        return "Widersprüchliche Evidenz", "review"
    return "Noch offen", "neutral"


def present_hypotheses(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in payload.get("hypotheses", []):
        if not isinstance(raw, Mapping):
            continue
        label, tone = _hypothesis_status(raw)
        result.append(
            {
                "statement": humanize_investigation_text(raw.get("statement")),
                "status_label": label,
                "tone": tone,
                "references": list(raw.get("references") or []),
                "counterevidence_refs": list(raw.get("counterevidence_refs") or []),
                "raw_status": str(raw.get("status") or ""),
            }
        )
    return result


def present_calculations(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in payload.get("calculations", []):
        if not isinstance(raw, Mapping):
            continue
        reference = raw.get("reference") if isinstance(raw.get("reference"), Mapping) else {}
        result.append(
            {
                "summary": humanize_investigation_text(raw.get("summary")),
                "population_summary": population_summary(raw.get("population")),
                "limits": humanize_investigation_text(raw.get("limits")),
                "reference": dict(reference),
                "raw_population": raw.get("population") or {},
            }
        )
    return result


def present_options(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in payload.get("options", []):
        if not isinstance(raw, Mapping):
            continue
        result.append(
            {
                "name": humanize_investigation_text(raw.get("name")),
                "description": humanize_investigation_text(raw.get("description")),
                "expected_value": humanize_investigation_text(raw.get("expected_value")),
                "risks": humanize_investigation_text(raw.get("risks")),
                "non_ai": bool(raw.get("non_ai")),
                "status_quo": bool(raw.get("status_quo")),
            }
        )
    return result


def present_investigation_steps(run: InvestigationRun) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for step in run.steps.all():
        result.append(
            {
                "sequence": step.sequence,
                "action_label": _TOOL_LABELS.get(step.tool_name, "Analyseschritt ausgeführt"),
                "progress_label": _PROGRESS_LABELS.get(
                    step.progress_kind,
                    step.get_progress_kind_display(),
                ),
                "expected_finding": humanize_investigation_text(
                    step.expected_discriminating_finding
                ),
                "tool_name": step.tool_name,
                "target_claim_id": step.target_claim_id,
                "status": step.get_status_display(),
            }
        )
    return result


def _supported_finding(
    payload: Mapping[str, Any],
    hypotheses: list[dict[str, Any]],
    calculations: list[dict[str, Any]],
) -> str:
    for item in hypotheses:
        if item["raw_status"] == "supported" and item["statement"]:
            return item["statement"]
    for item in calculations:
        if item["summary"]:
            return item["summary"]
    problem = payload.get("problem")
    if isinstance(problem, Mapping):
        return humanize_investigation_text(problem.get("statement"))
    return ""


def _clarification_text(run: InvestigationRun, key: str) -> str:
    payload = run.clarification_payload
    if not isinstance(payload, Mapping):
        return ""
    return humanize_investigation_text(payload.get(key))


def _frozen_process_text(run: InvestigationRun, key: str) -> str:
    base = run.execution_snapshot.get("domain_materialization_base")
    if not isinstance(base, Mapping):
        return ""
    process = base.get("process")
    if not isinstance(process, Mapping):
        return ""
    return humanize_investigation_text(process.get(key))


def build_decision_surface(
    *,
    run: InvestigationRun,
    policy,
    latest_materialization,
    materialization_preview,
) -> dict[str, Any]:
    payload = run.brief_payload if isinstance(run.brief_payload, Mapping) else {}
    question_scope = (
        payload.get("question_scope") if isinstance(payload.get("question_scope"), Mapping) else {}
    )
    problem = payload.get("problem") if isinstance(payload.get("problem"), Mapping) else {}
    recommendation = (
        payload.get("recommendation") if isinstance(payload.get("recommendation"), Mapping) else {}
    )

    hypotheses = present_hypotheses(payload)
    calculations = present_calculations(payload)
    options = present_options(payload)
    risks = [
        humanize_investigation_text(item)
        for item in payload.get("risks_unknowns", [])
        if str(item or "").strip()
    ]

    clarification_question = _clarification_text(run, "question")
    needed_evidence = _clarification_text(run, "needed_evidence")
    required_action = _clarification_text(run, "required_action")
    clarification_impact = _clarification_text(run, "impact")

    problem_statement = humanize_investigation_text(problem.get("statement"))
    frozen_problem = _frozen_process_text(run, "diagnostic_observations")
    situation = problem_statement or frozen_problem or humanize_investigation_text(run.decision_question)
    scope = humanize_investigation_text(question_scope.get("scope"))
    if not scope and situation != humanize_investigation_text(run.decision_question):
        scope = f"Fragestellung: {humanize_investigation_text(run.decision_question)}"

    finding = _supported_finding(payload, hypotheses, calculations)
    if not finding and run.clarification_reason == "missing_evidence":
        if needed_evidence:
            finding = f"Entscheidungskritischer Nachweis fehlt: {needed_evidence}"
        else:
            finding = clarification_impact

    policy_outcome = str(policy.outcome)
    ready_for_decision = (
        policy_outcome == "READY_FOR_DECISION" and run.status == InvestigationRun.Status.READY
    )
    clarification_required = (
        policy_outcome == "HUMAN_CLARIFICATION"
        or run.status == InvestigationRun.Status.WAITING_HUMAN
    )

    status_label = "Untersuchung läuft"
    status_detail = "Die Evidenzprüfung ist noch nicht abgeschlossen."
    status_tone = "neutral"
    technical_status_label = {
        InvestigationRun.Status.RUNNING: "Technische Untersuchung läuft",
        InvestigationRun.Status.WAITING_HUMAN: "Technisch auf Klärung wartend",
        InvestigationRun.Status.READY: "Technisch abgeschlossen",
        InvestigationRun.Status.FAILED: "Technisch fehlgeschlagen",
        InvestigationRun.Status.ABORTED: "Technisch beendet",
    }.get(run.status, run.status)

    if run.status == InvestigationRun.Status.ABORTED:
        status_label = "Untersuchung beendet"
        status_detail = (
            "Der Lauf wurde beendet. Aus diesem Stand wird keine fachliche "
            "Lösungsentscheidung abgeleitet."
        )
        status_tone = "review"
    elif run.status == InvestigationRun.Status.FAILED:
        status_label = "Technische Prüfung fehlgeschlagen"
        status_detail = (
            "Der Lauf ist technisch fehlgeschlagen. Aus diesem Stand darf kein "
            "fachlicher Schluss abgeleitet werden."
        )
        status_tone = "danger"
    elif ready_for_decision:
        status_label = "Entscheidungsgrundlage bereit"
        status_detail = "Die Evidenz ist geprüft; die fachliche Lösungsentscheidung ist noch offen."
        status_tone = "ready"
    elif clarification_required:
        status_label = "Klärung erforderlich"
        status_detail = (
            clarification_impact
            or "Für die Richtungsentscheidung fehlt noch eine entscheidungskritische Information."
        )
        status_tone = "review"
    elif run.status == InvestigationRun.Status.READY:
        status_label = "Entscheidungsgrundlage noch unvollständig"
        status_detail = (
            "Der gespeicherte Stand erfüllt die aktuelle Readiness-Prüfung noch nicht. "
            "Aus diesem Stand wird keine fachliche Empfehlung abgeleitet."
        )
        status_tone = "review"

    if ready_for_decision:
        recommendation_summary = humanize_investigation_text(recommendation.get("summary"))
        recommendation_rationale = humanize_investigation_text(recommendation.get("rationale"))
    else:
        recommendation_summary = "Noch keine belastbare Empfehlung aus diesem Lauf."
        recommendation_rationale = clarification_impact or status_detail

    if ready_for_decision and latest_materialization:
        next_action = {
            "kind": "compare",
            "title": "Lösungsoptionen fachlich vergleichen",
            "description": (
                "Die Entwürfe sind im kanonischen Lösungsraum angekommen. Dort Kandidaten "
                "bearbeiten, bewerten oder nicht weiter verfolgen und erst dort eine "
                "bevorzugte Option auswählen."
            ),
        }
    elif ready_for_decision and materialization_preview is not None:
        next_action = {
            "kind": "handoff",
            "title": "Entwürfe vor der Übergabe prüfen",
            "description": (
                "Prüfen Sie die geplanten Änderungen und übergeben Sie nur bestätigte "
                "Entwürfe in den bestehenden Lösungsraum."
            ),
        }
    elif clarification_required and run.status == InvestigationRun.Status.WAITING_HUMAN:
        next_action = {
            "kind": "clarify",
            "title": clarification_question or "Entscheidungskritische Information klären",
            "description": needed_evidence or required_action or status_detail,
        }
    elif run.status in {
        InvestigationRun.Status.ABORTED,
        InvestigationRun.Status.FAILED,
        InvestigationRun.Status.READY,
    }:
        evidence_hint = needed_evidence or required_action
        description_parts = [item for item in [clarification_question, evidence_hint] if item]
        if run.clarification_reason == "missing_evidence":
            next_title = "Fehlenden Nachweis ergänzen und Untersuchung neu starten"
        else:
            next_title = "Aus der Prozessanalyse einen neuen Untersuchungsstand vorbereiten"
        next_action = {
            "kind": "process",
            "title": next_title,
            "description": " · ".join(description_parts) or status_detail,
        }
    else:
        next_action = {
            "kind": "wait",
            "title": "Untersuchung abschließen lassen",
            "description": (
                "Während des laufenden Agentenlaufs ist keine fachliche Entscheidung nötig."
            ),
        }

    if not finding:
        finding = status_detail

    return {
        "status_label": status_label,
        "status_detail": status_detail,
        "status_tone": status_tone,
        "technical_status_label": technical_status_label,
        "situation": situation,
        "scope": scope,
        "question": humanize_investigation_text(
            question_scope.get("question") or run.decision_question
        ),
        "finding": finding,
        "recommendation_summary": recommendation_summary,
        "recommendation_rationale": recommendation_rationale,
        "risks": risks,
        "next_action": next_action,
        "hypotheses": hypotheses,
        "calculations": calculations,
        "options": options,
        "validation_step": {
            "step": humanize_investigation_text(
                (payload.get("validation_step") or {}).get("step")
                if isinstance(payload.get("validation_step"), Mapping)
                else ""
            ),
            "measurement": humanize_investigation_text(
                (payload.get("validation_step") or {}).get("measurement")
                if isinstance(payload.get("validation_step"), Mapping)
                else ""
            ),
        },
        "clarification_question": clarification_question,
        "needed_evidence": needed_evidence,
        "required_action": required_action,
        "policy_outcome": policy_outcome,
        "policy_reason": str(policy.reason_code or ""),
        "steps": present_investigation_steps(run),
    }
