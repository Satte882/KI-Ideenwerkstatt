import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator import analysis_service
from ki_radar.accelerator.catalogs import CURRENT_CATALOG_VERSIONS, get_capture_catalog
from ki_radar.accelerator.models import AcceleratorLLMQuota, CaptureAnalysis, CaptureSession
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "50000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "700",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
}


def _completed_session(owner, capture_type=CaptureSession.CaptureType.VALUE_STREAM):
    catalog = get_capture_catalog(capture_type, "1.0")
    answers = {question.key: f"Antwort für {question.key}" for question in catalog.questions}
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=capture_type,
        catalog_version="1.0",
        schema_version="1.0",
        answers=answers,
        status=CaptureSession.Status.COMPLETED,
        revision=4,
        completed_at=now,
        expires_at=now + timedelta(days=90),
    )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_prepare_uses_frozen_catalog_and_minimized_input(owner, monkeypatch):
    session = _completed_session(owner)
    session.answers["vs_open_questions"] = ""
    session.save(update_fields=["answers", "updated_at"])
    monkeypatch.setitem(CURRENT_CATALOG_VERSIONS, "value_stream", "9.9")

    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    payload = json.loads(prepared.messages[1]["content"])

    assert prepared.catalog.version == "1.0"
    assert prepared.analysis.catalog_version == "1.0"
    assert prepared.analysis.source_revision == 4
    assert all(question["id"] != "vs_open_questions" for question in payload["questions"])
    assert "owner" not in payload
    assert "email" not in prepared.messages[1]["content"]


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_prepare_rejects_non_completed_session_without_consuming_quota(owner):
    session = _completed_session(owner)
    session.status = CaptureSession.Status.DRAFT
    session.save(update_fields=["status", "updated_at"])

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    assert exc_info.value.code == "invalid_capture_state"
    assert AcceleratorLLMQuota.objects.count() == 0
    assert CaptureAnalysis.objects.count() == 0


@pytest.mark.django_db
@override_settings(**{**LIMITS, "ACCELERATOR_LLM_MAX_INPUT_CHARS": "20"})
def test_input_limit_is_checked_before_quota_reservation(owner):
    session = _completed_session(owner)

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    assert exc_info.value.code == "input_too_large"
    assert AcceleratorLLMQuota.objects.count() == 0


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_prepare_reserves_context_user_and_global_quota(owner):
    session = _completed_session(owner)

    analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    quotas = {quota.scope: quota.calls for quota in AcceleratorLLMQuota.objects.all()}
    assert quotas == {"context": 1, "user": 1, "global": 1}


@pytest.mark.django_db
@override_settings(**{**LIMITS, "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "1"})
def test_context_quota_rejects_second_source_after_first_call(owner):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    analysis_service.mark_capture_analysis_failed(
        analysis_id=prepared.analysis.pk,
        error_code="provider_unavailable",
    )
    session.revision += 1
    session.answers["vs_context"] = "Geänderter Kontext"
    session.save(update_fields=["revision", "answers", "updated_at"])

    with pytest.raises(analysis_service.CaptureAnalysisQuotaExceeded) as exc_info:
        analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    assert exc_info.value.code == "context_quota_exceeded"
    assert AcceleratorLLMQuota.objects.get(scope="context").calls == 1


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_same_source_cannot_start_twice_in_parallel(owner):
    session = _completed_session(owner)
    analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    with pytest.raises(analysis_service.CaptureAnalysisAlreadyRunning) as exc_info:
        analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    assert exc_info.value.code == "analysis_already_running"
    assert CaptureAnalysis.objects.filter(status="running").count() == 1


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_provider_failure_marks_analysis_failed_without_retry(owner, monkeypatch):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    calls = 0

    def fail_provider(**kwargs):
        nonlocal calls
        calls += 1
        raise OpenRouterUnavailable("Nicht erreichbar", code="provider_unavailable")

    monkeypatch.setattr(analysis_service, "request_openrouter", fail_provider)

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.request_capture_provider(prepared)

    prepared.analysis.refresh_from_db()
    assert exc_info.value.code == "provider_unavailable"
    assert calls == 1
    assert prepared.analysis.status == CaptureAnalysis.Status.FAILED
    assert prepared.analysis.finished_at is not None


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_provider_payload_is_json_object_and_metadata_is_returned(owner, monkeypatch):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    response = {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "suggestions": [],
        "open_questions": [],
        "contradictions": [],
    }

    captured = {}

    def fake_request_openrouter(**kwargs):
        captured.update(kwargs)
        return OpenRouterResult(
            content=json.dumps(response),
            model="test/model",
            usage={"total_tokens": 12, "cost": 0.001},
            output_chars=100,
            finish_reason="stop",
        )

    monkeypatch.setattr(analysis_service, "request_openrouter", fake_request_openrouter)

    provider = analysis_service.request_capture_provider(prepared)

    assert provider.payload == response
    assert provider.result.model == "test/model"
    assert captured["provider"] == {"require_parameters": True}
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert (
        captured["response_format"]["json_schema"]["schema"]["properties"]["schema_version"][
            "const"
        ]
        == "1.0"
    )
    assert prepared.analysis.status == CaptureAnalysis.Status.RUNNING


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_invalid_provider_json_marks_analysis_failed(owner, monkeypatch):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: OpenRouterResult(
            content="kein-json",
            model="test/model",
            usage={},
            output_chars=9,
        ),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.request_capture_provider(prepared)

    prepared.analysis.refresh_from_db()
    assert exc_info.value.code == "invalid_response"
    assert prepared.analysis.status == CaptureAnalysis.Status.FAILED
    assert prepared.analysis.model_name == "test/model"


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_truncated_provider_output_has_explicit_error_code(owner, monkeypatch):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: OpenRouterResult(
            content='{"schema_version":"1.0"',
            model="test/model",
            usage={"completion_tokens": 700},
            output_chars=23,
            finish_reason="length",
        ),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.request_capture_provider(prepared)

    prepared.analysis.refresh_from_db()
    assert exc_info.value.code == "output_truncated"
    assert prepared.analysis.error_code == "output_truncated"
    assert prepared.analysis.status == CaptureAnalysis.Status.FAILED
    assert prepared.analysis.completion_tokens == 700


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_schema_provider_error_is_preserved_on_analysis(owner, monkeypatch):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    def fail_provider(**kwargs):
        raise OpenRouterUnavailable(
            "Kein kompatibler Provider",
            code="provider_schema_unsupported",
        )

    monkeypatch.setattr(analysis_service, "request_openrouter", fail_provider)

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        analysis_service.request_capture_provider(prepared)

    prepared.analysis.refresh_from_db()
    assert exc_info.value.code == "provider_schema_unsupported"
    assert prepared.analysis.error_code == "provider_schema_unsupported"
    assert prepared.analysis.status == CaptureAnalysis.Status.FAILED
