"""Provenance-backed permission to continue drafts, never a binding selection gate."""

from django.core.exceptions import ValidationError

from ki_radar.accelerator import strategic_discovery as strategic
from ki_radar.accelerator.investigation_models import InvestigationSourceSnapshot
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession

from .discovery_materialization import _existing_result
from .focus import get_value_stream_focus


def has_strategic_exploration(process) -> bool:
    """Recognize an actual materialization and its frozen human scope; fail closed."""
    source = process.source_snapshot
    if not isinstance(source, dict):
        return False
    record = source.get("strategic_exploration")
    if not isinstance(record, dict) or record.get("schema") != strategic.SCHEMA:
        return False
    focus = get_value_stream_focus(process.stage.value_stream)
    if focus is not None and focus.is_terminal:
        return False
    scope = record.get("human_scope")
    if (
        not isinstance(scope, dict)
        or strategic.missing_scope_question(scope)
        or scope.get("explicit_strategic") is not True
        or scope.get("input_schema") != strategic.INPUT_SCHEMA
        or scope.get("actor_id") != record.get("scope_confirmed_by")
    ):
        return False
    # This process-owned immutable copy survives capture retention. No request data is used.
    if process.investigation_source_snapshots.filter(
        process_context__strategic_exploration=record,
        process_context__materialized_stage_id=str(process.stage_id),
    ).exists():
        return True
    # Compatibility for strategic materializations made before the durable copy existed.
    try:
        analysis = CaptureAnalysis.objects.select_related("session").get(
            pk=record.get("analysis_id"),
            status=CaptureAnalysis.Status.SUCCESS,
            extraction_schema_version=strategic.SCHEMA,
            session__status__in=[CaptureSession.Status.COMPLETED, CaptureSession.Status.EXPIRED],
            session__target_value_stream=process.stage.value_stream,
        )
        session = analysis.session
        result = _existing_result(session, analysis.pk)
        if result is None or result.process_analysis_id != process.pk:
            return False
        snapshot = InvestigationSourceSnapshot.objects.get(
            pk=analysis.result_payload.get("discovery_snapshot_id"), capture_session=session
        )
        scope = strategic.frozen_human_scope(session, snapshot)
        return bool(
            not strategic.missing_scope_question(scope)
            and record.get("human_scope") == scope
            and record.get("scope_confirmed_by") == session.owner_id
            and record.get("scope_confirmed_at")
            and source.get("name", {}).get("id") == str(process.stage_id)
        )
    except (
        CaptureAnalysis.DoesNotExist,
        InvestigationSourceSnapshot.DoesNotExist,
        ValidationError,
    ):
        return False
