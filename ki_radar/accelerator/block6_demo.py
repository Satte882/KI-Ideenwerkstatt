from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
)
from ki_radar.use_cases.models import UseCase

from . import structured_adoption_orchestrator
from .catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from .extraction_contract import EXTRACTION_PROMPT_VERSION, EXTRACTION_SCHEMA_VERSION
from .models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from .services import create_capture_session
from .structured_models import StructuredAdoptionBatch, StructuredAdoptionItem
from .structured_review import (
    StructuredReviewAction,
    commit_review_batch,
    decide_review_item,
    get_or_create_review_batch,
)
from .target_binding import bind_capture_target

DEMO_USERNAME = "block6-real-demo"
DEMO_BUSINESS_UNIT = "Block-6-Real-DEMO"
VALUE_STREAM_DEMO_KEY = "block6-real-demo-value-stream"
ROLLBACK_STREAM_DEMO_KEY = "block6-real-demo-rollback"
USE_CASE_DEMO_KEY = "block6-real-demo-use-case"

PROCESS_FIELDS = {
    "name": "Angebotsvergleich",
    "scope_start": "Freigegebener Bedarf und Angebote liegen vor",
    "scope_end": "Bevorzugtes Angebot ist nachvollziehbar ausgewählt",
    "trigger": "Mindestens zwei vergleichbare Angebote liegen vor",
    "outcome": "Das wirtschaftlichste Angebot ist ausgewählt",
    "current_flow": "Einkauf vergleicht Angebote manuell.",
    "roles": "Einkauf, Fachbereich",
    "systems": "ERP, Tabellenkalkulation",
    "data_objects": "Angebote, Bestellanforderung",
    "bottlenecks": "Medienbruch und manueller Vergleich",
    "baseline_metrics": "11 Minuten je Angebotsvergleich",
}

STAGES = (
    ("stage-01", 1, "Bedarf klären"),
    ("stage-02", 2, "Angebote vergleichen"),
    ("stage-03", 3, "Bestellung auslösen"),
)


def _prepare_actor() -> tuple[User, BusinessUnit]:
    business_unit, _ = BusinessUnit.objects.get_or_create(name=DEMO_BUSINESS_UNIT)
    actor, _ = User.objects.get_or_create(
        username=DEMO_USERNAME,
        defaults={"business_unit": business_unit, "is_active": True},
    )
    changed_fields = []
    if actor.business_unit_id != business_unit.pk:
        actor.business_unit = business_unit
        changed_fields.append("business_unit")
    if not actor.is_active:
        actor.is_active = True
        changed_fields.append("is_active")
    if changed_fields:
        actor.save(update_fields=[*changed_fields, "updated_at"])
    group, _ = Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)
    actor.groups.add(group)
    return actor, business_unit


def _reset_demo_data(actor: User) -> None:
    StructuredAdoptionBatch.objects.filter(created_by=actor).delete()
    CaptureSession.objects.filter(owner=actor).delete()
    UseCase.objects.filter(demo_key=USE_CASE_DEMO_KEY).delete()
    ValueStream.objects.filter(
        demo_key__in=[VALUE_STREAM_DEMO_KEY, ROLLBACK_STREAM_DEMO_KEY]
    ).delete()


def _completed_session(*, actor: User, target, capture_type: str) -> CaptureSession:
    session = create_capture_session(
        actor=actor,
        capture_type=capture_type,
        working_title=f"[Real-DEMO] {target}",
    )
    bind_capture_target(actor=actor, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])
    return session


def _analysis(*, session: CaptureSession, actor: User, source_hash: str) -> CaptureAnalysis:
    now = timezone.now()
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=actor,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash=source_hash,
        capture_type=session.capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        started_at=now,
        finished_at=now,
    )


def _suggestion(
    *,
    analysis: CaptureAnalysis,
    target_object_type: str,
    target_field: str,
    field_type: str,
    value,
    group_key: str = "",
) -> CaptureFieldSuggestion:
    return CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=target_object_type,
        target_field=target_field,
        target_group_key=group_key,
        field_type=field_type,
        suggested_value=value,
        source_question="real_demo_source",
        source_excerpt=f"[Real-DEMO] {target_field}: {value}",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Reproduzierbarer Block-6-Abschlussnachweis.",
    )


def _metric_suggestions(analysis: CaptureAnalysis) -> None:
    _suggestion(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.baseline",
        field_type=CaptureFieldSuggestion.FieldType.DECIMAL,
        value="11,0 min",
    )
    _suggestion(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.target",
        field_type=CaptureFieldSuggestion.FieldType.DECIMAL,
        value="8,0 min",
    )
    _suggestion(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.measurement_method",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        value="Zeitmessung über 20 Angebotsvergleiche",
    )


def _stage_suggestions(
    analysis: CaptureAnalysis,
    *,
    key: str,
    sequence: int,
    name: str,
) -> None:
    _suggestion(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].sequence",
        field_type=CaptureFieldSuggestion.FieldType.INTEGER,
        value=sequence,
        group_key=key,
    )
    _suggestion(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        value=name,
        group_key=key,
    )


def _process_suggestions(analysis: CaptureAnalysis) -> None:
    for field_name, value in PROCESS_FIELDS.items():
        _suggestion(
            analysis=analysis,
            target_object_type=CaptureFieldSuggestion.TargetObjectType.PROCESS_ANALYSIS,
            target_field=f"process_analysis.{field_name}",
            field_type=CaptureFieldSuggestion.FieldType.TEXT,
            value=value,
        )


def _create_roots(*, actor: User, business_unit: BusinessUnit) -> tuple[ValueStream, UseCase]:
    value_stream = ValueStream.objects.create(
        demo_key=VALUE_STREAM_DEMO_KEY,
        name="[Real-DEMO] Beschaffungsbedarf bis Bestellung",
        business_unit=business_unit,
        owner=actor,
        trigger="Ein freigegebener Bedarf liegt vor.",
        outcome="Die Bestellung ist ausgelöst.",
        scope_in="Vom freigegebenen Bedarf bis zur Bestellung.",
        status=ValueStream.Status.DRAFT,
        created_by=actor,
    )
    use_case = UseCase.objects.create(
        demo_key=USE_CASE_DEMO_KEY,
        title="[Real-DEMO] KI-Assistenz Angebotsvergleich",
        problem_statement="Der manuelle Angebotsvergleich dauert zu lange.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        business_owner=actor,
        submitter=actor,
        expected_benefit="Bearbeitungszeit reduzieren",
        metric_name="Bearbeitungszeit Angebotsvergleich",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="min",
        metric_baseline=Decimal("10"),
        metric_target=Decimal("8.25"),
        metric_measurement_method="Zeitmessung in 20 Fällen",
        status=UseCase.Status.IDEA,
        decision_status=UseCase.DecisionStatus.CLARIFICATION,
    )
    return value_stream, use_case


def _exercise_metric_merge(*, actor: User, use_case: UseCase) -> dict[str, object]:
    session = _completed_session(
        actor=actor,
        target=use_case,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    analysis = _analysis(session=session, actor=actor, source_hash="6" * 64)
    _metric_suggestions(analysis)
    batch = get_or_create_review_batch(analysis_id=analysis.id, actor=actor)
    by_path = {item.target_path: item for item in batch.items.all()}

    decide_review_item(
        batch_id=batch.id,
        item_id=by_path["use_case.metric.baseline"].id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
    )
    decide_review_item(
        batch_id=batch.id,
        item_id=by_path["use_case.metric.target"].id,
        actor=actor,
        action=StructuredReviewAction.REJECT,
    )
    decide_review_item(
        batch_id=batch.id,
        item_id=by_path["use_case.metric.measurement_method"].id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
    )
    commit_review_batch(batch_id=batch.id, actor=actor)

    use_case.refresh_from_db()
    return {
        "confirmed_paths": [
            "use_case.metric.baseline",
            "use_case.metric.measurement_method",
        ],
        "rejected_paths": ["use_case.metric.target"],
        "final_baseline": format(use_case.metric_baseline.normalize(), "f"),
        "final_target": format(use_case.metric_target.normalize(), "f"),
        "final_measurement_method": use_case.metric_measurement_method,
    }


def _exercise_value_stream_graph(*, actor: User, value_stream: ValueStream) -> dict[str, object]:
    session = _completed_session(
        actor=actor,
        target=value_stream,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    analysis = _analysis(session=session, actor=actor, source_hash="7" * 64)
    for key, sequence, name in STAGES:
        _stage_suggestions(analysis, key=key, sequence=sequence, name=name)
    _process_suggestions(analysis)

    batch = get_or_create_review_batch(analysis_id=analysis.id, actor=actor)
    stage_items = {
        item.local_key: item
        for item in batch.items.filter(
            candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
        )
    }
    process_item = batch.items.get(
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
    )

    for key, _sequence, _name in STAGES:
        decide_review_item(
            batch_id=batch.id,
            item_id=stage_items[key].id,
            actor=actor,
            action=StructuredReviewAction.CONFIRM,
        )
    decide_review_item(
        batch_id=batch.id,
        item_id=process_item.id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
        stage_reference="local:stage-02",
    )

    decide_review_item(
        batch_id=batch.id,
        item_id=stage_items["stage-02"].id,
        actor=actor,
        action=StructuredReviewAction.REJECT,
    )
    process_item.refresh_from_db()
    cascade_invalidated = (
        process_item.status == StructuredAdoptionItem.Status.DEPENDENCY_INVALID
        and process_item.decision == StructuredAdoptionItem.Decision.PENDING
    )

    decide_review_item(
        batch_id=batch.id,
        item_id=stage_items["stage-02"].id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
    )
    decide_review_item(
        batch_id=batch.id,
        item_id=process_item.id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
        stage_reference="local:stage-02",
    )
    process_item.refresh_from_db()
    process_reconfirmed = (
        process_item.status == StructuredAdoptionItem.Status.CONFIRMED
        and process_item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL
    )

    commit_review_batch(batch_id=batch.id, actor=actor)

    stages = list(value_stream.stages.order_by("sequence", "id"))
    process = ProcessAnalysis.objects.get(stage__value_stream=value_stream)
    return {
        "stage_count": len(stages),
        "stage_names": [stage.name for stage in stages],
        "process_count": ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count(),
        "process_stage": process.stage.name,
        "process_status": process.status,
        "cascade_invalidated": cascade_invalidated,
        "process_reconfirmed": process_reconfirmed,
    }


def _exercise_rollback(*, actor: User, business_unit: BusinessUnit) -> dict[str, object]:
    value_stream = ValueStream.objects.create(
        demo_key=ROLLBACK_STREAM_DEMO_KEY,
        name="[Real-DEMO] Rollback-Nachweis",
        business_unit=business_unit,
        owner=actor,
        trigger="Rollback-Test startet.",
        outcome="Keine Teilobjekte bleiben bestehen.",
        scope_in="Nur technischer Abschlussnachweis.",
        status=ValueStream.Status.DRAFT,
        created_by=actor,
    )
    session = _completed_session(
        actor=actor,
        target=value_stream,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    analysis = _analysis(session=session, actor=actor, source_hash="8" * 64)
    _stage_suggestions(
        analysis,
        key="rollback-stage",
        sequence=1,
        name="Rollback-Phase",
    )
    _process_suggestions(analysis)
    batch = get_or_create_review_batch(analysis_id=analysis.id, actor=actor)
    stage_item = batch.items.get(
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
    )
    process_item = batch.items.get(
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
    )
    decide_review_item(
        batch_id=batch.id,
        item_id=stage_item.id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
    )
    decide_review_item(
        batch_id=batch.id,
        item_id=process_item.id,
        actor=actor,
        action=StructuredReviewAction.CONFIRM,
        stage_reference="local:rollback-stage",
    )

    def fail_success_audit(**kwargs):
        raise RuntimeError("simulierter Real-DEMO-Abschlussfehler")

    error_code = ""
    error_step = ""
    with patch.object(
        structured_adoption_orchestrator,
        "_record_success_audit",
        fail_success_audit,
    ):
        try:
            commit_review_batch(batch_id=batch.id, actor=actor)
        except structured_adoption_orchestrator.StructuredCommitError as exc:
            error_code = exc.error_code
            error_step = exc.step

    batch.refresh_from_db()
    return {
        "batch_status": batch.status,
        "error_code": error_code,
        "error_step": error_step,
        "stage_count": value_stream.stages.count(),
        "process_count": ProcessAnalysis.objects.filter(stage__value_stream=value_stream).count(),
    }


def run_block6_real_demo() -> dict[str, object]:
    actor, business_unit = _prepare_actor()
    _reset_demo_data(actor)
    value_stream, use_case = _create_roots(actor=actor, business_unit=business_unit)

    metric_report = _exercise_metric_merge(actor=actor, use_case=use_case)
    graph_report = _exercise_value_stream_graph(actor=actor, value_stream=value_stream)
    rollback_report = _exercise_rollback(actor=actor, business_unit=business_unit)

    value_stream.refresh_from_db()
    use_case.refresh_from_db()
    process = ProcessAnalysis.objects.get(stage__value_stream=value_stream)
    return {
        "marker": "[Real-DEMO]",
        "schema_version": "1",
        "path": "structured_adoption",
        "legacy_blueprint_importer_used": False,
        "metric_merge": metric_report,
        "value_stream_graph": graph_report,
        "rollback": rollback_report,
        "gates": {
            "value_stream_status": value_stream.status,
            "use_case_status": use_case.status,
            "use_case_decision_status": use_case.decision_status,
            "process_validation_count": ProcessValidation.objects.filter(
                process_analysis=process
            ).count(),
            "solution_option_count": SolutionOption.objects.filter(
                process_analysis=process
            ).count(),
            "solution_selection_decision_count": SolutionSelectionDecision.objects.filter(
                process_analysis=process
            ).count(),
        },
    }
