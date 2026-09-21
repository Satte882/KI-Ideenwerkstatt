from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.forms import ValueStreamStageForm
from ki_radar.architecture.models import ValueStream, ValueStreamStage

from .models import CaptureFieldSuggestion
from .structured_contract import (
    STAGE_FIELD_SPECS,
    StructuredCandidateKind,
    dependency_is_invalidating,
    structured_field_spec,
    validate_local_key,
)
from .structured_models import StructuredAdoptionBatch, StructuredAdoptionItem


class StructuredStageError(ValueError):
    pass


class StructuredStageConflict(StructuredStageError):
    pass


class StructuredStageValidationError(StructuredStageError):
    def __init__(self, errors: dict[str, dict[str, list[str]]]):
        super().__init__("Mindestens eine Value-Stream-Phase ist fachlich ungültig.")
        self.errors = errors


@dataclass(frozen=True)
class StageSuggestionGroup:
    local_key: str
    values: dict[str, Any]
    source_snapshot: dict[str, Any]


@dataclass(frozen=True)
class PreparedStage:
    item: StructuredAdoptionItem
    form: ValueStreamStageForm


@dataclass(frozen=True)
class StructuredStageResult:
    created_stage_ids: dict[str, str]


STAGE_TARGET_TO_FIELD = {spec.target_path: spec.model_field for spec in STAGE_FIELD_SPECS}
STAGE_MODEL_FIELDS = tuple(STAGE_TARGET_TO_FIELD.values())
STAGE_FIELDS = frozenset(STAGE_MODEL_FIELDS)
REQUIRED_STAGE_FIELDS = frozenset(
    spec.model_field for spec in STAGE_FIELD_SPECS if spec.required_for_object
)
_CONFIRMED_DECISIONS = {
    StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    StructuredAdoptionItem.Decision.CONFIRMED_EDITED,
}


def _excerpt_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_stage_values(*, local_key: str, values: dict[str, Any]) -> dict[str, Any]:
    unknown_fields = set(values) - STAGE_FIELDS
    if unknown_fields:
        raise StructuredStageError(
            f"Die Phase {local_key} enthält nicht freigegebene Felder: "
            f"{', '.join(sorted(unknown_fields))}."
        )

    missing_fields = REQUIRED_STAGE_FIELDS - set(values)
    if missing_fields:
        raise StructuredStageError(
            f"Der Phase {local_key} fehlen Pflichtfelder: {', '.join(sorted(missing_fields))}."
        )

    sequence = values.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise StructuredStageError(
            f"Die Phase {local_key} benötigt eine positive ganzzahlige Reihenfolge."
        )

    name = str(values.get("name", "")).strip()
    if not name:
        raise StructuredStageError(f"Die Phase {local_key} benötigt einen Namen.")

    normalized = {field_name: values.get(field_name, "") for field_name in STAGE_MODEL_FIELDS}
    normalized["sequence"] = sequence
    normalized["name"] = name
    return normalized


def group_stage_suggestions(
    suggestions: Iterable[CaptureFieldSuggestion],
) -> tuple[StageSuggestionGroup, ...]:
    grouped: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, list[Any]]] = {}

    ordered = sorted(
        suggestions,
        key=lambda suggestion: (
            suggestion.target_group_key,
            suggestion.target_field,
            str(suggestion.id),
        ),
    )
    for suggestion in ordered:
        if (
            suggestion.target_object_type
            != CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE
        ):
            raise StructuredStageError("Die Gruppierung akzeptiert nur Phasenvorschläge.")
        local_key = validate_local_key(suggestion.target_group_key)
        spec = structured_field_spec(
            target_path=suggestion.target_field,
            provider_field_type=suggestion.field_type,
        )
        if spec.candidate_kind != StructuredCandidateKind.VALUE_STREAM_STAGE:
            raise StructuredStageError("Der Vorschlag gehört nicht zu einer Value-Stream-Phase.")

        values = grouped.setdefault(local_key, {})
        if spec.model_field in values:
            raise StructuredStageError(
                f"Das Phasenfeld {spec.model_field} ist in {local_key} doppelt vorhanden."
            )
        values[spec.model_field] = suggestion.suggested_value

        source = sources.setdefault(
            local_key,
            {"suggestion_ids": [], "question_ids": [], "excerpt_hashes": []},
        )
        source["suggestion_ids"].append(str(suggestion.id))
        source["question_ids"].append(suggestion.source_question)
        source["excerpt_hashes"].append(_excerpt_hash(suggestion.source_excerpt))

    result: list[StageSuggestionGroup] = []
    sequences: dict[int, str] = {}
    for local_key, values in grouped.items():
        normalized = _validate_stage_values(local_key=local_key, values=values)
        sequence = normalized["sequence"]
        if sequence in sequences:
            raise StructuredStageConflict(
                f"Die lokale Phasenreihenfolge {sequence} wird von "
                f"{sequences[sequence]} und {local_key} verwendet."
            )
        sequences[sequence] = local_key
        result.append(
            StageSuggestionGroup(
                local_key=local_key,
                values=normalized,
                source_snapshot=sources[local_key],
            )
        )

    return tuple(sorted(result, key=lambda group: (group.values["sequence"], group.local_key)))


def stage_item_defaults(group: StageSuggestionGroup) -> dict[str, Any]:
    return {
        "local_key": group.local_key,
        "candidate_kind": StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        "target_group_key": group.local_key,
        "proposed_snapshot": {"fields": group.values},
        "source_snapshot": group.source_snapshot,
    }


def _confirmed_stage_values(item: StructuredAdoptionItem) -> dict[str, Any]:
    if item.candidate_kind != StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
        raise StructuredStageError("Der Phasenadapter akzeptiert nur Phasenitems.")
    local_key = validate_local_key(item.local_key)
    if item.target_group_key != local_key:
        raise StructuredStageError("Lokaler Schlüssel und Phasengruppenschlüssel weichen ab.")
    if item.status != StructuredAdoptionItem.Status.CONFIRMED:
        raise StructuredStageError("Eine Phase muss vor der Anlage bestätigt sein.")
    if item.decision not in _CONFIRMED_DECISIONS:
        raise StructuredStageError("Eine Phase benötigt eine bestätigte Nutzerentscheidung.")

    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL:
        values = item.interpretation_snapshot.get("fields")
    else:
        values = item.decision_snapshot.get("edited_fields")
    if not isinstance(values, dict):
        raise StructuredStageError("Dem bestätigten Phasenitem fehlt ein Feldobjekt.")
    return _validate_stage_values(local_key=local_key, values=values)


def prepare_stage_forms(
    *,
    value_stream: ValueStream,
    items: Iterable[StructuredAdoptionItem],
) -> tuple[PreparedStage, ...]:
    stage_items = tuple(items)
    if not stage_items:
        return ()

    batch_ids = {item.batch_id for item in stage_items}
    if len(batch_ids) != 1:
        raise StructuredStageError("Alle Phasenitems müssen zum selben Batch gehören.")

    prepared_values: list[tuple[StructuredAdoptionItem, dict[str, Any]]] = []
    local_keys: set[str] = set()
    sequences: dict[int, str] = {}
    for item in stage_items:
        if item.batch.target_object_type != StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM:
            raise StructuredStageError("Der Batch ist nicht an einen Value Stream gebunden.")
        if item.batch.target_object_id != value_stream.id:
            raise StructuredStageError("Das Phasenitem gehört zu einem anderen Value Stream.")
        if item.local_key in local_keys:
            raise StructuredStageError("Ein lokaler Phasenschlüssel ist mehrfach vorhanden.")
        local_keys.add(item.local_key)

        values = _confirmed_stage_values(item)
        sequence = values["sequence"]
        if sequence in sequences:
            raise StructuredStageConflict(
                f"Die lokale Phasenreihenfolge {sequence} wird mehrfach verwendet."
            )
        sequences[sequence] = item.local_key
        prepared_values.append((item, values))

    existing_sequences = set(
        value_stream.stages.filter(sequence__in=sequences).values_list("sequence", flat=True)
    )
    if existing_sequences:
        collisions = ", ".join(str(value) for value in sorted(existing_sequences))
        raise StructuredStageConflict(
            f"Die Phasenreihenfolge kollidiert mit bestehenden Sequenzen: {collisions}."
        )

    prepared: list[PreparedStage] = []
    errors: dict[str, dict[str, list[str]]] = {}
    for item, values in sorted(
        prepared_values,
        key=lambda entry: (entry[1]["sequence"], entry[0].local_key),
    ):
        form = ValueStreamStageForm(
            data=values,
            instance=ValueStreamStage(value_stream=value_stream),
        )
        if not form.is_valid():
            errors[item.local_key] = {
                field_name: [str(message) for message in messages]
                for field_name, messages in form.errors.items()
            }
        prepared.append(PreparedStage(item=item, form=form))

    if errors:
        raise StructuredStageValidationError(errors)
    return tuple(prepared)


@transaction.atomic
def adopt_stage_items(
    *,
    value_stream_id,
    items: Iterable[StructuredAdoptionItem],
) -> StructuredStageResult:
    value_stream = ValueStream.objects.select_for_update().get(pk=value_stream_id)
    list(
        ValueStreamStage.objects.select_for_update()
        .filter(value_stream=value_stream)
        .order_by("id")
    )
    prepared = prepare_stage_forms(value_stream=value_stream, items=items)

    created_stage_ids: dict[str, str] = {}
    resolved_at = timezone.now()
    for entry in prepared:
        stage = entry.form.save()
        entry.item.status = StructuredAdoptionItem.Status.ADOPTED
        entry.item.created_object_id = stage.id
        entry.item.resolved_at = resolved_at
        entry.item.error_code = ""
        entry.item.save(
            update_fields=[
                "status",
                "created_object_id",
                "resolved_at",
                "error_code",
                "updated_at",
            ]
        )
        created_stage_ids[entry.item.local_key] = str(stage.id)

    return StructuredStageResult(created_stage_ids=created_stage_ids)


@transaction.atomic
def cascade_invalidate_stage_dependents(
    *,
    stage_item: StructuredAdoptionItem,
    stage_state: str,
) -> int:
    if stage_item.candidate_kind != StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
        raise StructuredStageError("Cascade-Invalidierung benötigt ein Phasenitem.")
    if not dependency_is_invalidating(stage_state):
        return 0

    dependents = stage_item.dependents.filter(
        batch_id=stage_item.batch_id,
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
    ).exclude(status=StructuredAdoptionItem.Status.ADOPTED)
    resolved_at = timezone.now()
    return dependents.update(
        status=StructuredAdoptionItem.Status.DEPENDENCY_INVALID,
        decision=StructuredAdoptionItem.Decision.PENDING,
        confirmed_by=None,
        confirmed_by_id_snapshot=None,
        confirmed_at=None,
        resolved_at=resolved_at,
        created_object_id=None,
        error_code=f"stage_dependency_{stage_state}"[:50],
        updated_at=resolved_at,
    )
