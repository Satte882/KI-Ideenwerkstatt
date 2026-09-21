from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.forms import ProcessAnalysisForm
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

from .models import CaptureFieldSuggestion
from .structured_contract import (
    PROCESS_ANALYSIS_FIELD_SPECS,
    StructuredCandidateKind,
    structured_field_spec,
    validate_local_key,
)
from .structured_models import StructuredAdoptionBatch, StructuredAdoptionItem


class StructuredProcessError(ValueError):
    pass


class StructuredProcessReferenceError(StructuredProcessError):
    pass


class StructuredProcessValidationError(StructuredProcessError):
    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("Die Prozessanalyse ist fachlich ungültig.")
        self.errors = errors


class StageReferenceKind(StrEnum):
    EXISTING = "existing"
    LOCAL = "local"


@dataclass(frozen=True)
class StageReference:
    kind: StageReferenceKind
    stage_id: UUID | None = None
    local_key: str = ""

    @classmethod
    def existing(cls, stage_id: UUID | str) -> StageReference:
        try:
            normalized_id = UUID(str(stage_id))
        except (TypeError, ValueError) as exc:
            raise StructuredProcessReferenceError(
                "Die bestehende Phasenreferenz benötigt eine gültige UUID."
            ) from exc
        return cls(kind=StageReferenceKind.EXISTING, stage_id=normalized_id)

    @classmethod
    def local(cls, local_key: str) -> StageReference:
        return cls(kind=StageReferenceKind.LOCAL, local_key=validate_local_key(local_key))

    def snapshot(self) -> dict[str, str]:
        if self.kind == StageReferenceKind.EXISTING and self.stage_id is not None:
            return {"kind": self.kind.value, "stage_id": str(self.stage_id)}
        if self.kind == StageReferenceKind.LOCAL and self.local_key:
            return {"kind": self.kind.value, "local_key": self.local_key}
        raise StructuredProcessReferenceError("Die Phasenreferenz ist unvollständig.")


@dataclass(frozen=True)
class ProcessSuggestionGroup:
    local_key: str
    values: dict[str, str]
    source_snapshot: dict[str, Any]


@dataclass(frozen=True)
class StructuredProcessResult:
    process_analysis_id: str
    stage_id: str


PROCESS_TARGET_TO_FIELD = {
    spec.target_path: spec.model_field for spec in PROCESS_ANALYSIS_FIELD_SPECS
}
PROCESS_MODEL_FIELDS = tuple(PROCESS_TARGET_TO_FIELD.values())
PROCESS_FIELDS = frozenset(PROCESS_MODEL_FIELDS)
REQUIRED_PROCESS_FIELDS = frozenset(
    spec.model_field for spec in PROCESS_ANALYSIS_FIELD_SPECS if spec.required_for_object
)
_CONFIRMED_DECISIONS = {
    StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    StructuredAdoptionItem.Decision.CONFIRMED_EDITED,
}
_SOURCE_SCHEMA = "accelerator.process_analysis.v1"


def _excerpt_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _suggestion_source_metadata(suggestion) -> tuple[str, str]:
    analysis = getattr(suggestion, "analysis", None)
    analysis_id = getattr(suggestion, "analysis_id", None)
    if analysis_id is None and analysis is not None:
        analysis_id = getattr(analysis, "id", None)
    extraction_version = getattr(analysis, "extraction_schema_version", "")
    if not extraction_version:
        extraction_version = getattr(suggestion, "extraction_schema_version", "")
    if analysis_id is None or not str(extraction_version).strip():
        raise StructuredProcessError(
            "Der Prozessvorschlag benötigt Analyse-ID und Extraktionsversion."
        )
    return str(analysis_id), str(extraction_version).strip()


def _validate_process_values(*, local_key: str, values: dict[str, Any]) -> dict[str, str]:
    unknown_fields = set(values) - PROCESS_FIELDS
    if unknown_fields:
        raise StructuredProcessError(
            f"Die Prozessanalyse {local_key} enthält nicht freigegebene Felder: "
            f"{', '.join(sorted(unknown_fields))}."
        )

    normalized: dict[str, str] = {}
    for field_name in PROCESS_MODEL_FIELDS:
        value = values.get(field_name, "")
        if not isinstance(value, str):
            raise StructuredProcessError(
                f"Das Prozessfeld {field_name} in {local_key} muss Text enthalten."
            )
        normalized[field_name] = value.strip()

    missing_fields = [
        field_name for field_name in REQUIRED_PROCESS_FIELDS if not normalized[field_name]
    ]
    if missing_fields:
        raise StructuredProcessError(
            f"Der Prozessanalyse {local_key} fehlen Pflichtfelder: "
            f"{', '.join(sorted(missing_fields))}."
        )
    return normalized


def group_process_suggestions(
    suggestions: Iterable[CaptureFieldSuggestion],
) -> tuple[ProcessSuggestionGroup, ...]:
    grouped: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, list[str]]] = {}
    source_metadata: dict[str, set[tuple[str, str]]] = {}

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
            != CaptureFieldSuggestion.TargetObjectType.PROCESS_ANALYSIS
        ):
            raise StructuredProcessError("Die Gruppierung akzeptiert nur Prozessanalysevorschläge.")
        local_key = validate_local_key(suggestion.target_group_key)
        spec = structured_field_spec(
            target_path=suggestion.target_field,
            provider_field_type=suggestion.field_type,
        )
        if spec.candidate_kind != StructuredCandidateKind.PROCESS_ANALYSIS:
            raise StructuredProcessError("Der Vorschlag gehört nicht zu einer Prozessanalyse.")

        values = grouped.setdefault(local_key, {})
        if spec.model_field in values:
            raise StructuredProcessError(
                f"Das Prozessfeld {spec.model_field} ist in {local_key} doppelt vorhanden."
            )
        values[spec.model_field] = suggestion.suggested_value

        source = sources.setdefault(
            local_key,
            {"suggestion_ids": [], "question_ids": [], "excerpt_hashes": []},
        )
        source["suggestion_ids"].append(str(suggestion.id))
        source["question_ids"].append(suggestion.source_question)
        source["excerpt_hashes"].append(_excerpt_hash(suggestion.source_excerpt))
        source_metadata.setdefault(local_key, set()).add(_suggestion_source_metadata(suggestion))

    result: list[ProcessSuggestionGroup] = []
    for local_key, values in grouped.items():
        metadata = source_metadata[local_key]
        if len(metadata) != 1:
            raise StructuredProcessError(
                f"Die Prozessanalyse {local_key} mischt mehrere Analysequellen."
            )
        analysis_id, extraction_version = next(iter(metadata))
        source_snapshot: dict[str, Any] = {
            **sources[local_key],
            "analysis_id": analysis_id,
            "extraction_schema_version": extraction_version,
        }
        result.append(
            ProcessSuggestionGroup(
                local_key=local_key,
                values=_validate_process_values(local_key=local_key, values=values),
                source_snapshot=source_snapshot,
            )
        )
    return tuple(sorted(result, key=lambda group: group.local_key))


def process_item_defaults(
    group: ProcessSuggestionGroup,
    *,
    stage_reference: StageReference,
) -> dict[str, Any]:
    reference_snapshot = stage_reference.snapshot()
    defaults: dict[str, Any] = {
        "local_key": group.local_key,
        "candidate_kind": StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
        "target_group_key": group.local_key,
        "proposed_snapshot": {
            "fields": group.values,
            "stage_reference": reference_snapshot,
        },
        "source_snapshot": group.source_snapshot,
    }
    if stage_reference.kind == StageReferenceKind.LOCAL:
        defaults["dependency_key_snapshot"] = stage_reference.local_key
    return defaults


def _confirmed_process_values(item: StructuredAdoptionItem) -> dict[str, str]:
    if item.candidate_kind != StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS:
        raise StructuredProcessError("Der Prozessadapter akzeptiert nur Prozessanalyseitems.")
    local_key = validate_local_key(item.local_key)
    if item.target_group_key != local_key:
        raise StructuredProcessError("Lokaler Schlüssel und Prozessgruppenschlüssel weichen ab.")
    if item.status != StructuredAdoptionItem.Status.CONFIRMED:
        raise StructuredProcessError("Eine Prozessanalyse muss vor der Anlage bestätigt sein.")
    if item.decision not in _CONFIRMED_DECISIONS:
        raise StructuredProcessError(
            "Eine Prozessanalyse benötigt eine bestätigte Nutzerentscheidung."
        )
    if item.confirmed_at is None or item.confirmed_by_id_snapshot is None:
        raise StructuredProcessError(
            "Der Prozessanalyse fehlt eine nachvollziehbare Nutzerbestätigung."
        )

    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL:
        values = item.interpretation_snapshot.get("fields")
    else:
        values = item.decision_snapshot.get("edited_fields")
    if not isinstance(values, dict):
        raise StructuredProcessError("Dem bestätigten Prozessanalyseitem fehlt ein Feldobjekt.")
    return _validate_process_values(local_key=local_key, values=values)


def _stage_reference_from_item(item: StructuredAdoptionItem) -> StageReference:
    payload = item.proposed_snapshot.get("stage_reference")
    if not isinstance(payload, dict):
        raise StructuredProcessReferenceError("Dem Prozessanalyseitem fehlt die Phasenreferenz.")
    kind = payload.get("kind")
    if kind == StageReferenceKind.EXISTING:
        return StageReference.existing(payload.get("stage_id", ""))
    if kind == StageReferenceKind.LOCAL:
        return StageReference.local(payload.get("local_key", ""))
    raise StructuredProcessReferenceError("Die Art der Phasenreferenz ist ungültig.")


def _resolve_stage(
    *,
    value_stream: ValueStream,
    item: StructuredAdoptionItem,
    reference: StageReference,
) -> ValueStreamStage:
    if reference.kind == StageReferenceKind.EXISTING:
        if item.depends_on_id is not None or item.dependency_key_snapshot:
            raise StructuredProcessReferenceError(
                "Eine bestehende Phasenreferenz darf keine lokale Abhängigkeit besitzen."
            )
        try:
            return ValueStreamStage.objects.select_for_update().get(
                pk=reference.stage_id,
                value_stream=value_stream,
            )
        except ValueStreamStage.DoesNotExist as exc:
            raise StructuredProcessReferenceError(
                "Die bestehende Phase gehört nicht zum gebundenen Value Stream."
            ) from exc

    if item.depends_on_id is None:
        raise StructuredProcessReferenceError(
            "Eine lokale Phasenreferenz benötigt ein abhängiges Phasenitem."
        )
    dependency = StructuredAdoptionItem.objects.select_for_update().get(pk=item.depends_on_id)
    if dependency.batch_id != item.batch_id:
        raise StructuredProcessReferenceError("Die lokale Phase gehört zu einem anderen Batch.")
    if dependency.candidate_kind != StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
        raise StructuredProcessReferenceError("Die lokale Abhängigkeit ist kein Phasenitem.")
    if (
        dependency.local_key != reference.local_key
        or item.dependency_key_snapshot != reference.local_key
    ):
        raise StructuredProcessReferenceError(
            "Der lokale Phasenschlüssel passt nicht zur gespeicherten Abhängigkeit."
        )
    if (
        dependency.status != StructuredAdoptionItem.Status.ADOPTED
        or dependency.created_object_id is None
    ):
        raise StructuredProcessReferenceError(
            "Die lokale Phase wurde noch nicht erfolgreich angelegt."
        )
    try:
        return ValueStreamStage.objects.select_for_update().get(
            pk=dependency.created_object_id,
            value_stream=value_stream,
        )
    except ValueStreamStage.DoesNotExist as exc:
        raise StructuredProcessReferenceError(
            "Die angelegte lokale Phase gehört nicht zum gebundenen Value Stream."
        ) from exc


def _build_source_snapshot(
    *,
    item: StructuredAdoptionItem,
    reference: StageReference,
    stage: ValueStreamStage,
) -> dict[str, Any]:
    source = item.source_snapshot
    if source.get("analysis_id") != str(item.batch.analysis_id_snapshot):
        raise StructuredProcessError(
            "Die Analysequelle stimmt nicht mit dem Structured-Adoption-Batch überein."
        )
    extraction_version = str(source.get("extraction_schema_version", "")).strip()
    if not extraction_version:
        raise StructuredProcessError("Der Herkunft fehlt die Extraktionsversion.")

    return {
        "schema": _SOURCE_SCHEMA,
        "capture": {
            "session_id": str(item.batch.session_id_snapshot),
            "revision": item.batch.source_revision,
            "analysis_id": str(item.batch.analysis_id_snapshot),
            "extraction_schema_version": extraction_version,
            "interpretation_version": item.batch.interpretation_version,
        },
        "sources": source,
        "structured_adoption": {
            "batch_id": str(item.batch_id),
            "item_id": str(item.id),
            "confirmed_by_id": item.confirmed_by_id_snapshot,
            "confirmed_at": item.confirmed_at.isoformat(),
        },
        "stage_reference": {
            **reference.snapshot(),
            "resolved_stage_id": str(stage.id),
        },
    }


@transaction.atomic
def adopt_process_item(
    *,
    value_stream_id: UUID,
    item: StructuredAdoptionItem,
) -> StructuredProcessResult:
    value_stream = ValueStream.objects.select_for_update().get(pk=value_stream_id)
    locked_item = (
        StructuredAdoptionItem.objects.select_for_update().select_related("batch").get(pk=item.pk)
    )
    if (
        locked_item.batch.target_object_type
        != StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM
    ):
        raise StructuredProcessError("Der Batch ist nicht an einen Value Stream gebunden.")
    if locked_item.batch.target_object_id != value_stream.id:
        raise StructuredProcessError("Das Prozessanalyseitem gehört zu einem anderen Value Stream.")

    values = _confirmed_process_values(locked_item)
    reference = _stage_reference_from_item(locked_item)
    stage = _resolve_stage(
        value_stream=value_stream,
        item=locked_item,
        reference=reference,
    )
    form = ProcessAnalysisForm(
        data={**values, "status": ProcessAnalysis.Status.DRAFT},
        instance=ProcessAnalysis(
            stage=stage,
            status=ProcessAnalysis.Status.DRAFT,
            analyzed_by=locked_item.confirmed_by,
        ),
    )
    if not form.is_valid():
        errors = {
            field_name: [str(message) for message in messages]
            for field_name, messages in form.errors.items()
        }
        raise StructuredProcessValidationError(errors)

    process_analysis = form.save(commit=False)
    process_analysis.stage = stage
    process_analysis.status = ProcessAnalysis.Status.DRAFT
    process_analysis.analyzed_by = locked_item.confirmed_by
    process_analysis.source_snapshot = _build_source_snapshot(
        item=locked_item,
        reference=reference,
        stage=stage,
    )
    process_analysis.save()
    if process_analysis.status != ProcessAnalysis.Status.DRAFT:
        raise StructuredProcessError("Die neue Prozessanalyse wurde nicht als Entwurf gespeichert.")

    resolved_at = timezone.now()
    locked_item.status = StructuredAdoptionItem.Status.ADOPTED
    locked_item.created_object_id = process_analysis.id
    locked_item.resolved_at = resolved_at
    locked_item.error_code = ""
    locked_item.save(
        update_fields=[
            "status",
            "created_object_id",
            "resolved_at",
            "error_code",
            "updated_at",
        ]
    )
    return StructuredProcessResult(
        process_analysis_id=str(process_analysis.id),
        stage_id=str(stage.id),
    )
