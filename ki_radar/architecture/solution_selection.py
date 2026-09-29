from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

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


def ordered_solution_options(process_analysis: ProcessAnalysis) -> list[SolutionOption]:
    return sorted(
        active_solution_options(process_analysis),
        key=lambda option: (
            OPTION_TYPE_PRIORITY.get(option.option_type, 99),
            option.name.casefold(),
            str(option.pk),
        ),
    )


def comparison_blockers(options: list[SolutionOption]) -> list[str]:
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
    return blockers


def focus_readiness_blockers(process_analysis: ProcessAnalysis) -> list[str]:
    focus = get_value_stream_focus(process_analysis.stage.value_stream)
    if focus is None or not focus.is_selected:
        return [
            "Der Value Stream muss vollständig gescreent und für die Prozessanalyse "
            "ausgewählt sein."
        ]
    return []


def diagnosis_readiness_blockers(process_analysis: ProcessAnalysis) -> list[str]:
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
            "expected_value": option.expected_value,
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
    return {
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
            }
            if validation
            else None
        ),
    }


@transaction.atomic
def confirm_diagnosis_and_select_solution(
    *,
    process_analysis: ProcessAnalysis,
    selected_option: SolutionOption,
    confirmed_causes: str,
    rationale: str,
    expected_process_version: int,
    actor,
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
    )


@transaction.atomic
def select_preferred_solution(
    *,
    process_analysis: ProcessAnalysis,
    selected_option: SolutionOption,
    rationale: str,
    actor,
) -> SolutionSelectionDecision:
    process_analysis = ProcessAnalysis.objects.select_for_update().get(pk=process_analysis.pk)
    if not can_edit_value_stream(actor, process_analysis.stage.value_stream):
        raise ValidationError("Für diese Lösungsentscheidung fehlt die Berechtigung.")
    if focus_readiness_blockers(process_analysis):
        raise ValidationError(
            "Eine bevorzugte Option kann erst nach einer dokumentierten "
            "Fokusentscheidung gewählt werden."
        )
    options = ordered_solution_options(process_analysis)
    blockers = comparison_blockers(options)
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

    decision = SolutionSelectionDecision.objects.create(
        process_analysis=process_analysis,
        selected_option=selected,
        rationale=reason,
        comparison_snapshot=build_comparison_snapshot(options),
        process_version=process_analysis.version,
        diagnosis_snapshot=build_diagnosis_snapshot(process_analysis),
        decided_by=actor,
    )
    active_ids = [option.pk for option in options]
    process_analysis.solution_options.filter(pk__in=active_ids).exclude(pk=selected.pk).update(
        recommendation=SolutionOption.Recommendation.REJECTED
    )
    selected.recommendation = SolutionOption.Recommendation.PREFERRED
    selected.save(update_fields=["recommendation", "updated_at"])
    return decision
