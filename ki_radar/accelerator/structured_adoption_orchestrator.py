from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_edit_use_case

from . import (
    structured_metric_adoption,
    structured_process_adoption,
    structured_stage_adoption,
)
from .models import CaptureAnalysis, CaptureSession
from .structured_models import (
    StructuredAdoptionAudit,
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)


class StructuredCommitOutcome(StrEnum):
    COMMITTED = "committed"
    REPLAYED = "replayed"


class StructuredCommitError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        step: str,
        error_code: str,
        item: StructuredAdoptionItem | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.step = step
        self.error_code = error_code[:50]
        self.item = item
        self.details = details or {}


class StructuredCommitPermissionDenied(PermissionDenied):
    pass


class StructuredBatchBusy(StructuredCommitError):
    pass


class StructuredBatchTerminal(StructuredCommitError):
    pass


@dataclass(frozen=True)
class StructuredCommitResult:
    outcome: StructuredCommitOutcome
    batch_id: str
    target_object_type: str
    target_object_id: str
    attempt_count: int
    result_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Reservation:
    batch_id: UUID
    attempt_count: int
    replay: StructuredCommitResult | None = None


LOCK_ORDER = (
    "batch",
    "root_target",
    "existing_stages",
    "items",
    "revalidation",
    "forms",
    "domain_writes",
    "audit_and_batch_completion",
)

_RETRYABLE_BATCH_STATES = {
    StructuredAdoptionBatch.Status.OPEN,
    StructuredAdoptionBatch.Status.FAILED,
}
_SELECTED_DECISIONS = {
    StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    StructuredAdoptionItem.Decision.CONFIRMED_EDITED,
    StructuredAdoptionItem.Decision.CURRENT_DATABASE,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        _json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_selected_graph_hash(items) -> str:
    graph = []
    for item in sorted(items, key=lambda entry: (entry.local_key, str(entry.pk))):
        graph.append(
            {
                "local_key": item.local_key,
                "candidate_kind": item.candidate_kind,
                "target_path": item.target_path,
                "target_group_key": item.target_group_key,
                "dependency_key": item.dependency_key_snapshot,
                "status": item.status,
                "decision": item.decision,
                "proposed": item.proposed_snapshot,
                "interpretation": item.interpretation_snapshot,
                "decision_snapshot": item.decision_snapshot,
                "field_snapshot": item.field_snapshot,
                "source_snapshot": item.source_snapshot,
                "confirmed_by_id": item.confirmed_by_id_snapshot,
            }
        )
    return _canonical_hash(graph)


def build_idempotency_key(
    *,
    session_id: UUID,
    analysis_id: UUID,
    target_object_type: str,
    target_object_id: UUID,
    selected_graph_hash: str,
    interpretation_version: str,
) -> str:
    return _canonical_hash(
        {
            "session_id": session_id,
            "analysis_id": analysis_id,
            "target_object_type": target_object_type,
            "target_object_id": target_object_id,
            "selected_graph_hash": selected_graph_hash,
            "interpretation_version": interpretation_version,
        }
    )


def _result_from_batch(
    batch: StructuredAdoptionBatch,
    *,
    replayed: bool,
) -> StructuredCommitResult:
    return StructuredCommitResult(
        outcome=(
            StructuredCommitOutcome.REPLAYED if replayed else StructuredCommitOutcome.COMMITTED
        ),
        batch_id=str(batch.id),
        target_object_type=batch.target_object_type,
        target_object_id=str(batch.target_object_id),
        attempt_count=batch.attempt_count,
        result_snapshot=batch.result_snapshot,
    )


def _expected_idempotency_key(batch: StructuredAdoptionBatch) -> str:
    return build_idempotency_key(
        session_id=batch.session_id_snapshot,
        analysis_id=batch.analysis_id_snapshot,
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        selected_graph_hash=batch.selected_graph_hash,
        interpretation_version=batch.interpretation_version,
    )


def _load_target(batch: StructuredAdoptionBatch, *, lock: bool):
    queryset = None
    if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.USE_CASE:
        queryset = UseCase.objects
    elif batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM:
        queryset = ValueStream.objects
    else:
        raise StructuredCommitError(
            "Der Batch besitzt keinen unterstützten Zieltyp.",
            step="root_target",
            error_code="unsupported_target_type",
        )
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=batch.target_object_id)
    except (UseCase.DoesNotExist, ValueStream.DoesNotExist) as exc:
        raise StructuredCommitError(
            "Das gebundene Zielobjekt existiert nicht mehr.",
            step="root_target",
            error_code="target_missing",
        ) from exc


def _can_edit_target(*, actor, batch: StructuredAdoptionBatch, target) -> bool:
    if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.USE_CASE:
        return can_edit_use_case(actor, target)
    if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM:
        return can_edit_value_stream(actor, target)
    return False


def _assert_permission(*, actor, batch: StructuredAdoptionBatch, target) -> None:
    if not getattr(actor, "is_authenticated", False) or not _can_edit_target(
        actor=actor,
        batch=batch,
        target=target,
    ):
        raise StructuredCommitPermissionDenied(
            "Der Nutzer darf das gebundene Zielobjekt nicht bearbeiten."
        )


def _assert_batch_identity(
    *,
    batch: StructuredAdoptionBatch,
    idempotency_key: str,
) -> None:
    if idempotency_key != batch.idempotency_key:
        raise StructuredCommitError(
            "Der Idempotency-Key gehört nicht zu diesem Batch.",
            step="batch",
            error_code="idempotency_key_mismatch",
        )
    if batch.idempotency_key != _expected_idempotency_key(batch):
        raise StructuredCommitError(
            "Der gespeicherte Idempotency-Key passt nicht zum Batchgraphen.",
            step="batch",
            error_code="idempotency_integrity_failed",
        )


def _preflight(*, batch_id: UUID, actor, idempotency_key: str) -> None:
    batch = StructuredAdoptionBatch.objects.get(pk=batch_id)
    _assert_batch_identity(batch=batch, idempotency_key=idempotency_key)
    target = _load_target(batch, lock=False)
    _assert_permission(actor=actor, batch=batch, target=target)


@transaction.atomic
def _reserve_batch(
    *,
    batch_id: UUID,
    actor,
    idempotency_key: str,
) -> _Reservation:
    batch = StructuredAdoptionBatch.objects.select_for_update().get(pk=batch_id)
    _assert_batch_identity(batch=batch, idempotency_key=idempotency_key)
    if batch.status == StructuredAdoptionBatch.Status.COMMITTED:
        return _Reservation(
            batch_id=batch.id,
            attempt_count=batch.attempt_count,
            replay=_result_from_batch(batch, replayed=True),
        )
    if batch.status == StructuredAdoptionBatch.Status.PROCESSING:
        raise StructuredBatchBusy(
            "Der Batch wird bereits verarbeitet.",
            step="batch",
            error_code="batch_in_progress",
        )
    if batch.status not in _RETRYABLE_BATCH_STATES:
        raise StructuredBatchTerminal(
            "Der Batch befindet sich in einem nicht erneut ausführbaren Endzustand.",
            step="batch",
            error_code=f"batch_{batch.status}",
        )

    now = timezone.now()
    batch.status = StructuredAdoptionBatch.Status.PROCESSING
    batch.processing_by = actor
    batch.processing_started_at = now
    batch.completed_at = None
    batch.attempt_count += 1
    batch.result_snapshot = {}
    batch.error_code = ""
    batch.save(
        update_fields=[
            "status",
            "processing_by",
            "processing_started_at",
            "completed_at",
            "attempt_count",
            "result_snapshot",
            "error_code",
            "updated_at",
        ]
    )
    return _Reservation(batch_id=batch.id, attempt_count=batch.attempt_count)


def _lock_root(batch: StructuredAdoptionBatch):
    return _load_target(batch, lock=True)


def _lock_existing_stages(batch: StructuredAdoptionBatch, target) -> tuple[ValueStreamStage, ...]:
    if batch.target_object_type != StructuredAdoptionBatch.TargetObjectType.VALUE_STREAM:
        return ()
    return tuple(
        ValueStreamStage.objects.select_for_update().filter(value_stream=target).order_by("id")
    )


def _lock_items(batch: StructuredAdoptionBatch) -> tuple[StructuredAdoptionItem, ...]:
    return tuple(
        StructuredAdoptionItem.objects.select_for_update()
        .filter(batch=batch)
        .order_by("local_key", "id")
    )


def _assert_capture_snapshots(batch: StructuredAdoptionBatch) -> None:
    if batch.session_id is not None:
        session = CaptureSession.objects.get(pk=batch.session_id)
        bound_target_id = (
            session.target_use_case_id
            if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.USE_CASE
            else session.target_value_stream_id
        )
        if (
            session.id != batch.session_id_snapshot
            or session.capture_type != batch.target_object_type
            or session.revision != batch.source_revision
            or bound_target_id != batch.target_object_id
        ):
            raise StructuredCommitError(
                "Die Capture-Session stimmt nicht mehr mit dem Batchsnapshot überein.",
                step="revalidation",
                error_code="session_snapshot_stale",
            )
    if batch.analysis_id is not None:
        analysis = CaptureAnalysis.objects.get(pk=batch.analysis_id)
        if (
            analysis.id != batch.analysis_id_snapshot
            or analysis.source_revision != batch.source_revision
            or analysis.capture_type != batch.target_object_type
            or analysis.status != CaptureAnalysis.Status.SUCCESS
            or analysis.session_id != batch.session_id_snapshot
        ):
            raise StructuredCommitError(
                "Die Capture-Analyse stimmt nicht mehr mit dem Batchsnapshot überein.",
                step="revalidation",
                error_code="analysis_snapshot_stale",
            )


def _assert_item_graph(
    *,
    batch: StructuredAdoptionBatch,
    items: tuple[StructuredAdoptionItem, ...],
) -> None:
    if not items:
        raise StructuredCommitError(
            "Der Batch enthält keine strukturierten Items.",
            step="revalidation",
            error_code="empty_item_graph",
        )
    if build_selected_graph_hash(items) != batch.selected_graph_hash:
        raise StructuredCommitError(
            "Der bestätigte Itemgraph wurde nach der Batchbildung verändert.",
            step="revalidation",
            error_code="selected_graph_changed",
        )

    by_id = {item.id: item for item in items}
    for item in items:
        if item.decision == StructuredAdoptionItem.Decision.REJECTED:
            if item.status != StructuredAdoptionItem.Status.REJECTED:
                raise StructuredCommitError(
                    "Ein verworfenes Item besitzt keinen verworfenen Status.",
                    step="revalidation",
                    error_code="rejected_item_state_invalid",
                    item=item,
                )
            continue
        if item.decision not in _SELECTED_DECISIONS:
            raise StructuredCommitError(
                "Ein ausgewähltes Item besitzt keine terminale Nutzerentscheidung.",
                step="revalidation",
                error_code="item_decision_pending",
                item=item,
            )
        if item.status != StructuredAdoptionItem.Status.CONFIRMED:
            raise StructuredCommitError(
                "Ein ausgewähltes Item ist nicht bestätigt.",
                step="revalidation",
                error_code="item_not_confirmed",
                item=item,
            )
        if item.confirmed_by_id_snapshot is None or item.confirmed_at is None:
            raise StructuredCommitError(
                "Dem ausgewählten Item fehlt der Bestätigungssnapshot.",
                step="revalidation",
                error_code="confirmation_snapshot_missing",
                item=item,
            )
        if item.depends_on_id is None:
            if item.dependency_key_snapshot:
                raise StructuredCommitError(
                    "Ein Item enthält einen Abhängigkeitsschlüssel ohne Abhängigkeit.",
                    step="revalidation",
                    error_code="dependency_snapshot_orphaned",
                    item=item,
                )
            continue
        dependency = by_id.get(item.depends_on_id)
        if dependency is None or dependency.batch_id != batch.id:
            raise StructuredCommitError(
                "Die Itemabhängigkeit liegt außerhalb des gesperrten Batches.",
                step="revalidation",
                error_code="dependency_outside_batch",
                item=item,
            )
        if item.dependency_key_snapshot != dependency.local_key:
            raise StructuredCommitError(
                "Der lokale Abhängigkeitsschlüssel passt nicht zum referenzierten Item.",
                step="revalidation",
                error_code="dependency_key_mismatch",
                item=item,
            )
        if dependency.decision == StructuredAdoptionItem.Decision.REJECTED or dependency.status in {
            StructuredAdoptionItem.Status.REJECTED,
            StructuredAdoptionItem.Status.INVALID,
            StructuredAdoptionItem.Status.DEPENDENCY_INVALID,
            StructuredAdoptionItem.Status.CONFLICT,
            StructuredAdoptionItem.Status.STALE,
            StructuredAdoptionItem.Status.FAILED,
        }:
            raise StructuredCommitError(
                "Die lokale Itemabhängigkeit ist nicht ausführbar.",
                step="revalidation",
                error_code="dependency_not_executable",
                item=item,
            )


def _selected_items(
    items: tuple[StructuredAdoptionItem, ...],
    kind: str,
) -> tuple[StructuredAdoptionItem, ...]:
    return tuple(
        item
        for item in items
        if item.candidate_kind == kind
        and item.decision in _SELECTED_DECISIONS
        and item.status == StructuredAdoptionItem.Status.CONFIRMED
    )


def _wrap_execution_error(
    exc: Exception,
    *,
    step: str,
    items: tuple[StructuredAdoptionItem, ...],
) -> StructuredCommitError:
    item = items[0] if items else None
    errors = getattr(exc, "errors", None)
    if isinstance(errors, dict) and errors:
        first_key = sorted(errors)[0]
        keyed_item = next((entry for entry in items if entry.local_key == first_key), None)
        item = keyed_item or item
    error_code = (
        "domain_conflict" if "Conflict" in type(exc).__name__ else "domain_validation_failed"
    )
    return StructuredCommitError(
        str(exc),
        step=step,
        error_code=error_code,
        item=item,
        details={"errors": _json_value(errors)} if errors else {},
    )


def _mark_metric_items_adopted(items: tuple[StructuredAdoptionItem, ...]) -> None:
    if not items:
        return
    resolved_at = timezone.now()
    for item in items:
        item.status = StructuredAdoptionItem.Status.ADOPTED
        item.resolved_at = resolved_at
        item.error_code = ""
        item.save(update_fields=["status", "resolved_at", "error_code", "updated_at"])


def _execute_use_case_group(
    *,
    batch: StructuredAdoptionBatch,
    target: UseCase,
    actor,
    items: tuple[StructuredAdoptionItem, ...],
) -> dict[str, Any]:
    foreign = [
        item
        for item in items
        if item.decision != StructuredAdoptionItem.Decision.REJECTED
        and item.candidate_kind != StructuredAdoptionItem.CandidateKind.METRIC_SET
    ]
    if foreign:
        raise StructuredCommitError(
            "Ein Use-Case-Batch enthält einen unzulässigen Kandidatentyp.",
            step="revalidation",
            error_code="use_case_item_kind_invalid",
            item=foreign[0],
        )
    metric_items = _selected_items(items, StructuredAdoptionItem.CandidateKind.METRIC_SET)
    if not metric_items:
        raise StructuredCommitError(
            "Der Use-Case-Batch enthält keine bestätigte Metrikgruppe.",
            step="revalidation",
            error_code="metric_group_missing",
        )
    try:
        metric_result = structured_metric_adoption.adopt_metric_items(
            use_case_id=target.id,
            actor=actor,
            items=metric_items,
        )
    except Exception as exc:
        raise _wrap_execution_error(exc, step="metric_group", items=metric_items) from exc
    _mark_metric_items_adopted(metric_items)
    return {
        "metrics": {
            "effective_values": _json_value(metric_result.effective_values),
            "sources": metric_result.sources,
            "changed_fields": sorted(metric_result.changed_fields),
        }
    }


def _execute_value_stream_group(
    *,
    batch: StructuredAdoptionBatch,
    target: ValueStream,
    items: tuple[StructuredAdoptionItem, ...],
) -> dict[str, Any]:
    allowed_kinds = {
        StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
        StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
    }
    foreign = [
        item
        for item in items
        if item.decision != StructuredAdoptionItem.Decision.REJECTED
        and item.candidate_kind not in allowed_kinds
    ]
    if foreign:
        raise StructuredCommitError(
            "Ein Value-Stream-Batch enthält einen unzulässigen Kandidatentyp.",
            step="revalidation",
            error_code="value_stream_item_kind_invalid",
            item=foreign[0],
        )

    stage_items = _selected_items(
        items,
        StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE,
    )
    process_items = _selected_items(
        items,
        StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS,
    )
    if not stage_items and not process_items:
        raise StructuredCommitError(
            "Der Value-Stream-Batch enthält keine bestätigten Entwurfsobjekte.",
            step="revalidation",
            error_code="value_stream_graph_empty",
        )

    try:
        stage_result = structured_stage_adoption.adopt_stage_items(
            value_stream_id=target.id,
            items=stage_items,
        )
    except Exception as exc:
        raise _wrap_execution_error(exc, step="value_stream_stages", items=stage_items) from exc

    process_results: dict[str, dict[str, str]] = {}
    for item in process_items:
        try:
            result = structured_process_adoption.adopt_process_item(
                value_stream_id=target.id,
                item=item,
            )
        except Exception as exc:
            raise _wrap_execution_error(
                exc,
                step="process_analysis",
                items=(item,),
            ) from exc
        process_results[item.local_key] = {
            "process_analysis_id": result.process_analysis_id,
            "stage_id": result.stage_id,
        }

    return {
        "stages": stage_result.created_stage_ids,
        "process_analyses": process_results,
    }


def _record_success_audit(
    *,
    batch: StructuredAdoptionBatch,
    actor,
    result_snapshot: dict[str, Any],
) -> None:
    StructuredAdoptionAudit.objects.create(
        batch=batch,
        actor=actor,
        batch_id_snapshot=batch.id,
        session_id_snapshot=batch.session_id_snapshot,
        analysis_id_snapshot=batch.analysis_id_snapshot,
        actor_id_snapshot=getattr(actor, "id", None),
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        idempotency_key=batch.idempotency_key,
        attempt_count=batch.attempt_count,
        event=StructuredAdoptionAudit.Event.COMMITTED,
        outcome="committed",
        step="batch_complete",
        details={"result": result_snapshot},
    )


@transaction.atomic
def _execute_reserved_batch(
    *,
    batch_id: UUID,
    actor,
    idempotency_key: str,
) -> StructuredCommitResult:
    batch = StructuredAdoptionBatch.objects.select_for_update().get(pk=batch_id)
    _assert_batch_identity(batch=batch, idempotency_key=idempotency_key)
    if (
        batch.status != StructuredAdoptionBatch.Status.PROCESSING
        or batch.processing_by_id != getattr(actor, "id", None)
    ):
        raise StructuredCommitError(
            "Der Batch ist nicht für diesen Commitversuch reserviert.",
            step="batch",
            error_code="batch_reservation_lost",
        )

    target = _lock_root(batch)
    _lock_existing_stages(batch, target)
    items = _lock_items(batch)
    _assert_permission(actor=actor, batch=batch, target=target)
    _assert_capture_snapshots(batch)
    _assert_item_graph(batch=batch, items=items)

    if batch.target_object_type == StructuredAdoptionBatch.TargetObjectType.USE_CASE:
        result_payload = _execute_use_case_group(
            batch=batch,
            target=target,
            actor=actor,
            items=items,
        )
    else:
        result_payload = _execute_value_stream_group(
            batch=batch,
            target=target,
            items=items,
        )

    completed_at = timezone.now()
    result_snapshot = {
        "schema": "structured_adoption.result.v1",
        "target": {
            "type": batch.target_object_type,
            "id": str(batch.target_object_id),
        },
        "attempt_count": batch.attempt_count,
        **result_payload,
    }
    _record_success_audit(
        batch=batch,
        actor=actor,
        result_snapshot=result_snapshot,
    )
    batch.status = StructuredAdoptionBatch.Status.COMMITTED
    batch.result_snapshot = result_snapshot
    batch.error_code = ""
    batch.completed_at = completed_at
    batch.processing_by = None
    batch.processing_started_at = None
    batch.save(
        update_fields=[
            "status",
            "result_snapshot",
            "error_code",
            "completed_at",
            "processing_by",
            "processing_started_at",
            "updated_at",
        ]
    )
    return _result_from_batch(batch, replayed=False)


def _failure_status(error: StructuredCommitError) -> str:
    if "conflict" in error.error_code:
        return StructuredAdoptionBatch.Status.CONFLICT
    if "stale" in error.error_code or error.error_code == "target_missing":
        return StructuredAdoptionBatch.Status.STALE
    return StructuredAdoptionBatch.Status.FAILED


@transaction.atomic
def _record_failure(
    *,
    batch_id: UUID,
    actor,
    error: StructuredCommitError,
) -> None:
    batch = StructuredAdoptionBatch.objects.select_for_update().get(pk=batch_id)
    if batch.status == StructuredAdoptionBatch.Status.COMMITTED:
        return
    completed_at = timezone.now()
    batch.status = _failure_status(error)
    batch.error_code = error.error_code
    batch.completed_at = completed_at
    batch.processing_by = None
    batch.processing_started_at = None
    batch.save(
        update_fields=[
            "status",
            "error_code",
            "completed_at",
            "processing_by",
            "processing_started_at",
            "updated_at",
        ]
    )
    item = error.item
    StructuredAdoptionAudit.objects.create(
        batch=batch,
        item=item,
        actor=actor,
        batch_id_snapshot=batch.id,
        item_id_snapshot=item.id if item is not None else None,
        session_id_snapshot=batch.session_id_snapshot,
        analysis_id_snapshot=batch.analysis_id_snapshot,
        actor_id_snapshot=getattr(actor, "id", None),
        target_object_type=batch.target_object_type,
        target_object_id=batch.target_object_id,
        idempotency_key=batch.idempotency_key,
        attempt_count=batch.attempt_count,
        event=(
            StructuredAdoptionAudit.Event.CONFLICT
            if batch.status == StructuredAdoptionBatch.Status.CONFLICT
            else StructuredAdoptionAudit.Event.FAILED
        ),
        outcome=batch.status,
        step=error.step,
        item_kind=item.candidate_kind if item is not None else "",
        item_local_key=item.local_key if item is not None else "",
        target_field=item.target_path if item is not None else "",
        error_code=error.error_code,
        details={"message": str(error), **_json_value(error.details)},
    )


def _normalize_error(exc: Exception) -> StructuredCommitError:
    if isinstance(exc, StructuredCommitError):
        return exc
    if isinstance(exc, PermissionDenied):
        return StructuredCommitError(
            str(exc),
            step="revalidation",
            error_code="permission_denied",
        )
    return StructuredCommitError(
        str(exc) or type(exc).__name__,
        step="orchestration",
        error_code="unexpected_commit_failure",
        details={"exception_type": type(exc).__name__},
    )


def commit_structured_batch(
    *,
    batch_id: UUID,
    actor,
    idempotency_key: str,
) -> StructuredCommitResult:
    _preflight(batch_id=batch_id, actor=actor, idempotency_key=idempotency_key)
    reservation = _reserve_batch(
        batch_id=batch_id,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    if reservation.replay is not None:
        return reservation.replay
    try:
        return _execute_reserved_batch(
            batch_id=reservation.batch_id,
            actor=actor,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        error = _normalize_error(exc)
        _record_failure(batch_id=reservation.batch_id, actor=actor, error=error)
        if error is exc:
            raise
        raise error from exc
