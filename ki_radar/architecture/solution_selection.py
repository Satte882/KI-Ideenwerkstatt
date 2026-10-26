from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .comparison_policy import DIAGNOSIS_BASES, requires_decision_quality
from .focus import get_value_stream_focus
from .models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
)
from .permissions import can_edit_value_stream, process_validator_role
from .solution_retirement import active_solution_options

OPTION_TYPE_PRIORITY = {
    SolutionOption.OptionType.NO_TECH: 0,
    SolutionOption.OptionType.ORGANIZATIONAL: 1,
    SolutionOption.OptionType.RULE_AUTOMATION: 2,
    SolutionOption.OptionType.STANDARD_SOFTWARE: 3,
    SolutionOption.OptionType.CUSTOM_SOFTWARE: 4,
    SolutionOption.OptionType.ANALYTICS_ML: 5,
    SolutionOption.OptionType.GENERATIVE_AI: 6,
    SolutionOption.OptionType.ASSISTANT: 7,
    SolutionOption.OptionType.HYBRID: 8,
    SolutionOption.OptionType.OTHER: 9,
}

# The existing diagnosis snapshot also captures the material process basis. Names,
# timestamps and workflow status are not a change to the intervention itself.
PROCESS_BASIS_FIELDS = (
    "scope_start",
    "scope_end",
    "trigger",
    "outcome",
    "current_flow",
    "roles",
    "systems",
    "data_objects",
    "business_rules",
    "handoffs",
    "bottlenecks",
    "diagnostic_observations",
    "cause_hypotheses",
    "confirmed_causes",
    "constraints",
    "exceptions",
    "baseline_metrics",
    "target_state_principles",
)


def selection_basis_is_stale(decision):
    """One material comparison for handoff, approval and impact interpretation."""
    from ki_radar.use_cases.initiatives import _text

    process = decision.process_analysis
    if not decision.outcome_snapshot:
        # Preserve the historical selected-option-only handoff contract.
        if decision.process_version != process.version:
            return True
        selected = process.solution_options.get(pk=decision.selected_option_id)
        captured = next(
            (row for row in decision.comparison_snapshot if row.get("id") == str(selected.pk)),
            None,
        )
        if captured is None:
            return True
        current = build_comparison_snapshot([selected])[0]
        ignored = {"id", "updated_at", "outcome_effect", "effort_assessment"}
        return any(
            value != captured.get(key)
            for key, value in current.items()
            if key not in ignored and not key.endswith("_label")
        )
    diagnosis = build_diagnosis_snapshot(process)
    captured_basis = decision.diagnosis_snapshot.get("process_basis")
    if captured_basis is None:
        # Older snapshots lack the full process basis; never invent a backfill.
        if decision.process_version != process.version:
            return True
    elif any(
        _text(captured_basis.get(key, "")) != _text(diagnosis["process_basis"][key])
        for key in PROCESS_BASIS_FIELDS
    ):
        return True
    for key in ("diagnostic_observations", "cause_hypotheses", "confirmed_causes", "constraints"):
        if _text(decision.diagnosis_snapshot.get(key, "")) != _text(diagnosis[key]):
            return True
    # Reconfirming the same finding changes audit time/version, not its evidence.
    old_validation = decision.diagnosis_snapshot.get("validation") or {}
    validation = diagnosis.get("validation") or {}
    if not validation and captured_basis is not None:
        previous_validation = process.validations.filter(
            process_version=decision.process_version
        ).first()
        if previous_validation:
            validation = {
                key: getattr(previous_validation, key)
                for key in ("validator_role", "evidence_url", "note")
            }
    if any(
        _text(old_validation.get(key, "")) != _text(validation.get(key, ""))
        for key in ("validator_role", "evidence_url", "note")
    ):
        return True
    options = ordered_solution_options(process)
    current = {row["id"]: row for row in build_comparison_snapshot(options)}
    captured = {row["id"]: row for row in decision.comparison_snapshot}
    if current.keys() != captured.keys():
        return True
    ignored = {"id", "name", "updated_at"}
    return any(
        _text(value) != _text(current[pk].get(key, ""))
        for pk, row in captured.items()
        for key, value in row.items()
        if key not in ignored and not key.endswith("_label")
    )


def ordered_solution_options(process_analysis: ProcessAnalysis) -> list[SolutionOption]:
    return sorted(
        active_solution_options(process_analysis),
        key=lambda option: (
            OPTION_TYPE_PRIORITY.get(option.option_type, 99),
            option.name.casefold(),
            str(option.pk),
        ),
    )


def missing_outcome_effect_options(options, *, process_analysis):
    if not process_analysis.outcome_contract_version:
        return []
    return [option for option in options if not option.outcome_effect.strip()]


def comparison_blockers(options: list[SolutionOption], *, process_analysis=None) -> list[str]:
    blockers: list[str] = []
    if len(options) < 2:
        blockers.append(
            "Für die spätere Auswahl sind mindestens zwei unterschiedliche, aktive "
            "Lösungsoptionen erforderlich."
        )
    incomplete = [option.name for option in options if not option.comparison_complete]
    if incomplete:
        blockers.append(
            "Folgende Optionen sind noch nicht vollständig bewertet: " + ", ".join(incomplete)
        )
    if process_analysis is not None:
        blockers.extend(
            f"Wirkung auf das gemeinsame Geschäftsergebnis fehlt: {option.name}"
            for option in missing_outcome_effect_options(options, process_analysis=process_analysis)
        )
        if requires_decision_quality(process_analysis):
            blockers.extend(
                f"Aufwand, Kosten und Umstellung fehlen: {option.name}"
                for option in options
                if not option.effort_assessment.strip()
            )
    return blockers


def build_quality_snapshot(
    process, options, *, difference_reason, uncertainty_reason, diagnosis_basis, diagnosis_note
):
    if not requires_decision_quality(process):
        return {}, {}
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (difference_reason, uncertainty_reason)
    ):
        raise ValidationError(
            "Unterschiedliche Handlungshebel und die Annahme verbleibender Unsicherheiten "
            "müssen ausdrücklich begründet werden."
        )
    # Detect literal renamed copies only; no semantic/economic truth guarantee.
    signatures = {
        tuple(
            " ".join(getattr(option, key).casefold().split())
            for key in (
                "description",
                "expected_value",
                "bottleneck_coverage",
                "risks",
                "architecture_fit",
            )
        )
        for option in options
    }
    if len(signatures) < 2:
        raise ValidationError(
            "Nur umbenannte, textgleiche Optionen belegen keine unterschiedlichen "
            "Handlungshebel. Den Lösungsraum fachlich erweitern; Entwürfe bleiben speicherbar."
        )
    path = process.discovery_path_decisions.first()
    if path and path.path == "strategic":
        diagnosis = {
            "basis": "not_required",
            "label": "Strategisch: keine Ursache erforderlich",
            "note": path.strategic_potential,
            "validation_step": path.validation_step,
        }
    else:
        labels = dict(DIAGNOSIS_BASES)
        if (
            diagnosis_basis not in labels
            or not isinstance(diagnosis_note, str)
            or not diagnosis_note.strip()
        ):
            raise ValidationError(
                "Grundlage der Ursachenbestätigung benennen: fachliche Annahme oder "
                "konkrete Evidenz mit Quelle und Grenzen. Bestätigung allein ist kein Beweis."
            )
        diagnosis = {
            "basis": diagnosis_basis,
            "label": labels[diagnosis_basis],
            "note": diagnosis_note.strip(),
        }
    return {
        "version": 1,
        "difference_reason": difference_reason.strip(),
        "uncertainty_reason": uncertainty_reason.strip(),
        "assessment": "human_reasoned_not_independently_verified",
    }, diagnosis


def focus_readiness_blockers(process_analysis: ProcessAnalysis) -> list[str]:
    focus = get_value_stream_focus(process_analysis.stage.value_stream)
    if focus is None or not focus.is_selected:
        return [
            "Der Value Stream muss vollständig gescreent und für die Prozessanalyse "
            "ausgewählt sein."
        ]
    return []


def diagnosis_readiness_blockers(process_analysis: ProcessAnalysis) -> list[str]:
    if process_analysis.outcome_contract_version:
        path = process_analysis.discovery_path_decisions.first()
        if path is not None and path.path == "strategic":
            return (
                []
                if path.strategic_potential.strip() and path.validation_step.strip()
                else [
                    "strategisches Potenzial und Validierungsschritt",
                ]
            )
    blockers: list[str] = []
    if not process_analysis.diagnostic_observations.strip():
        blockers.append("Beobachtung/Problem")
    if not process_analysis.confirmed_causes.strip():
        blockers.append("bestätigte Ursache")
    return blockers


def build_comparison_snapshot(options: list[SolutionOption]) -> list[dict]:
    return [
        {
            "id": str(option.pk),
            "name": option.name,
            "option_type": option.option_type,
            "option_type_label": option.get_option_type_display(),
            "contains_ai_component": option.starts_ai_use_case,
            "evaluation_status": option.evaluation_status,
            "evidence_basis": option.evidence_basis,
            "evidence_basis_label": option.get_evidence_basis_display(),
            "description": option.description,
            "effort_assessment": option.effort_assessment,
            "expected_value": option.expected_value,
            "outcome_effect": option.outcome_effect,
            "time_to_value": option.time_to_value,
            "time_to_value_label": option.get_time_to_value_display(),
            "bottleneck_coverage": option.bottleneck_coverage,
            "feasibility": option.feasibility,
            "data_requirements": option.data_requirements,
            "application_impact": option.application_impact,
            "integration_effort": option.integration_effort,
            "integration_impact": option.integration_impact,
            "technology_constraints": option.technology_constraints,
            "risks": option.risks,
            "architecture_fit": option.architecture_fit,
            "updated_at": option.updated_at.isoformat(),
        }
        for option in options
    ]


def build_diagnosis_snapshot(process_analysis: ProcessAnalysis) -> dict:
    validation = process_analysis.validations.filter(
        process_version=process_analysis.version
    ).first()
    snapshot = {
        "diagnostic_observations": process_analysis.diagnostic_observations,
        "cause_hypotheses": process_analysis.cause_hypotheses,
        "confirmed_causes": process_analysis.confirmed_causes,
        "constraints": process_analysis.constraints,
        "validation": (
            {
                "process_version": validation.process_version,
                "validated_at": validation.validated_at.isoformat(),
                "validator_role": validation.validator_role,
                "evidence_url": validation.evidence_url,
                "note": validation.note,
            }
            if validation
            else None
        ),
    }
    if process_analysis.outcome_contract_version:
        snapshot["process_basis"] = {
            key: getattr(process_analysis, key) for key in PROCESS_BASIS_FIELDS
        }
    return snapshot


@transaction.atomic
def confirm_diagnosis_and_select_solution(
    *,
    process_analysis: ProcessAnalysis,
    selected_option: SolutionOption,
    confirmed_causes: str,
    rationale: str,
    expected_process_version: int,
    actor,
    difference_reason="",
    uncertainty_reason="",
    diagnosis_basis="",
    diagnosis_note="",
) -> SolutionSelectionDecision:
    process = (
        ProcessAnalysis.objects.select_for_update()
        .select_related("stage__value_stream")
        .get(pk=process_analysis.pk)
    )
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise ValidationError("Für diese Diagnose- und Lösungsentscheidung fehlt die Berechtigung.")
    if process.version != expected_process_version:
        raise ValidationError(
            "Die Prozessanalyse wurde seit dem Review geändert. "
            "Bitte den aktuellen Stand erneut prüfen; es wurde nichts überschrieben."
        )
    if process.outcome_contract_version:
        from ki_radar.use_cases.outcome_contract import build_outcome_snapshot

        build_outcome_snapshot(process, lock=True)

    cause = confirmed_causes.strip()
    if not cause:
        raise ValidationError("Für die Bestätigung ist ein fachlicher Kernbefund erforderlich.")

    current_cause = process.confirmed_causes.strip()
    if current_cause and current_cause != cause:
        raise ValidationError(
            "Die bestätigte Ursache wurde zwischenzeitlich geändert. "
            "Bitte den aktuellen Stand erneut prüfen; es wurde nichts überschrieben."
        )

    if not current_cause:
        process.confirmed_causes = cause
        process.version += 1
        update_fields = ["confirmed_causes", "version", "updated_at"]
        if process.status in {
            ProcessAnalysis.Status.DRAFT,
            ProcessAnalysis.Status.REVIEW_REQUIRED,
        }:
            process.status = ProcessAnalysis.Status.VALIDATED
            update_fields.append("status")
        process.full_clean()
        process.save(update_fields=update_fields)

    validation = process.validations.filter(process_version=process.version).first()
    if validation is None:
        ProcessValidation.objects.create(
            process_analysis=process,
            process_version=process.version,
            validated_by=actor,
            validator_role=process_validator_role(actor),
            note=("Kernbefund im kombinierten Diagnose- und Lösungsreview fachlich bestätigt."),
        )
        if process.status in {
            ProcessAnalysis.Status.DRAFT,
            ProcessAnalysis.Status.REVIEW_REQUIRED,
        }:
            process.status = ProcessAnalysis.Status.VALIDATED
            process.save(update_fields=["status", "updated_at"])

    return select_preferred_solution(
        process_analysis=process,
        selected_option=selected_option,
        rationale=rationale,
        actor=actor,
        difference_reason=difference_reason,
        uncertainty_reason=uncertainty_reason,
        diagnosis_basis=diagnosis_basis,
        diagnosis_note=diagnosis_note,
    )


@transaction.atomic
def select_preferred_solution(
    *,
    process_analysis: ProcessAnalysis,
    selected_option: SolutionOption,
    rationale: str,
    actor,
    expected_process_version: int | None = None,
    difference_reason="",
    uncertainty_reason="",
    diagnosis_basis="",
    diagnosis_note="",
) -> SolutionSelectionDecision:
    process_analysis = ProcessAnalysis.objects.select_for_update().get(pk=process_analysis.pk)
    if (
        expected_process_version is not None
        and process_analysis.version != expected_process_version
    ):
        raise ValidationError(
            "Die Prozessanalyse wurde seit dem Review geändert. "
            "Bitte den aktuellen Stand erneut prüfen; es wurde nichts überschrieben."
        )
    if not can_edit_value_stream(actor, process_analysis.stage.value_stream):
        raise ValidationError("Für diese Lösungsentscheidung fehlt die Berechtigung.")
    from ki_radar.use_cases.outcome_contract import build_outcome_snapshot

    outcome_snapshot = build_outcome_snapshot(process_analysis, lock=True)
    if focus_readiness_blockers(process_analysis):
        raise ValidationError(
            "Eine bevorzugte Option kann erst nach einer dokumentierten "
            "Fokusentscheidung gewählt werden."
        )
    options = ordered_solution_options(process_analysis)
    blockers = comparison_blockers(options, process_analysis=process_analysis)
    if blockers:
        raise ValidationError(" | ".join(blockers))
    selected = next((option for option in options if option.pk == selected_option.pk), None)
    if selected is None:
        raise ValidationError("Die gewählte Option gehört nicht zu den aktiven Lösungsoptionen.")
    reason = rationale.strip()
    if not reason:
        raise ValidationError("Für die Auswahl ist eine Begründung erforderlich.")

    diagnosis_blockers = diagnosis_readiness_blockers(process_analysis)
    if diagnosis_blockers:
        raise ValidationError(
            "Verbindliche Lösungspräferenz nicht möglich: Diagnose noch nicht belastbar. "
            "Es fehlen: "
            + ", ".join(diagnosis_blockers)
            + ". Lösungsoptionen können weiterhin exploriert und verglichen werden."
        )

    quality, confirmation = build_quality_snapshot(
        process_analysis,
        options,
        difference_reason=difference_reason,
        uncertainty_reason=uncertainty_reason,
        diagnosis_basis=diagnosis_basis,
        diagnosis_note=diagnosis_note,
    )
    diagnosis = build_diagnosis_snapshot(process_analysis)
    if confirmation:
        diagnosis["confirmation_basis"] = confirmation
    decision = SolutionSelectionDecision(
        quality_snapshot=quality,
        process_analysis=process_analysis,
        selected_option=selected,
        rationale=reason,
        comparison_snapshot=build_comparison_snapshot(options),
        process_version=process_analysis.version,
        diagnosis_snapshot=diagnosis,
        decided_by=actor,
        outcome_snapshot=outcome_snapshot,
    )
    decision._comparison_authorized = True
    decision._outcome_authorized = True
    decision.save()
    active_ids = [option.pk for option in options]
    process_analysis.solution_options.filter(pk__in=active_ids).exclude(pk=selected.pk).update(
        recommendation=SolutionOption.Recommendation.REJECTED
    )
    selected.recommendation = SolutionOption.Recommendation.PREFERRED
    selected.save(update_fields=["recommendation", "updated_at"])
    return decision
