import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator import analysis_service, extraction_validation
from ki_radar.accelerator.analysis_service import CaptureAnalysisError
from ki_radar.accelerator.candidate_snapshot import CandidateSnapshotError
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.extraction_validation import execute_capture_analysis
from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureSession,
    FieldAdoptionCandidate,
)
from ki_radar.core.openrouter import OpenRouterResult
from ki_radar.use_cases.models import UseCase

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "accelerator" / "real_demo_capture.v1.json"
LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "60",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "50000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS": "32768",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "90",
    "ACCELERATOR_FIELD_ADOPTION_ENABLED": True,
}


def _dataset() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _use_case_case() -> dict:
    return next(case for case in _dataset()["cases"] if case["name"] == "use_case")


def _bound_completed_session(*, owner, business_unit) -> CaptureSession:
    case = _use_case_case()
    catalog = get_capture_catalog("use_case", "1.0")
    target = UseCase.objects.create(
        title="[BENCHMARK] Leeres Accelerator-Ziel",
        problem_statement="Wird durch geprüfte Vorschläge ergänzt.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        business_owner=owner,
        expected_benefit="Wird im Review ergänzt.",
        submitter=owner,
    )
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title=case["working_title"],
        catalog_version=catalog.version,
        schema_version=catalog.schema_version,
        target_use_case=target,
        answers=case["answers"],
        status=CaptureSession.Status.COMPLETED,
        revision=1,
        answered_required_count=len(catalog.required_question_keys),
        required_question_count=len(catalog.required_question_keys),
        completed_at=now,
        expires_at=now + timedelta(days=90),
    )


def _provider_result() -> OpenRouterResult:
    payload = _use_case_case()["provider_payload"]
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model=_dataset()["model"],
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        output_chars=len(content),
        finish_reason="stop",
    )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_successful_bound_analysis_materializes_normal_review_candidates(
    owner,
    business_unit,
    monkeypatch,
):
    session = _bound_completed_session(owner=owner, business_unit=business_unit)
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: _provider_result(),
    )

    analysis = execute_capture_analysis(actor=owner, session_id=session.pk)

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    candidates = FieldAdoptionCandidate.objects.filter(
        suggestion__analysis=analysis
    ).select_related("suggestion")
    assert set(candidates.values_list("target_field", flat=True)) == {
        "title",
        "problem_statement",
        "intended_users",
        "data_sources",
        "expected_benefit",
        "human_oversight",
    }
    title_candidate = candidates.get(target_field="title")
    assert title_candidate.suggestion.target_field == "use_case.title"
    assert title_candidate.proposed_value == "KI-Assistenz Angebotsvergleich"
    assert not candidates.filter(target_field="metric.name").exists()


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_candidate_materialization_failure_rolls_back_suggestions_and_marks_analysis_failed(
    owner,
    business_unit,
    monkeypatch,
):
    session = _bound_completed_session(owner=owner, business_unit=business_unit)
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: _provider_result(),
    )

    def fail_candidate_creation(**kwargs):
        raise CandidateSnapshotError("snapshot failed")

    monkeypatch.setattr(
        extraction_validation,
        "create_adoption_candidates",
        fail_candidate_creation,
    )

    with pytest.raises(CaptureAnalysisError) as exc_info:
        execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get(session=session)
    assert exc_info.value.code == "candidate_snapshot_failed"
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert analysis.error_code == "candidate_snapshot_failed"
    assert analysis.suggestions.count() == 0
    assert FieldAdoptionCandidate.objects.count() == 0
