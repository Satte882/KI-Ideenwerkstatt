from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.forms import ProcessAnalysisForm, ValueStreamStageForm
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_edit_use_case

from .models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from .structured_adoption_orchestrator import (
    build_idempotency_key,
    build_selected_graph_hash,
    commit_structured_batch,
)
from .structured_contract import (
    PROCESS_ANALYSIS_FIELD_SPECS,
    STAGE_FIELD_SPECS,
    STRUCTURED_FIELD_SPECS,
    StructuredCandidateKind,
    StructuredFieldSpec,
    validate_local_key,
)
from .structured_metric_adoption import build_metric_field_snapshot
from .structured_models import (
    StructuredAdoptionAudit,
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from .structured_normalization import NormalizationStatus, normalize_structured_value
from .structured_stage_adoption import cascade_invalidate_stage_dependents


class StructuredReviewError(ValueError):
    pass


class StructuredReviewAction(StrEnum):
    CONFIRM = "confirm"
    EDIT = "edit"
    REJECT = "reject"


@dataclass(frozen=True)
class StructuredReviewDecision:
    batch_id: UUID
    item_id: UUID
    status: str
    decision: str


_TERMINAL_DECISIONS = {
    StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    StructuredAdoptionItem.Decision.CONFIRMED_EDITED,
    StructuredAdoptionItem.Decision.REJECTED,
}
_INVALID_DEPENDENCY_STATES = {
    StructuredAdoptionItem.Status.REJECTED,
    StructuredAdoptionItem.Status.AMBIGUOUS,
    StructuredAdoptionItem.Status.INVALID,
    StructuredAdoptionItem.Status.DEPENDENCY_INVALID,
    StructuredAdoptionItem.Status.CONFLICT,
    StructuredAdoptionItem.Status.STALE,
    StructuredAdoptionItem.Status.FAILED,
}
_FIELD_LABELS = {
    "metric_name": "Metrikname",
    "metric_type": "Metriktyp",
    "metric_direction": "Optimierungsrichtung",
    "metric_unit": "Einheit",
    "metric_baseline": "Baseline",
    "metric_target": "Zielwert",
    "metric_measurement_method": "Messmethode",
    "sequence": "Reihenfolge",
    "name": "Name",
    "description": "Aktivität und Ergebnis",
    "actors": "Beteiligte Rollen",
    "systems": "Systeme",
    "documents": "Daten und Dokumente",
    "pain_points": "Probleme und Engpässe",
    "baseline_metrics": "Kennzahlen und Baseline",
    "scope_start": "Start",
    "scope_end": "Ende",
    "trigger": "Auslöser",
    "outcome": "Ergebnis",
    "current_flow": "Heutiger Ablauf",
    "roles": "Rollen",
    "data_objects": "Datenobjekte",
    "business_rules": "Geschäftsregeln",
    "handoffs": "Übergaben",
    "bottlenecks": "Engpässe",
    "exceptions": "Ausnahmen",
    "target_state_principles": "Prinzipien des Zielzustands",
}
_FIELD_TYPE_LABELS = {
    "text": "Text",
    "integer": "Ganzzahl",
    "decimal": "Dezimalzahl",
    "enum": "Auswahlliste",
}
_STATUS_LABELS = {
    NormalizationStatus.VALID: "Gültig",
    NormalizationStatus.AMBIGUOUS: "Unklar",
    NormalizationStatus.INVALID: "Ungültig",
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _target_for_session(session: CaptureSession):
    if session.capture_type == CaptureSession.CaptureType.USE_CASE:
        return session.target_use_case
    if session.capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        return session.target_value_stream
    return None


def _can_edit(*, actor, session: CaptureSession, target) -> bool:
    if session.capture_type == CaptureSession.CaptureType.USE_CASE:
        return can_edit_use_case(actor, target)
    if session.capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        return can_edit_value_stream(actor, target)
    return False


def _assert_analysis_reviewable(*, analysis: CaptureAnalysis, actor):
    session = analysis.session
    if session.owner_id != actor.id:
        raise PermissionDenied("Die Analyse gehört einem anderen Nutzer.")
    if analysis.status != CaptureAnalysis.Status.SUCCESS:
        raise StructuredReviewError("Nur erfolgreiche Analysen können geprüft werden.")
    if analysis.source_revision != session.revision:
        raise StructuredReviewError("Die Analyse gehört nicht mehr zum aktuellen Erfassungsstand.")
    target = _target_for_session(session)
    if target is None:
        raise StructuredReviewError("Die Erfassung ist nicht an ein Zielobjekt gebunden.")
    if not _can_edit(actor=actor, session=session, target=target):
        raise PermissionDenied("Das gebundene Zielobjekt darf nicht bearbeitet werden.")
    return target


def _source_snapshot(
    *,
    analysis: CaptureAnalysis,
    suggestions: list[CaptureFieldSuggestion],
) -> dict[str, Any]:
    return {
        "analysis_id": str(analysis.id),
        "extraction_schema_version": analysis.extraction_schema_version,
        "suggestion_ids": [str(suggestion.id) for suggestion in suggestions],
        "question_ids": [suggestion.source_question for suggestion in suggestions],
        "excerpt_hashes": [_sha256(suggestion.source_excerpt) for suggestion in suggestions],
    }


def _normalize_suggestion(
    suggestion: CaptureFieldSuggestion,
    spec: StructuredFieldSpec,
) -> dict[str, Any]:
    try:
        normalized = normalize_structured_value(
            target_path=suggestion.target_field,
            provider_field_type=suggestion.field_type,
            value=suggestion.suggested_value,
        )
    except ValueError:
        return {
            "status": NormalizationStatus.INVALID,
            "value": None,
            "unit": "",
            "error_code": "contract_mismatch",
            "field_type": spec.field_type.value,
        }
    return {
        "status": normalized.status,
        "value": _json_value(normalized.value),
        "unit": normalized.unit,
        "error_code": normalized.error_code,
        "field_type": spec.field_type.value,
    }


def _status_from_meta(field_meta: dict[str, dict[str, Any]]) -> str:
    statuses = {meta["status"] for meta in field_meta.values()}
    if NormalizationStatus.INVALID in statuses:
        return StructuredAdoptionItem.Status.INVALID
    if NormalizationStatus.AMBIGUOUS in statuses:
        return StructuredAdoptionItem.Status.AMBIGUOUS
    return StructuredAdoptionItem.Status.OPEN


def _metric_items(
    *,
    batch: StructuredAdoptionBatch,
    analysis: CaptureAnalysis,
    target: UseCase,
    suggestions: list[CaptureFieldSuggestion],
) -> list[StructuredAdoptionItem]:
    current = build_metric_field_snapshot(target)
    items: list[StructuredAdoptionItem] = []
    for suggestion in suggestions:
        spec = STRUCTURED_FIELD_SPECS[suggestion.target_field]
        meta = _normalize_suggestion(suggestion, spec)
        local_key = f"metric-{spec.model_field.removeprefix('metric_').replace('_', '-')}"
        items.append(
            StructuredAdoptionItem(
                batch=batch,
                local_key=local_key,
                candidate_kind=StructuredAdoptionItem.CandidateKind.METRIC_SET,
                target_path=suggestion.target_field,
                proposed_snapshot={"value": suggestion.suggested_value},
                interpretation_snapshot=meta,
                field_snapshot=current[suggestion.target_field],
                source_snapshot=_source_snapshot(
                    analysis=analysis,
                    suggestions=[suggestion],
                ),
                status=(
                    StructuredAdoptionItem.Status.OPEN
                    if meta["status"] == NormalizationStatus.VALID
                    else (
                        StructuredAdoptionItem.Status.AMBIGUOUS
                        if meta["status"] == NormalizationStatus.AMBIGUOUS
                        else StructuredAdoptionItem.Status.INVALID
                    )
                ),
            )
        )
    return items


def _grouped_items(
    *,
    batch: StructuredAdoptionBatch,
    analysis: CaptureAnalysis,
    suggestions: list[CaptureFieldSuggestion],
    candidate_kind: StructuredCandidateKind,
) -> list[StructuredAdoptionItem]:
    grouped: dict[str, list[CaptureFieldSuggestion]] = {}
    default_key = (
        "process-analysis"
        if candidate_kind == StructuredCandidateKind.PROCESS_ANALYSIS
        else "ungrouped-stage"
    )
    for suggestion in suggestions:
        key = suggestion.target_group_key or default_key
        grouped.setdefault(key, []).append(suggestion)

    expected_specs = (
        STAGE_FIELD_SPECS
        if candidate_kind == StructuredCandidateKind.VALUE_STREAM_STAGE
        else PROCESS_ANALYSIS_FIELD_SPECS
    )
    items: list[StructuredAdoptionItem] = []
    for local_key, group in sorted(grouped.items()):
        try:
            normalized_key = validate_local_key(local_key)
        except ValueError:
            normalized_key = default_key
        proposed_fields: dict[str, Any] = {}
        interpreted_fields: dict[str, Any] = {}
        field_meta: dict[str, dict[str, Any]] = {}
        for suggestion in group:
            spec = STRUCTURED_FIELD_SPECS[suggestion.target_field]
            proposed_fields[spec.model_field] = suggestion.suggested_value
            meta = _normalize_suggestion(suggestion, spec)
            field_meta[spec.model_field] = meta
            if meta["status"] == NormalizationStatus.VALID:
                interpreted_fields[spec.model_field] = meta["value"]

        present = set(field_meta)
        for spec in expected_specs:
            if spec.required_for_object and spec.model_field not in present:
                field_meta[spec.model_field] = {
                    "status": NormalizationStatus.INVALID,
                    "value": None,
                    "unit": "",
                    "error_code": "required_field_missing",
                    "field_type": spec.field_type.value,
                }

        item = StructuredAdoptionItem(
            batch=batch,
            local_key=normalized_key,
            candidate_kind=candidate_kind.value,
            target_group_key=normalized_key,
            proposed_snapshot={"fields": proposed_fields},
            interpretation_snapshot={
                "fields": interpreted_fields,
                "field_meta": field_meta,
            },
            source_snapshot=_source_snapshot(analysis=analysis, suggestions=group),
            status=_status_from_meta(field_meta),
        )
        items.append(item)
    return items


def _supported_suggestions(analysis: CaptureAnalysis) -> list[CaptureFieldSuggestion]:
    supported: list[CaptureFieldSuggestion] = []
    for suggestion in analysis.suggestions.all():
        spec = STRUCTURED_FIELD_SPECS.get(suggestion.target_field)
        if spec is None:
            continue
        if (
            analysis.capture_type == CaptureSession.CaptureType.USE_CASE
            and spec.candidate_kind != StructuredCandidateKind.METRIC_SET
        ):
            continue
        if (
            analysis.capture_type == CaptureSession.CaptureType.VALUE_STREAM
            and spec.candidate_kind == StructuredCandidateKind.METRIC_SET
        ):
            continue
        supported.append(suggestion)
    return supported


def _seal_batch(batch: StructuredAdoptionBatch) -> None:
    items = tuple(batch.items.order_by("local_key", "id"))
    selected_graph_hash = build_selected_graph_hash(items)
    batch.selected_graph_hash = selected_graph_hash
    batch.idempotency_key = build_idempotency_key(
        session_id=batch.session_id_snapshot,
        analysis_id=batch.analysis_id_snapshot,
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        selected_graph_hash=selected_graph_hash,
        interpretation_version=batch.interpretation_version,
    )
    if batch.status in {
        StructuredAdoptionBatch.Status.FAILED,
        StructuredAdoptionBatch.Status.CONFLICT,
        StructuredAdoptionBatch.Status.STALE,
    }:
        batch.status = StructuredAdoptionBatch.Status.OPEN
        batch.processing_by = None
        batch.processing_started_at = None
        batch.completed_at = None
        batch.error_code = ""
        batch.result_snapshot = {}
    batch.save(
        update_fields=[
            "selected_graph_hash",
            "idempotency_key",
            "status",
            "processing_by",
            "processing_started_at",
            "completed_at",
            "error_code",
            "result_snapshot",
            "updated_at",
        ]
    )


def _record_audit(
    *,
    batch: StructuredAdoptionBatch,
    actor,
    event: str,
    outcome: str,
    item: StructuredAdoptionItem | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    StructuredAdoptionAudit.objects.create(
        batch=batch,
        item=item,
        actor=actor,
        batch_id_snapshot=batch.id,
        item_id_snapshot=item.id if item else None,
        session_id_snapshot=batch.session_id_snapshot,
        analysis_id_snapshot=batch.analysis_id_snapshot,
        actor_id_snapshot=actor.id,
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        idempotency_key=batch.idempotency_key,
        attempt_count=batch.attempt_count,
        event=event,
        outcome=outcome,
        step="review",
        item_kind=item.candidate_kind if item else "",
        item_local_key=item.local_key if item else "",
        target_field=item.target_path if item else "",
        details=details or {},
    )


@transaction.atomic
def get_or_create_review_batch(*, analysis_id: UUID, actor) -> StructuredAdoptionBatch:
    analysis = (
        CaptureAnalysis.objects.select_for_update().select_related("session").get(pk=analysis_id)
    )
    target = _assert_analysis_reviewable(analysis=analysis, actor=actor)
    existing = (
        StructuredAdoptionBatch.objects.filter(
            analysis_id_snapshot=analysis.id,
            session_id_snapshot=analysis.session_id,
            created_by=actor,
            target_object_type=analysis.capture_type,
            target_object_id=target.id,
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing

    suggestions = _supported_suggestions(analysis)
    if not suggestions:
        raise StructuredReviewError("Die Analyse enthält keine strukturierten Block-6-Vorschläge.")

    placeholder = _sha256(f"review:{analysis.id}:{target.id}:{actor.id}")
    batch = StructuredAdoptionBatch.objects.create(
        session=analysis.session,
        analysis=analysis,
        created_by=actor,
        session_id_snapshot=analysis.session_id,
        analysis_id_snapshot=analysis.id,
        actor_id_snapshot=actor.id,
        target_object_type=analysis.capture_type,
        target_object_id=target.id,
        source_revision=analysis.source_revision,
        interpretation_version="1",
        idempotency_key=placeholder,
        selected_graph_hash="0" * 64,
        decision_snapshot={"review_version": "1"},
    )

    by_kind: dict[StructuredCandidateKind, list[CaptureFieldSuggestion]] = {
        kind: [] for kind in StructuredCandidateKind
    }
    for suggestion in suggestions:
        by_kind[STRUCTURED_FIELD_SPECS[suggestion.target_field].candidate_kind].append(suggestion)

    items: list[StructuredAdoptionItem] = []
    if analysis.capture_type == CaptureSession.CaptureType.USE_CASE:
        items.extend(
            _metric_items(
                batch=batch,
                analysis=analysis,
                target=target,
                suggestions=by_kind[StructuredCandidateKind.METRIC_SET],
            )
        )
    else:
        items.extend(
            _grouped_items(
                batch=batch,
                analysis=analysis,
                suggestions=by_kind[StructuredCandidateKind.VALUE_STREAM_STAGE],
                candidate_kind=StructuredCandidateKind.VALUE_STREAM_STAGE,
            )
        )
        items.extend(
            _grouped_items(
                batch=batch,
                analysis=analysis,
                suggestions=by_kind[StructuredCandidateKind.PROCESS_ANALYSIS],
                candidate_kind=StructuredCandidateKind.PROCESS_ANALYSIS,
            )
        )
    StructuredAdoptionItem.objects.bulk_create(items)
    _seal_batch(batch)
    _record_audit(
        batch=batch,
        actor=actor,
        event=StructuredAdoptionAudit.Event.CREATED,
        outcome="review_created",
        details={"item_count": len(items)},
    )
    return batch


def _assert_batch_editable(*, batch: StructuredAdoptionBatch, actor):
    if batch.created_by_id != actor.id:
        raise PermissionDenied("Der Review-Batch gehört einem anderen Nutzer.")
    target = _target_for_session(batch.session) if batch.session_id else None
    if target is None:
        if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.USE_CASE:
            target = UseCase.objects.get(pk=batch.target_object_id)
        else:
            target = ValueStream.objects.get(pk=batch.target_object_id)
    if not _can_edit(actor=actor, session=batch.session, target=target):
        raise PermissionDenied("Das gebundene Zielobjekt darf nicht bearbeitet werden.")
    if batch.status in {
        StructuredAdoptionBatch.Status.PROCESSING,
        StructuredAdoptionBatch.Status.COMMITTED,
        StructuredAdoptionBatch.Status.REJECTED,
    }:
        raise StructuredReviewError("Der Batch kann nicht mehr bearbeitet werden.")
    return target


def _normalize_edited_metric(item: StructuredAdoptionItem, edited_value: Any) -> Any:
    normalized = normalize_structured_value(
        target_path=item.target_path,
        provider_field_type=STRUCTURED_FIELD_SPECS[item.target_path].field_type.value,
        value=edited_value,
    )
    if normalized.status != NormalizationStatus.VALID:
        raise StructuredReviewError("Der bearbeitete Wert ist nicht eindeutig gültig.")
    return _json_value(normalized.value)


def _normalize_edited_fields(
    *,
    item: StructuredAdoptionItem,
    edited_fields: dict[str, Any],
) -> dict[str, Any]:
    specs = (
        STAGE_FIELD_SPECS
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
        else PROCESS_ANALYSIS_FIELD_SPECS
    )
    normalized_fields: dict[str, Any] = {}
    errors: list[str] = []
    for spec in specs:
        value = edited_fields.get(spec.model_field, "")
        if not value and not spec.required_for_object:
            normalized_fields[spec.model_field] = ""
            continue
        normalized = normalize_structured_value(
            target_path=spec.target_path,
            provider_field_type=spec.field_type.value,
            value=value,
        )
        if normalized.status != NormalizationStatus.VALID:
            errors.append(_FIELD_LABELS.get(spec.model_field, spec.model_field))
            continue
        normalized_fields[spec.model_field] = _json_value(normalized.value)
    if errors:
        raise StructuredReviewError(
            "Diese bearbeiteten Felder sind nicht eindeutig gültig: " + ", ".join(errors)
        )
    return normalized_fields


def _validate_stage_fields(*, target: ValueStream, fields: dict[str, Any]) -> None:
    form = ValueStreamStageForm(
        data=fields,
        instance=ValueStreamStage(value_stream=target),
    )
    if not form.is_valid():
        messages = [str(message) for field in form.errors.values() for message in field]
        raise StructuredReviewError(" ".join(messages))


def _set_process_reference(
    *,
    item: StructuredAdoptionItem,
    target: ValueStream,
    reference_value: str,
) -> None:
    try:
        reference_kind, reference_id = reference_value.split(":", 1)
    except ValueError as exc:
        raise StructuredReviewError(
            "Für die Prozessanalyse muss eine Phase gewählt werden."
        ) from exc
    proposed = dict(item.proposed_snapshot)
    if reference_kind == "existing":
        try:
            stage_id = UUID(reference_id)
        except ValueError as exc:
            raise StructuredReviewError("Die bestehende Phasenreferenz ist ungültig.") from exc
        stage = ValueStreamStage.objects.filter(pk=stage_id, value_stream=target).first()
        if stage is None:
            raise StructuredReviewError("Die gewählte bestehende Phase ist nicht zulässig.")
        proposed["stage_reference"] = {"kind": "existing", "stage_id": str(stage.id)}
        item.depends_on = None
        item.dependency_key_snapshot = ""
    elif reference_kind == "local":
        local_key = validate_local_key(reference_id)
        dependency = StructuredAdoptionItem.objects.filter(
            batch=item.batch,
            local_key=local_key,
            candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        ).first()
        if dependency is None or dependency.status in _INVALID_DEPENDENCY_STATES:
            raise StructuredReviewError("Die gewählte neue Phase ist nicht ausführbar.")
        proposed["stage_reference"] = {"kind": "local", "local_key": local_key}
        item.depends_on = dependency
        item.dependency_key_snapshot = local_key
    else:
        raise StructuredReviewError("Die Art der Phasenreferenz ist ungültig.")
    item.proposed_snapshot = proposed


def _validate_process_fields(*, fields: dict[str, Any]) -> None:
    form = ProcessAnalysisForm(
        data={**fields, "status": ProcessAnalysis.Status.DRAFT},
        instance=ProcessAnalysis(status=ProcessAnalysis.Status.DRAFT),
    )
    if not form.is_valid():
        messages = [str(message) for field in form.errors.values() for message in field]
        raise StructuredReviewError(" ".join(messages))


@transaction.atomic
def decide_review_item(
    *,
    batch_id: UUID,
    item_id: UUID,
    actor,
    action: StructuredReviewAction,
    edited_value: Any = None,
    edited_fields: dict[str, Any] | None = None,
    stage_reference: str = "",
) -> StructuredReviewDecision:
    batch = StructuredAdoptionBatch.objects.select_for_update().get(pk=batch_id)
    target = _assert_batch_editable(batch=batch, actor=actor)
    item = StructuredAdoptionItem.objects.select_for_update().get(pk=item_id, batch=batch)

    if action == StructuredReviewAction.REJECT:
        item.status = StructuredAdoptionItem.Status.REJECTED
        item.decision = StructuredAdoptionItem.Decision.REJECTED
        item.decision_snapshot = {}
        item.confirmed_by = actor
        item.confirmed_by_id_snapshot = actor.id
        item.confirmed_at = timezone.now()
        item.resolved_at = timezone.now()
        item.error_code = ""
        item.save()
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
            cascade_invalidate_stage_dependents(stage_item=item, stage_state="rejected")
        event = StructuredAdoptionAudit.Event.REJECTED
        outcome = "rejected"
    else:
        direct = action == StructuredReviewAction.CONFIRM
        if direct:
            interpretation_status = item.interpretation_snapshot.get("status")
            if item.candidate_kind != StructuredAdoptionItem.CandidateKind.METRIC_SET:
                field_meta = item.interpretation_snapshot.get("field_meta", {})
                interpretation_status = (
                    NormalizationStatus.VALID
                    if field_meta
                    and all(
                        meta.get("status") == NormalizationStatus.VALID
                        for meta in field_meta.values()
                    )
                    else NormalizationStatus.INVALID
                )
            if interpretation_status != NormalizationStatus.VALID:
                raise StructuredReviewError(
                    "Unklare oder ungültige Vorschläge müssen bearbeitet oder verworfen werden."
                )
            suggestion_ids = item.source_snapshot.get("suggestion_ids", [])
            if CaptureFieldSuggestion.objects.filter(
                id__in=suggestion_ids,
                uncertainty__in=[
                    CaptureFieldSuggestion.Uncertainty.MEDIUM,
                    CaptureFieldSuggestion.Uncertainty.HIGH,
                ],
            ).exists():
                raise StructuredReviewError(
                    "Vorschläge mit mittlerer oder hoher Unsicherheit müssen bearbeitet werden."
                )

        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.METRIC_SET:
            if direct:
                value = item.interpretation_snapshot.get("value")
            else:
                value = _normalize_edited_metric(item, edited_value)
            item.decision_snapshot = {} if direct else {"edited_value": value}
        else:
            if direct:
                fields = item.interpretation_snapshot.get("fields", {})
            else:
                fields = _normalize_edited_fields(
                    item=item,
                    edited_fields=edited_fields or {},
                )
            if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
                _validate_stage_fields(target=target, fields=fields)
            else:
                if not isinstance(target, ValueStream):
                    raise StructuredReviewError("Die Prozessanalyse benötigt einen Value Stream.")
                _set_process_reference(
                    item=item,
                    target=target,
                    reference_value=stage_reference,
                )
                _validate_process_fields(fields=fields)
            item.decision_snapshot = {} if direct else {"edited_fields": fields}

        item.status = StructuredAdoptionItem.Status.CONFIRMED
        item.decision = (
            StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL
            if direct
            else StructuredAdoptionItem.Decision.CONFIRMED_EDITED
        )
        item.confirmed_by = actor
        item.confirmed_by_id_snapshot = actor.id
        item.confirmed_at = timezone.now()
        item.resolved_at = None
        item.error_code = ""
        item.save()
        event = StructuredAdoptionAudit.Event.CONFIRMED
        outcome = item.decision

    _seal_batch(batch)
    item.refresh_from_db()
    _record_audit(
        batch=batch,
        actor=actor,
        event=event,
        outcome=outcome,
        item=item,
    )
    return StructuredReviewDecision(
        batch_id=batch.id,
        item_id=item.id,
        status=item.status,
        decision=item.decision,
    )


def review_batch_ready(batch: StructuredAdoptionBatch) -> bool:
    items = tuple(batch.items.select_related("depends_on").all())
    if not items or batch.status not in {
        StructuredAdoptionBatch.Status.OPEN,
        StructuredAdoptionBatch.Status.FAILED,
    }:
        return False
    selected = 0
    for item in items:
        if item.decision not in _TERMINAL_DECISIONS:
            return False
        if item.decision == StructuredAdoptionItem.Decision.REJECTED:
            if item.status != StructuredAdoptionItem.Status.REJECTED:
                return False
            continue
        selected += 1
        if item.status != StructuredAdoptionItem.Status.CONFIRMED:
            return False
        if item.depends_on_id is not None and (
            item.depends_on.decision == StructuredAdoptionItem.Decision.REJECTED
            or item.depends_on.status != StructuredAdoptionItem.Status.CONFIRMED
        ):
            return False
    return selected > 0


def commit_review_batch(*, batch_id: UUID, actor):
    batch = StructuredAdoptionBatch.objects.select_related(
        "session__target_use_case",
        "session__target_value_stream",
    ).get(pk=batch_id)
    _assert_batch_editable(batch=batch, actor=actor)
    if not review_batch_ready(batch):
        raise StructuredReviewError(
            "Vor dem Commit benötigt jedes Item eine gültige Einzelentscheidung."
        )
    return commit_structured_batch(
        batch_id=batch.id,
        actor=actor,
        idempotency_key=batch.idempotency_key,
    )


def _display(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, dict):
        return " · ".join(f"{key}: {_display(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " · ".join(_display(item) for item in value)
    return str(value)


def _field_rows(item: StructuredAdoptionItem) -> list[dict[str, str]]:
    if item.candidate_kind == StructuredAdoptionItem.CandidateKind.METRIC_SET:
        spec = STRUCTURED_FIELD_SPECS[item.target_path]
        meta = item.interpretation_snapshot
        return [
            {
                "name": spec.model_field,
                "label": _FIELD_LABELS.get(spec.model_field, spec.model_field),
                "proposal": _display(item.proposed_snapshot.get("value")),
                "interpretation": _display(meta.get("value")),
                "field_type": _FIELD_TYPE_LABELS.get(
                    meta.get("field_type"), meta.get("field_type")
                ),
                "unit": meta.get("unit") or "-",
                "validation": _STATUS_LABELS.get(meta.get("status"), str(meta.get("status"))),
                "error_code": meta.get("error_code", ""),
                "edit_value": _display(meta.get("value")) if meta.get("value") is not None else "",
            }
        ]

    proposed = item.proposed_snapshot.get("fields", {})
    interpreted = item.interpretation_snapshot.get("fields", {})
    meta = item.interpretation_snapshot.get("field_meta", {})
    specs = (
        STAGE_FIELD_SPECS
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
        else PROCESS_ANALYSIS_FIELD_SPECS
    )
    return [
        {
            "name": spec.model_field,
            "label": _FIELD_LABELS.get(spec.model_field, spec.model_field),
            "proposal": _display(proposed.get(spec.model_field)),
            "interpretation": _display(interpreted.get(spec.model_field)),
            "field_type": _FIELD_TYPE_LABELS.get(spec.field_type.value, spec.field_type.value),
            "unit": meta.get(spec.model_field, {}).get("unit") or "-",
            "validation": _STATUS_LABELS.get(
                meta.get(spec.model_field, {}).get("status"),
                "Fehlt" if spec.required_for_object else "Optional",
            ),
            "error_code": meta.get(spec.model_field, {}).get("error_code", ""),
            "edit_value": _display(interpreted.get(spec.model_field))
            if interpreted.get(spec.model_field) is not None
            else "",
        }
        for spec in specs
    ]


def _effective_source(item: StructuredAdoptionItem) -> str:
    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL:
        return "Interpretierter Vorschlag"
    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_EDITED:
        return "Bestätigte Bearbeitung"
    if item.decision == StructuredAdoptionItem.Decision.REJECTED:
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.METRIC_SET:
            return "Aktueller Datenbankwert"
        return "Nicht Teil des Commit-Batches"
    return "Noch nicht entschieden"


def build_review_context(batch: StructuredAdoptionBatch) -> dict[str, Any]:
    items = list(batch.items.select_related("depends_on").order_by("local_key", "id"))
    suggestion_ids = {
        UUID(value) for item in items for value in item.source_snapshot.get("suggestion_ids", [])
    }
    suggestions = {
        suggestion.id: suggestion
        for suggestion in CaptureFieldSuggestion.objects.filter(id__in=suggestion_ids)
    }

    target = _target_for_session(batch.session) if batch.session_id else None
    local_stages = [
        item
        for item in items
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
    ]
    local_stages.sort(
        key=lambda item: (
            item.interpretation_snapshot.get("fields", {}).get("sequence", 9999),
            item.local_key,
        )
    )
    stage_options: list[dict[str, str]] = []
    if isinstance(target, ValueStream):
        stage_options.extend(
            {
                "value": f"existing:{stage.id}",
                "label": f"Bestehend · {stage.sequence}. {stage.name}",
            }
            for stage in target.stages.order_by("sequence", "id")
        )
        stage_options.extend(
            {
                "value": f"local:{item.local_key}",
                "label": (
                    "Neu · "
                    f"{item.interpretation_snapshot.get('fields', {}).get('sequence', '-')}. "
                    f"{item.interpretation_snapshot.get('fields', {}).get('name', item.local_key)}"
                ),
            }
            for item in local_stages
            if item.status not in _INVALID_DEPENDENCY_STATES
        )

    def item_sort_key(item: StructuredAdoptionItem):
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.METRIC_SET:
            order = [spec.target_path for spec in STRUCTURED_FIELD_SPECS.values()]
            return (0, order.index(item.target_path), item.local_key)
        if item.candidate_kind == StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE:
            return (
                1,
                item.interpretation_snapshot.get("fields", {}).get("sequence", 9999),
                item.local_key,
            )
        return (2, 0, item.local_key)

    presented = []
    for item in sorted(items, key=item_sort_key):
        item_suggestions = [
            suggestions.get(UUID(value))
            for value in item.source_snapshot.get("suggestion_ids", [])
            if UUID(value) in suggestions
        ]
        reference = item.proposed_snapshot.get("stage_reference", {})
        selected_reference = ""
        dependency_label = "Noch keine Phase gewählt"
        if reference.get("kind") == "existing":
            selected_reference = f"existing:{reference.get('stage_id')}"
            stage = ValueStreamStage.objects.filter(pk=reference.get("stage_id")).first()
            dependency_label = (
                f"Bestehende Phase · {stage.sequence}. {stage.name}"
                if stage
                else "Bestehende Phase nicht mehr verfügbar"
            )
        elif reference.get("kind") == "local":
            selected_reference = f"local:{reference.get('local_key')}"
            dependency_label = f"Neue Phase · {reference.get('local_key')}"
        presented.append(
            {
                "id": item.id,
                "local_key": item.local_key,
                "kind": item.candidate_kind,
                "kind_label": item.get_candidate_kind_display(),
                "status": item.status,
                "status_label": item.get_status_display(),
                "decision": item.decision,
                "decision_label": item.get_decision_display(),
                "effective_source": _effective_source(item),
                "current_database": _display(item.field_snapshot.get("value")),
                "field_rows": _field_rows(item),
                "sources": [
                    {
                        "question": suggestion.source_question,
                        "excerpt": suggestion.source_excerpt,
                        "uncertainty": suggestion.get_uncertainty_display(),
                        "reason": suggestion.uncertainty_reason,
                    }
                    for suggestion in item_suggestions
                    if suggestion is not None
                ],
                "stage_options": stage_options
                if item.candidate_kind == StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
                else [],
                "selected_stage_reference": selected_reference,
                "dependency_label": dependency_label,
                "requires_reconfirmation": (
                    item.status == StructuredAdoptionItem.Status.DEPENDENCY_INVALID
                ),
                "editable": batch.status
                not in {
                    StructuredAdoptionBatch.Status.PROCESSING,
                    StructuredAdoptionBatch.Status.COMMITTED,
                    StructuredAdoptionBatch.Status.REJECTED,
                },
            }
        )
    return {
        "batch": batch,
        "items": presented,
        "ready_to_commit": review_batch_ready(batch),
        "target": target,
        "has_process_item": any(
            item.candidate_kind == StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
            for item in items
        ),
    }
