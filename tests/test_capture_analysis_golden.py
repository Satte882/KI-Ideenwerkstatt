import copy
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator import analysis_service
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
)
from ki_radar.accelerator.extraction_validation import execute_capture_analysis
from ki_radar.accelerator.models import (
    AcceleratorLLMQuota,
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "accelerator" / "real_demo_capture.v1.json"
CHECKSUM_PATH = FIXTURE_PATH.with_suffix(".sha256")
LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "50000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4000",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "90",
}
CORE_VALUE_STREAM_TERMS = (
    "LIEFERE",
    "Lieferant",
    "Onboarding",
    "Leistungserfassung",
    "RECHNUNGSPRÜFUNG",
    "BUCHEN",
    "BEZAHLEN",
)


def _dataset() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _case(name: str) -> dict:
    return next(case for case in _dataset()["cases"] if case["name"] == name)


def _completed_session(owner, case: dict) -> CaptureSession:
    catalog = get_capture_catalog(case["capture_type"], "1.0")
    missing = set(catalog.required_question_keys) - set(case["answers"])
    assert not missing, f"Golden fixture misses required answers: {sorted(missing)}"
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=case["capture_type"],
        working_title=case["working_title"],
        catalog_version=catalog.version,
        schema_version=catalog.schema_version,
        answers=case["answers"],
        status=CaptureSession.Status.COMPLETED,
        revision=7,
        answered_required_count=len(catalog.required_question_keys),
        required_question_count=len(catalog.required_question_keys),
        completed_at=now,
        expires_at=now + timedelta(days=90),
    )


def _provider_result(payload: object) -> OpenRouterResult:
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model=_dataset()["model"],
        usage={
            "prompt_tokens": 500,
            "completion_tokens": 250,
            "total_tokens": 750,
            "cost": "0.0042",
        },
        output_chars=len(content),
    )


def test_real_demo_fixture_checksum_prevents_silent_drift():
    expected = CHECKSUM_PATH.read_text(encoding="utf-8").split()[0]
    normalized = FIXTURE_PATH.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(normalized).hexdigest()

    assert actual == expected
    assert _dataset()["fixture_id"] == "[Real-DEMO]-einkaufsanforderung-v1"


@pytest.mark.django_db
@pytest.mark.parametrize("case_name", ["value_stream", "use_case"])
@override_settings(**LIMITS)
def test_real_demo_capture_analysis_golden_path(owner, monkeypatch, case_name):
    dataset = _dataset()
    case = _case(case_name)
    session = _completed_session(owner, case)
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: _provider_result(case["provider_payload"]),
    )

    analysis = execute_capture_analysis(actor=owner, session_id=session.pk)
    suggestions = list(analysis.suggestions.all())

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert analysis.source_revision == session.revision
    assert analysis.source_hash == analysis_service.canonical_answer_hash(case["answers"])
    assert analysis.catalog_version == session.catalog_version
    assert analysis.answer_schema_version == session.schema_version
    assert analysis.prompt_version == EXTRACTION_PROMPT_VERSION
    assert analysis.extraction_schema_version == EXTRACTION_SCHEMA_VERSION
    assert analysis.model_name == dataset["model"]
    assert len(suggestions) == len(case["provider_payload"]["suggestions"])
    assert all(
        suggestion.target_object_type in CaptureFieldSuggestion.TargetObjectType.values
        for suggestion in suggestions
    )
    assert all(suggestion.target_object_id is None for suggestion in suggestions)
    assert all(
        suggestion.source_excerpt.casefold()
        in case["answers"][suggestion.source_question].casefold()
        for suggestion in suggestions
    )

    if case_name == "value_stream":
        extracted_text = " ".join(
            f"{suggestion.suggested_value} {suggestion.source_excerpt}"
            for suggestion in suggestions
        ).casefold()
        assert all(term.casefold() in extracted_text for term in CORE_VALUE_STREAM_TERMS)


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_real_demo_invalid_json_fails_without_suggestions(owner, monkeypatch):
    session = _completed_session(owner, _case("value_stream"))
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: OpenRouterResult(
            content="kein-json",
            model=_dataset()["model"],
            usage={},
            output_chars=9,
        ),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get(session=session)
    assert exc_info.value.code == "invalid_response"
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert analysis.suggestions.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("failure_kind", ["schema", "evidence", "taxonomy"])
@override_settings(**LIMITS)
def test_real_demo_rejects_invalid_extractions(owner, monkeypatch, failure_kind):
    case = _case("value_stream")
    session = _completed_session(owner, case)
    payload = copy.deepcopy(case["provider_payload"])
    if failure_kind == "schema":
        payload.pop("prompt_version")
    elif failure_kind == "evidence":
        payload["suggestions"][0]["source_excerpt"] = "nicht belegte Behauptung"
    else:
        payload["suggestions"][0]["target_field"] = "value_stream.unbekannt"
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: _provider_result(payload),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get(session=session)
    assert exc_info.value.code == "invalid_extraction"
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert analysis.suggestions.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error_code",
    ["timeout", "provider_unavailable", "rate_limit", "response_too_large"],
)
@override_settings(**LIMITS)
def test_real_demo_provider_timeout_and_5xx_fail_without_retry(
    owner,
    monkeypatch,
    error_code,
):
    session = _completed_session(owner, _case("value_stream"))
    calls = 0

    def fail_provider(**kwargs):
        nonlocal calls
        calls += 1
        raise OpenRouterUnavailable("Providerfehler", code=error_code)

    monkeypatch.setattr(analysis_service, "request_openrouter", fail_provider)

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get(session=session)
    assert exc_info.value.code == error_code
    assert calls == 1
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert analysis.suggestions.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("scope", "setting_name", "error_code"),
    [
        ("context", "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT", "context_quota_exceeded"),
        ("user", "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY", "user_quota_exceeded"),
        ("global", "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY", "global_quota_exceeded"),
    ],
)
def test_real_demo_enforces_context_user_and_global_quota(
    owner,
    scope,
    setting_name,
    error_code,
):
    session = _completed_session(owner, _case("value_stream"))
    subject = {}
    if scope == AcceleratorLLMQuota.Scope.CONTEXT:
        subject["session"] = session
    elif scope == AcceleratorLLMQuota.Scope.USER:
        subject["user"] = owner
    AcceleratorLLMQuota.objects.create(
        scope=scope,
        quota_date=timezone.localdate(),
        calls=1,
        **subject,
    )
    configured = {**LIMITS}
    configured["ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT"] = "1"
    if scope in {AcceleratorLLMQuota.Scope.USER, AcceleratorLLMQuota.Scope.GLOBAL}:
        configured["ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY"] = "1"
    if scope == AcceleratorLLMQuota.Scope.GLOBAL:
        configured["ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY"] = "1"

    with (
        override_settings(**configured),
        pytest.raises(analysis_service.CaptureAnalysisQuotaExceeded) as exc_info,
    ):
        analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    assert exc_info.value.code == error_code
    assert CaptureAnalysis.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    **{
        **LIMITS,
        "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "1",
        "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "1",
        "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "1",
    }
)
def test_real_demo_daily_quotas_reset_on_new_local_date(owner):
    session = _completed_session(owner, _case("value_stream"))
    yesterday = timezone.localdate() - timedelta(days=1)
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        quota_date=yesterday,
        session=session,
        calls=1,
    )
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=yesterday,
        user=owner,
        calls=1,
    )
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.GLOBAL,
        quota_date=yesterday,
        calls=1,
    )

    analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    today_quotas = AcceleratorLLMQuota.objects.filter(quota_date=timezone.localdate())
    assert {quota.scope: quota.calls for quota in today_quotas} == {
        AcceleratorLLMQuota.Scope.CONTEXT: 1,
        AcceleratorLLMQuota.Scope.USER: 1,
        AcceleratorLLMQuota.Scope.GLOBAL: 1,
    }


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_real_demo_result_redisplay_is_idempotent_without_provider_call(
    owner,
    client,
    monkeypatch,
):
    case = _case("value_stream")
    session = _completed_session(owner, case)
    calls = 0

    def provider(**kwargs):
        nonlocal calls
        calls += 1
        return _provider_result(case["provider_payload"])

    monkeypatch.setattr(analysis_service, "request_openrouter", provider)
    analysis = execute_capture_analysis(actor=owner, session_id=session.pk)
    client.force_login(owner)

    for _index in range(2):
        response = client.get(
            reverse("accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk})
        )
        assert response.status_code == 200

    assert calls == 1
    assert CaptureAnalysis.objects.filter(pk=analysis.pk).count() == 1


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_real_demo_rejects_excessive_suggestion_count_atomically(owner, monkeypatch):
    case = _case("value_stream")
    session = _completed_session(owner, case)
    payload = copy.deepcopy(case["provider_payload"])
    base = payload["suggestions"][0]
    payload["suggestions"] = [
        {
            **base,
            "target_field": "value_stream.stages[].name",
            "target_object_type": "value_stream_stage",
            "target_group_key": f"phase-{index}",
            "source_question": "vs_stages",
            "source_excerpt": "LIEFERE",
            "suggested_value": f"Phase {index}",
        }
        for index in range(101)
    ]
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: _provider_result(payload),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get(session=session)
    assert exc_info.value.code == "invalid_extraction"
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert analysis.suggestions.count() == 0
