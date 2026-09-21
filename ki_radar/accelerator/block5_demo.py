from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER
from ki_radar.architecture.models import ValueStream
from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.use_cases.models import UseCase

from .adoption_service import adopt_field_candidate, reject_field_candidate
from .candidate_snapshot import create_adoption_candidates
from .catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from .extraction_contract import EXTRACTION_PROMPT_VERSION, EXTRACTION_SCHEMA_VERSION
from .models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionAudit,
    FieldAdoptionCandidate,
)
from .services import create_capture_session
from .target_binding import bind_capture_target

DEMO_USERNAME = "block5-real-demo"
DEMO_BUSINESS_UNIT = "Block-5-Real-DEMO"
VALUE_STREAM_DEMO_KEY = "block5-real-demo-value-stream"
USE_CASE_DEMO_KEY = "block5-real-demo-use-case"


@dataclass(frozen=True)
class TimedAction:
    elapsed_ms: int


def _timed(action, /, *args, **kwargs) -> TimedAction:
    started = perf_counter()
    action(*args, **kwargs)
    return TimedAction(elapsed_ms=max(1, round((perf_counter() - started) * 1000)))


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


def _analysis(
    *,
    session: CaptureSession,
    actor: User,
    source_hash: str,
    duration_ms: int,
    cost: Decimal,
) -> CaptureAnalysis:
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
        provider="openrouter",
        model_name="openai/gpt-5-mini-real-demo",
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        started_at=now,
        finished_at=now,
        duration_ms=duration_ms,
        prompt_tokens=900,
        completion_tokens=300,
        total_tokens=1200,
        cost=cost,
    )


def _suggestion(
    *,
    analysis: CaptureAnalysis,
    field_name: str,
    value: str,
    uncertainty: str = CaptureFieldSuggestion.Uncertainty.LOW,
) -> CaptureFieldSuggestion:
    return CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=analysis.capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=value,
        source_question="real_demo_source",
        source_excerpt=f"[Real-DEMO] {value}",
        uncertainty=uncertainty,
        uncertainty_reason="Reproduzierbarer fachlicher Real-DEMO-Nachweis.",
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
    FieldAdoptionAudit.objects.filter(actor=actor).delete()
    CaptureSession.objects.filter(owner=actor).delete()
    UseCase.objects.filter(demo_key=USE_CASE_DEMO_KEY).delete()
    ValueStream.objects.filter(demo_key=VALUE_STREAM_DEMO_KEY).delete()


def _status_counts(candidates: QuerySet[FieldAdoptionCandidate]) -> dict[str, int]:
    counts = Counter(candidates.values_list("status", flat=True))
    return {
        "direct_adopted": counts[FieldAdoptionCandidate.Status.ADOPTED],
        "edited_adopted": counts[FieldAdoptionCandidate.Status.ADOPTED_EDITED],
        "rejected": counts[FieldAdoptionCandidate.Status.REJECTED],
        "conflict": counts[FieldAdoptionCandidate.Status.CONFLICT],
        "superseded": counts[FieldAdoptionCandidate.Status.SUPERSEDED],
        "open": counts[FieldAdoptionCandidate.Status.OPEN],
    }


def _sum_cost(analyses: QuerySet[CaptureAnalysis]) -> Decimal:
    return sum(
        (analysis.cost or Decimal("0") for analysis in analyses),
        Decimal("0"),
    )


def _report(
    *,
    sessions: list[CaptureSession],
    review_ms: int,
    correction_ms: int,
) -> dict[str, object]:
    session_ids = [session.pk for session in sessions]
    candidates = FieldAdoptionCandidate.objects.filter(
        suggestion__analysis__session_id__in=session_ids
    )
    analyses = CaptureAnalysis.objects.filter(session_id__in=session_ids).order_by("pk")
    adopted_audits = FieldAdoptionAudit.objects.filter(
        session_id_snapshot__in=session_ids,
        outcome__in=[
            FieldAdoptionCandidate.Status.ADOPTED,
            FieldAdoptionCandidate.Status.ADOPTED_EDITED,
        ],
    )
    used_analysis_ids = list(
        adopted_audits.values_list("analysis_id_snapshot", flat=True).distinct()
    )
    used_analyses = analyses.filter(pk__in=used_analysis_ids)
    used_field_count = adopted_audits.count()
    all_cost = _sum_cost(analyses)
    used_cost = _sum_cost(used_analyses)
    cost_per_used_field = (
        used_cost / Decimal(used_field_count) if used_field_count else Decimal("0")
    )
    return {
        "marker": "[Real-DEMO]",
        "session_ids": [str(session_id) for session_id in session_ids],
        "candidate_counts": _status_counts(candidates),
        "review_time_ms": review_ms,
        "correction_time_ms": correction_ms,
        "provider_wait_time_ms": sum(analysis.duration_ms or 0 for analysis in analyses),
        "unique_analysis_runs": analyses.count(),
        "unique_used_analysis_runs": len(used_analysis_ids),
        "used_field_count": used_field_count,
        "all_analysis_cost": str(all_cost),
        "used_analysis_cost": str(used_cost),
        "cost_per_used_field": str(cost_per_used_field.quantize(Decimal("0.000001"))),
    }


@transaction.atomic
def run_block5_real_demo() -> dict[str, object]:
    actor, business_unit = _prepare_actor()
    _reset_demo_data(actor)

    value_stream = ValueStream.objects.create(
        demo_key=VALUE_STREAM_DEMO_KEY,
        name="[Real-DEMO] Beschaffung bis Bestellung",
        description="Angebote werden heute manuell zusammengeführt.",
        business_unit=business_unit,
        owner=actor,
        trigger="Ein freigegebener Bedarf liegt vor.",
        outcome="Die Bestellung ist nachvollziehbar ausgelöst.",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        status=ValueStream.Status.ACTIVE,
        created_by=actor,
    )
    use_case = UseCase.objects.create(
        demo_key=USE_CASE_DEMO_KEY,
        title="[Real-DEMO] KI-Assistenz Angebotsvergleich",
        summary="Angebote werden strukturiert verglichen.",
        problem_statement="Der manuelle Vergleich dauert zu lange.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        target_users="Einkauf",
        business_owner=actor,
        expected_benefit="Bearbeitungszeit reduzieren",
        submitter=actor,
    )
    use_case.classification.business_domain = BusinessDomain.PROCUREMENT
    use_case.classification.capability = "Sourcing und Angebotsvergleich"
    use_case.classification.process_area = "Beschaffung"
    use_case.classification.save(
        update_fields=["business_domain", "capability", "process_area", "updated_at"]
    )

    value_stream_session = _completed_session(
        actor=actor,
        target=value_stream,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    use_case_session = _completed_session(
        actor=actor,
        target=use_case,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    value_stream_analysis = _analysis(
        session=value_stream_session,
        actor=actor,
        source_hash="b" * 64,
        duration_ms=1300,
        cost=Decimal("0.003000"),
    )
    _suggestion(
        analysis=value_stream_analysis,
        field_name="description",
        value="Angebote werden automatisch strukturiert und vergleichbar dargestellt.",
    )
    _suggestion(
        analysis=value_stream_analysis,
        field_name="trigger",
        value="Ein fachlich geprüfter Bedarf liegt vor.",
    )
    _suggestion(
        analysis=value_stream_analysis,
        field_name="strategic_objective",
        value="Transparenz und Durchlaufzeit verbessern.",
    )
    value_stream_candidates = {
        candidate.target_field: candidate
        for candidate in create_adoption_candidates(analysis_id=value_stream_analysis.pk)
    }

    review_actions = [
        _timed(
            adopt_field_candidate,
            candidate_id=value_stream_candidates["description"].pk,
            actor=actor,
        ),
        _timed(
            reject_field_candidate,
            candidate_id=value_stream_candidates["trigger"].pk,
            actor=actor,
        ),
    ]

    replacement_analysis = _analysis(
        session=value_stream_session,
        actor=actor,
        source_hash="c" * 64,
        duration_ms=800,
        cost=Decimal("0.001000"),
    )
    _suggestion(
        analysis=replacement_analysis,
        field_name="strategic_objective",
        value="Durchlaufzeit messbar reduzieren und Transparenz erhöhen.",
    )
    replacement_candidate = create_adoption_candidates(analysis_id=replacement_analysis.pk)[0]
    review_actions.append(
        _timed(
            reject_field_candidate,
            candidate_id=replacement_candidate.pk,
            actor=actor,
        )
    )

    use_case_analysis = _analysis(
        session=use_case_session,
        actor=actor,
        source_hash="d" * 64,
        duration_ms=1100,
        cost=Decimal("0.002000"),
    )
    _suggestion(
        analysis=use_case_analysis,
        field_name="summary",
        value="KI strukturiert Angebote und unterstützt den nachvollziehbaren Vergleich.",
    )
    _suggestion(
        analysis=use_case_analysis,
        field_name="problem_statement",
        value="Unstrukturierte Angebote verursachen unnötige Vergleichszeit.",
    )
    use_case_candidates = {
        candidate.target_field: candidate
        for candidate in create_adoption_candidates(analysis_id=use_case_analysis.pk)
    }

    correction_action = _timed(
        adopt_field_candidate,
        candidate_id=use_case_candidates["summary"].pk,
        actor=actor,
        edited_value=(
            "KI strukturiert Angebote und unterstützt einen fachlich geprüften Vergleich."
        ),
    )
    use_case.problem_statement = "Der Einkauf hat das Problem zwischenzeitlich konkretisiert."
    use_case.save(update_fields=["problem_statement", "updated_at"])
    review_actions.append(
        _timed(
            adopt_field_candidate,
            candidate_id=use_case_candidates["problem_statement"].pk,
            actor=actor,
        )
    )

    return _report(
        sessions=[value_stream_session, use_case_session],
        review_ms=sum(action.elapsed_ms for action in review_actions),
        correction_ms=correction_action.elapsed_ms,
    )
