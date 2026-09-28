from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ki_radar.accelerator.investigation_execution import request_execution
from ki_radar.accelerator.investigation_runtime import (
    StartInvestigationRequest,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import bind_discovery_snapshot_to_process
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.retention_policy import completed_capture_expiry

from .focus import ValueStreamFocus
from .models import ProcessAnalysis, ValueStream, ValueStreamStage
from .permissions import can_manage_architecture
from .provenance import build_process_source_snapshot
from .stage_focus import StageFocusDecision


class DiscoveryMaterializationError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DiscoveryMaterializationResult:
    value_stream_id: UUID
    process_analysis_id: UUID
    investigation_snapshot_id: UUID
    investigation_run_id: UUID
    reused: bool = False


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DiscoveryMaterializationError(
            f"Der bestätigte Discovery-Draft enthält kein belastbares Feld „{field}“.",
            code="incomplete_discovery_draft",
        )
    return text


def _optional_text(value: object) -> str:
    return str(value or "").strip()


def _reported_or_unknown(value: object) -> str:
    return _optional_text(value) or "Nicht in den autorisierten Quellen belegt."


def _existing_result(session: CaptureSession, analysis_id) -> DiscoveryMaterializationResult | None:
    metadata = dict((session.answers or {}).get("materialization") or {})
    if not metadata or str(metadata.get("analysis_id")) != str(analysis_id):
        return None
    try:
        value_stream = ValueStream.objects.get(
            pk=metadata["value_stream_id"],
            capture_sessions=session,
        )
        process = ProcessAnalysis.objects.get(
            pk=metadata["process_analysis_id"],
            stage__value_stream=value_stream,
        )
    except (KeyError, ValueError, ValueStream.DoesNotExist, ProcessAnalysis.DoesNotExist):
        return None
    from ki_radar.accelerator.investigation_models import (
        InvestigationRun,
        InvestigationSourceSnapshot,
    )

    try:
        snapshot = InvestigationSourceSnapshot.objects.get(
            pk=metadata["investigation_snapshot_id"],
            process_analysis=process,
        )
        run = InvestigationRun.objects.get(
            pk=metadata["investigation_run_id"],
            process_analysis=process,
            source_snapshot=snapshot,
        )
    except (
        KeyError,
        ValueError,
        InvestigationSourceSnapshot.DoesNotExist,
        InvestigationRun.DoesNotExist,
    ):
        return None
    return DiscoveryMaterializationResult(
        value_stream_id=value_stream.pk,
        process_analysis_id=process.pk,
        investigation_snapshot_id=snapshot.pk,
        investigation_run_id=run.pk,
        reused=True,
    )


def _criteria_snapshot(stages: list[ValueStreamStage], stage_drafts: list[dict]) -> dict:
    draft_by_key = {str(item["key"]): item for item in stage_drafts}
    return {
        str(stage.pk): {
            "sequence": stage.sequence,
            "name": stage.name,
            "impact": "",
            "pain_intensity": "",
            "improvement_potential": "",
            "data_accessibility": "",
            "change_effort": "",
            "time_to_value": "not_assessed",
            "evidence_basis": (
                "indicative"
                if draft_by_key.get(getattr(stage, "_discovery_key", ""), {}).get("evidence_refs")
                else "hypothesis"
            ),
            "indicators": {
                "pain_points": stage.pain_points,
                "baseline_metrics": stage.baseline_metrics,
                "evidence_refs": draft_by_key.get(
                    getattr(stage, "_discovery_key", ""),
                    {},
                ).get("evidence_refs", []),
            },
        }
        for stage in stages
    }


@transaction.atomic
def materialize_discovery_and_start_investigation(
    *,
    actor,
    session_id,
    analysis_id,
    selected_stage_key: str,
    expected_revision: int,
) -> DiscoveryMaterializationResult:
    try:
        session = (
            CaptureSession.objects.select_for_update()
            .select_related("owner__business_unit")
            .get(pk=session_id, owner=actor)
        )
    except (CaptureSession.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Die autonome Discovery ist nicht zugänglich.") from exc

    if (
        session.capture_type != CaptureSession.CaptureType.VALUE_STREAM
        or session.mode != CaptureSession.Mode.AUTONOMOUS
        or not can_manage_architecture(actor)
    ):
        raise PermissionDenied("Die autonome Discovery ist nicht materialisierbar.")

    if session.status == CaptureSession.Status.COMPLETED:
        existing = _existing_result(session, analysis_id)
        if existing is not None:
            return existing
        raise DiscoveryMaterializationError(
            "Diese Discovery wurde bereits mit einem anderen Stand abgeschlossen.",
            code="materialization_conflict",
        )
    if session.status != CaptureSession.Status.DRAFT:
        raise DiscoveryMaterializationError(
            "Diese Discovery ist nicht mehr bearbeitbar.",
            code="capture_not_editable",
        )
    if session.revision != expected_revision:
        raise DiscoveryMaterializationError(
            "Die Discovery wurde zwischenzeitlich geändert. Bitte den aktuellen Stand neu laden.",
            code="revision_conflict",
        )
    if session.owner.business_unit is None or not session.owner.business_unit.is_active:
        raise DiscoveryMaterializationError(
            "Die zugeordnete Organisationseinheit fehlt oder ist inaktiv.",
            code="missing_business_unit",
        )

    try:
        analysis = CaptureAnalysis.objects.select_for_update().get(
            pk=analysis_id,
            session=session,
            status=CaptureAnalysis.Status.SUCCESS,
        )
    except (CaptureAnalysis.DoesNotExist, ValueError) as exc:
        raise DiscoveryMaterializationError(
            "Es gibt keinen freigegebenen Discovery-Draft für diesen Stand.",
            code="analysis_not_approved",
        ) from exc
    if analysis.source_revision != session.revision:
        raise DiscoveryMaterializationError(
            "Der Discovery-Draft basiert auf einer älteren Eingaberevision.",
            code="analysis_revision_conflict",
        )
    verifier = dict(analysis.verification_payload or {})
    if verifier.get("status") != "approved":
        raise DiscoveryMaterializationError(
            "Der unabhängige Discovery-Review ist nicht freigegeben.",
            code="analysis_not_approved",
        )

    result_payload = dict(analysis.result_payload or {})
    draft = result_payload.get("draft")
    if not isinstance(draft, dict):
        raise DiscoveryMaterializationError(
            "Der strukturierte Discovery-Draft fehlt.",
            code="missing_discovery_payload",
        )
    stage_drafts = draft.get("stages")
    if not isinstance(stage_drafts, list) or not stage_drafts:
        raise DiscoveryMaterializationError(
            "Der Discovery-Draft enthält keine Value-Stream-Phasen.",
            code="missing_stages",
        )
    selected_key = str(selected_stage_key or "").strip()
    selected_draft = next(
        (item for item in stage_drafts if str(item.get("key") or "") == selected_key),
        None,
    )
    if selected_draft is None:
        raise DiscoveryMaterializationError(
            "Die gewählte Fokusphase gehört nicht zum geprüften Discovery-Draft.",
            code="invalid_focus_stage",
        )

    value_draft = dict(draft.get("value_stream") or {})
    focus_draft = dict(draft.get("focus") or {})
    process_draft = dict(draft.get("process_analysis") or {})

    value_stream = ValueStream(
        name=_required_text(value_draft.get("name"), field="Value Stream Name"),
        description=_optional_text(value_draft.get("description")),
        business_unit=session.owner.business_unit,
        owner=actor,
        created_by=actor,
        trigger=_required_text(value_draft.get("trigger"), field="Value Stream Trigger"),
        outcome=_required_text(value_draft.get("outcome"), field="Value Stream Outcome"),
        scope_in=_required_text(value_draft.get("scope_in"), field="Value Stream Scope"),
        scope_out=_optional_text(value_draft.get("scope_out")),
        strategic_objective=_optional_text(value_draft.get("strategic_objective")),
        stakeholders=_optional_text(value_draft.get("stakeholders")),
        constraints=_optional_text(value_draft.get("constraints")),
        status=ValueStream.Status.ACTIVE,
    )
    value_stream.full_clean()
    value_stream.save()

    stages: list[ValueStreamStage] = []
    stages_by_key: dict[str, ValueStreamStage] = {}
    for index, stage_draft in enumerate(stage_drafts, start=1):
        stage = ValueStreamStage(
            value_stream=value_stream,
            sequence=index,
            name=_required_text(stage_draft.get("name"), field=f"Phase {index} Name"),
            description=_optional_text(stage_draft.get("description")),
            actors=_optional_text(stage_draft.get("roles")),
            systems=_optional_text(stage_draft.get("systems")),
            documents=_optional_text(stage_draft.get("documents")),
            pain_points=_optional_text(stage_draft.get("pain_points")),
            baseline_metrics=_optional_text(stage_draft.get("baseline_metrics")),
        )
        stage.full_clean()
        stage.save()
        stage._discovery_key = str(stage_draft.get("key") or "")
        stages.append(stage)
        stages_by_key[stage._discovery_key] = stage

    selected_stage = stages_by_key[selected_key]
    focus = ValueStreamFocus(
        value_stream=value_stream,
        business_domain=_required_text(
            focus_draft.get("business_domain"),
            field="Fachdomäne",
        ),
        capability=_required_text(focus_draft.get("capability"), field="Business Capability"),
        strategic_impact=_required_text(
            focus_draft.get("strategic_impact"),
            field="Strategischer Impact",
        ),
        economic_potential=_required_text(
            focus_draft.get("economic_potential"),
            field="Wirtschaftliches Potenzial",
        ),
        pain_intensity=_required_text(
            focus_draft.get("pain_intensity"),
            field="Pain Intensity",
        ),
        data_accessibility=_required_text(
            focus_draft.get("data_accessibility"),
            field="Datenzugänglichkeit",
        ),
        change_effort=_required_text(
            focus_draft.get("change_effort"),
            field="Veränderungsaufwand",
        ),
        status=ValueStreamFocus.Status.SELECTED,
        rationale=_required_text(focus_draft.get("rationale"), field="Fokusbegründung"),
        updated_by=actor,
    )
    focus.full_clean()
    focus.save()

    recommended_key = str(focus_draft.get("recommended_stage_key") or "")
    if selected_key == recommended_key:
        decision_rationale = focus.rationale
    else:
        decision_rationale = (
            f"Im Scope-/Fokus-Review wurde „{selected_stage.name}“ statt der "
            "vorgeschlagenen Fokusphase ausgewählt."
        )
    StageFocusDecision.objects.create(
        value_stream=value_stream,
        selected_stage=selected_stage,
        criteria_snapshot=_criteria_snapshot(stages, stage_drafts),
        rationale=decision_rationale,
        is_short_path=False,
        short_path_reason="",
        selected_by=actor,
    )

    process = ProcessAnalysis(
        stage=selected_stage,
        name=_required_text(process_draft.get("name"), field="ProcessAnalysis Name"),
        status=ProcessAnalysis.Status.DRAFT,
        scope_start=_required_text(process_draft.get("scope_start"), field="Prozessstart"),
        scope_end=_required_text(process_draft.get("scope_end"), field="Prozessende"),
        trigger=_required_text(process_draft.get("trigger"), field="Prozess-Trigger"),
        outcome=_required_text(process_draft.get("outcome"), field="Prozess-Outcome"),
        current_flow=_required_text(process_draft.get("current_flow"), field="Ist-Ablauf"),
        roles=_reported_or_unknown(process_draft.get("roles")),
        systems=_reported_or_unknown(process_draft.get("systems")),
        data_objects=_reported_or_unknown(process_draft.get("data_objects")),
        business_rules=_optional_text(process_draft.get("business_rules")),
        handoffs=_optional_text(process_draft.get("handoffs")),
        bottlenecks=_required_text(process_draft.get("bottlenecks"), field="Bottlenecks"),
        diagnostic_observations=_optional_text(process_draft.get("observations")),
        cause_hypotheses=_optional_text(process_draft.get("cause_hypotheses")),
        confirmed_causes="",
        constraints=_optional_text(process_draft.get("constraints")),
        exceptions=_optional_text(process_draft.get("exceptions")),
        baseline_metrics=_reported_or_unknown(process_draft.get("baseline_metrics")),
        target_state_principles="",
        analyzed_by=actor,
    )
    process.source_snapshot = build_process_source_snapshot(selected_stage)
    process.full_clean()
    process.save()

    discovery_snapshot_id = result_payload.get("discovery_snapshot_id")
    if not discovery_snapshot_id:
        raise DiscoveryMaterializationError(
            "Der autorisierte Discovery-Quellenstand fehlt.",
            code="missing_discovery_snapshot",
        )
    decision_question = (
        f"Welche Ursachen und belastbaren Lösungsrichtungen werden für „{process.name}“ "
        "durch die autorisierten Quellen am stärksten gestützt?"
    )
    snapshot_result = bind_discovery_snapshot_to_process(
        actor=actor,
        discovery_snapshot_id=discovery_snapshot_id,
        process_analysis_id=process.pk,
        decision_question=decision_question,
    )
    handle = start_investigation(
        actor=actor,
        request=StartInvestigationRequest(
            snapshot_id=snapshot_result.snapshot_id,
            idempotency_key=(
                f"ap1-{session.pk.hex[:12]}-{analysis.pk.hex[:12]}"
            ),
        ),
    )
    request_execution(actor=actor, handle=handle)

    answers = dict(session.answers or {})
    answers["materialization"] = {
        "analysis_id": str(analysis.pk),
        "value_stream_id": str(value_stream.pk),
        "process_analysis_id": str(process.pk),
        "discovery_snapshot_id": str(discovery_snapshot_id),
        "investigation_snapshot_id": str(snapshot_result.snapshot_id),
        "manifest_hash": snapshot_result.manifest_hash,
        "investigation_run_id": str(handle.run_id),
        "selected_stage_key": selected_key,
    }
    now = timezone.now()
    session.answers = answers
    session.target_value_stream = value_stream
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = now
    session.expires_at = completed_capture_expiry(now=now)
    session.revision += 1
    session.save(
        update_fields=[
            "answers",
            "target_value_stream",
            "status",
            "completed_at",
            "expires_at",
            "revision",
            "updated_at",
        ]
    )

    return DiscoveryMaterializationResult(
        value_stream_id=value_stream.pk,
        process_analysis_id=process.pk,
        investigation_snapshot_id=snapshot_result.snapshot_id,
        investigation_run_id=handle.run_id,
        reused=handle.reused,
    )
