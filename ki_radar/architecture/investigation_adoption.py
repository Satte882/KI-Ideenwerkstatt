from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ProcessAnalysis, SolutionOption
from .permissions import can_edit_value_stream

_PROCESS_FIELD_LABELS = {
    "diagnostic_observations": "Beobachtung / Problem",
    "cause_hypotheses": "Ursachenhypothesen",
    "baseline_metrics": "Baseline und Kennzahlen",
}
_ALLOWED_PROCESS_FIELDS = frozenset(_PROCESS_FIELD_LABELS)
_ALLOWED_SOLUTION_FIELDS = frozenset(
    {
        "name",
        "option_type",
        "description",
        "expected_value",
        "bottleneck_coverage",
        "data_requirements",
        "application_impact",
        "integration_impact",
        "risks",
        "architecture_fit",
        "evidence_basis",
    }
)


class InvestigationDraftAdoptionError(Exception):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class InvestigationDraftAdoptionResult:
    applied_fields: dict[str, str]
    created_solution_option_ids: tuple[str, ...]
    updated_solution_option_ids: tuple[str, ...]
    conflicts: tuple[dict[str, Any], ...]


def _check_permission(actor, process: ProcessAnalysis) -> None:
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise InvestigationDraftAdoptionError(
            "Für die Übernahme in diese Prozessanalyse fehlt die Berechtigung.",
            code="architecture_edit_forbidden",
        )


def _validate_contract(
    *,
    process_fields: Mapping[str, str],
    solution_proposals: Sequence[Mapping[str, Any]],
) -> None:
    unsupported_process_fields = set(process_fields) - _ALLOWED_PROCESS_FIELDS
    if unsupported_process_fields:
        raise InvestigationDraftAdoptionError(
            "Die Investigation versucht nicht freigegebene Prozessfelder zu übernehmen.",
            code="unsupported_process_fields",
        )
    for proposal in solution_proposals:
        unsupported = set(proposal) - _ALLOWED_SOLUTION_FIELDS - {"existing_option_id"}
        if unsupported:
            raise InvestigationDraftAdoptionError(
                "Die Investigation versucht nicht freigegebene Lösungsfelder zu übernehmen.",
                code="unsupported_solution_fields",
            )


def _option_fields(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {key: proposal[key] for key in _ALLOWED_SOLUTION_FIELDS if key in proposal}


def _build_plan(
    *,
    process: ProcessAnalysis,
    expected_process_version: int,
    base_process: Mapping[str, Any],
    base_options: Mapping[str, Mapping[str, Any]],
    process_fields: Mapping[str, str],
    solution_proposals: Sequence[Mapping[str, Any]],
    current_options: Sequence[SolutionOption],
) -> dict[str, Any]:
    process_changes: list[dict[str, Any]] = []
    solution_changes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    side_effects: list[dict[str, str]] = []

    if process.version != expected_process_version:
        conflicts.append(
            {
                "type": "process_version_changed",
                "label": "Prozessstand wurde zwischenzeitlich geändert",
                "expected": expected_process_version,
                "current": process.version,
                "action": "Keine Prozessfelder oder Lösungsoptionen werden still überschrieben.",
            }
        )
        return {
            "process_changes": process_changes,
            "solution_changes": solution_changes,
            "conflicts": conflicts,
            "side_effects": side_effects,
            "change_count": 0,
        }

    for field_name, proposed in process_fields.items():
        if not proposed:
            continue
        base_value = str(base_process.get(field_name) or "")
        current_value = str(getattr(process, field_name) or "")
        if current_value != base_value:
            conflicts.append(
                {
                    "type": "process_field_changed",
                    "label": _PROCESS_FIELD_LABELS[field_name],
                    "field": field_name,
                    "current": current_value,
                    "proposed": proposed,
                }
            )
            continue
        if current_value != proposed:
            process_changes.append(
                {
                    "field": field_name,
                    "label": _PROCESS_FIELD_LABELS[field_name],
                    "current": current_value,
                    "proposed": proposed,
                }
            )

    current_by_id = {str(option.pk): option for option in current_options}
    current_name_map: dict[str, SolutionOption | None] = {
        option.name.strip().casefold(): option for option in current_options
    }

    for proposal in solution_proposals:
        fields = _option_fields(proposal)
        name = str(fields.get("name") or "").strip()
        if not name:
            continue
        existing_option_id = str(proposal.get("existing_option_id") or "").strip()
        if existing_option_id:
            current = current_by_id.get(existing_option_id)
            base = base_options.get(existing_option_id)
            if current is None or base is None:
                conflicts.append(
                    {
                        "type": "solution_option_missing_or_new",
                        "label": name,
                        "option_id": existing_option_id,
                        "proposed": fields,
                    }
                )
                continue
            if (
                current.recommendation != SolutionOption.Recommendation.CANDIDATE
                or current.evaluation_status != SolutionOption.EvaluationStatus.DRAFT
            ):
                conflicts.append(
                    {
                        "type": "solution_option_decision_changed",
                        "label": current.name,
                        "option_id": existing_option_id,
                        "recommendation": current.recommendation,
                        "evaluation_status": current.evaluation_status,
                        "proposed": fields,
                    }
                )
                continue
            if current.updated_at.isoformat() != str(base.get("updated_at") or ""):
                conflicts.append(
                    {
                        "type": "solution_option_changed",
                        "label": current.name,
                        "option_id": existing_option_id,
                        "base_updated_at": base.get("updated_at"),
                        "current_updated_at": current.updated_at.isoformat(),
                        "proposed": fields,
                    }
                )
                continue
            solution_changes.append(
                {
                    "action": "update",
                    "action_label": "Vorhandenen Entwurf aktualisieren",
                    "option_id": existing_option_id,
                    **fields,
                }
            )
            continue

        key = name.casefold()
        collision = current_name_map.get(key)
        if key in current_name_map:
            conflicts.append(
                {
                    "type": "solution_option_name_collision",
                    "label": name,
                    "current_option_id": str(collision.pk) if collision is not None else "",
                    "proposed": fields,
                }
            )
            continue
        solution_changes.append(
            {
                "action": "create",
                "action_label": "Neuen Entwurf anlegen",
                **fields,
            }
        )
        current_name_map[key] = None

    if process_changes and (
        process.status == ProcessAnalysis.Status.VALIDATED
        or process.validations.filter(process_version=process.version).exists()
    ):
        side_effects.append(
            {
                "type": "process_revalidation_required",
                "label": "Prozessvalidierung",
                "description": (
                    "Die aktuelle Validierung wird durch die Prozessänderung prüfbedürftig; "
                    "die neue Prozessversion muss erneut validiert werden."
                ),
            }
        )

    return {
        "process_changes": process_changes,
        "solution_changes": solution_changes,
        "conflicts": conflicts,
        "side_effects": side_effects,
        "change_count": len(process_changes) + len(solution_changes),
    }


def preview_investigation_draft_adoption(
    *,
    actor,
    process_analysis_id,
    expected_process_version: int,
    base_process: Mapping[str, Any],
    base_options: Mapping[str, Mapping[str, Any]],
    process_fields: Mapping[str, str],
    solution_proposals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _validate_contract(process_fields=process_fields, solution_proposals=solution_proposals)
    process = ProcessAnalysis.objects.select_related("stage__value_stream").get(
        pk=process_analysis_id
    )
    _check_permission(actor, process)
    current_options = list(process.solution_options.all())
    return _build_plan(
        process=process,
        expected_process_version=expected_process_version,
        base_process=base_process,
        base_options=base_options,
        process_fields=process_fields,
        solution_proposals=solution_proposals,
        current_options=current_options,
    )


@transaction.atomic
def adopt_investigation_drafts(
    *,
    actor,
    process_analysis_id,
    expected_process_version: int,
    base_process: Mapping[str, Any],
    base_options: Mapping[str, Mapping[str, Any]],
    process_fields: Mapping[str, str],
    solution_proposals: Sequence[Mapping[str, Any]],
) -> InvestigationDraftAdoptionResult:
    _validate_contract(
        process_fields=process_fields,
        solution_proposals=solution_proposals,
    )
    process = (
        ProcessAnalysis.objects.select_for_update()
        .select_related("stage__value_stream")
        .get(pk=process_analysis_id)
    )
    _check_permission(actor, process)
    current_options = list(
        SolutionOption.objects.select_for_update().filter(process_analysis=process)
    )
    plan = _build_plan(
        process=process,
        expected_process_version=expected_process_version,
        base_process=base_process,
        base_options=base_options,
        process_fields=process_fields,
        solution_proposals=solution_proposals,
        current_options=current_options,
    )

    applied_fields: dict[str, str] = {}
    created_ids: list[str] = []
    updated_ids: list[str] = []

    for change in plan["process_changes"]:
        field_name = change["field"]
        proposed = str(change["proposed"])
        setattr(process, field_name, proposed)
        applied_fields[field_name] = proposed

    if applied_fields:
        previous_version = process.version
        had_validation = process.validations.filter(process_version=previous_version).exists()
        process.version += 1
        status_changed = False
        if had_validation or process.status == ProcessAnalysis.Status.VALIDATED:
            process.status = ProcessAnalysis.Status.REVIEW_REQUIRED
            status_changed = True
        try:
            process.full_clean()
        except ValidationError as exc:
            raise InvestigationDraftAdoptionError(
                "Die vorgeschlagenen Prozessänderungen sind fachlich nicht gültig.",
                code="process_validation_failed",
            ) from exc
        update_fields = [*applied_fields.keys(), "version", "updated_at"]
        if status_changed:
            update_fields.append("status")
        process.save(update_fields=update_fields)

    current_by_id = {str(option.pk): option for option in current_options}
    for change in plan["solution_changes"]:
        fields = {key: change[key] for key in _ALLOWED_SOLUTION_FIELDS if key in change}
        if change["action"] == "update":
            option = current_by_id[change["option_id"]]
            for field_name, value in fields.items():
                setattr(option, field_name, value)
            try:
                option.full_clean()
            except ValidationError as exc:
                raise InvestigationDraftAdoptionError(
                    "Ein vorgeschlagener Lösungsentwurf ist fachlich nicht gültig.",
                    code="solution_validation_failed",
                ) from exc
            option.save()
            updated_ids.append(str(option.pk))
            continue

        option = SolutionOption(
            process_analysis=process,
            created_by=actor,
            recommendation=SolutionOption.Recommendation.CANDIDATE,
            evaluation_status=SolutionOption.EvaluationStatus.DRAFT,
            **fields,
        )
        try:
            option.full_clean()
        except ValidationError as exc:
            raise InvestigationDraftAdoptionError(
                "Ein vorgeschlagener Lösungsentwurf ist fachlich nicht gültig.",
                code="solution_validation_failed",
            ) from exc
        option.save()
        created_ids.append(str(option.pk))

    return InvestigationDraftAdoptionResult(
        applied_fields=applied_fields,
        created_solution_option_ids=tuple(created_ids),
        updated_solution_option_ids=tuple(updated_ids),
        conflicts=tuple(plan["conflicts"]),
    )
