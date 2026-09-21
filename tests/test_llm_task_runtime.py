import json
import logging
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from ki_radar.core import llm_tasks, openrouter
from ki_radar.core.llm_policy import LLMConfigurationError, get_llm_task_policy
from ki_radar.core.models import LLMTaskQuota, LLMTaskRun
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

SOURCE_HASH = "a" * 64
TASK_SETTINGS = {
    "LLM_TASK_TIMEOUT_SECONDS": "60",
    "LLM_TASK_TEMPERATURE": "0.1",
    "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY": "3",
    "LLM_TASK_MAX_CALLS_PER_USER_DAY": "20",
    "LLM_TASK_MAX_CALLS_GLOBAL_DAY": "100",
    "LLM_TASK_RUN_RETENTION_DAYS": "90",
    "LLM_DELIVERY_FIELD_DRAFT_MAX_INPUT_CHARS": "12000",
    "LLM_DELIVERY_FIELD_DRAFT_MAX_OUTPUT_TOKENS": "16384",
    "LLM_DELIVERY_FIELD_DRAFT_REASONING_EFFORT": "low",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_INPUT_CHARS": "16000",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_MAX_OUTPUT_TOKENS": "4096",
    "LLM_ORIGIN_CONSISTENCY_REVIEW_REASONING_EFFORT": "medium",
}


class FakeResponse:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1) -> bytes:
        encoded = json.dumps(self.payload).encode("utf-8")
        return encoded[:size] if size >= 0 else encoded


def _messages(text: str = "grounded context") -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Return strict JSON."},
        {"role": "user", "content": text},
    ]


def _prepare_delivery(owner, **overrides):
    values = {
        "task_type": LLMTaskRun.TaskType.DELIVERY_FIELD_DRAFT,
        "actor": owner,
        "object_type": "delivery_package",
        "object_id": "11111111-1111-1111-1111-111111111111",
        "field_key": "mvp_scope",
        "source_hash": SOURCE_HASH,
        "prompt_version": "1.0",
        "schema_version": "1.0",
        "messages": _messages(),
    }
    values.update(overrides)
    return llm_tasks.prepare_llm_task(**values)


def _prepare_consistency(owner, **overrides):
    values = {
        "task_type": LLMTaskRun.TaskType.ORIGIN_CONSISTENCY_REVIEW,
        "actor": owner,
        "object_type": "use_case",
        "object_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "source_hash": "b" * 64,
        "prompt_version": "1.0",
        "schema_version": "1.0",
        "messages": _messages(),
    }
    values.update(overrides)
    return llm_tasks.prepare_llm_task(**values)


@override_settings(**TASK_SETTINGS)
def test_first_wave_task_policies_are_explicit_and_separate():
    delivery = get_llm_task_policy(LLMTaskRun.TaskType.DELIVERY_FIELD_DRAFT)
    consistency = get_llm_task_policy(LLMTaskRun.TaskType.ORIGIN_CONSISTENCY_REVIEW)

    assert delivery.max_input_chars == 12000
    assert delivery.max_output_tokens == 16384
    assert delivery.reasoning_effort == "low"
    assert consistency.max_input_chars == 16000
    assert consistency.max_output_tokens == 4096
    assert consistency.reasoning_effort == "medium"
    assert delivery.max_calls_per_context_day == 3
    assert delivery.max_calls_per_user_day == 20
    assert delivery.max_calls_global_day == 100
    assert delivery.run_retention_days == 90


@override_settings(**TASK_SETTINGS)
def test_unknown_task_type_fails_closed():
    with pytest.raises(LLMConfigurationError, match="Unbekannter LLM-Task"):
        get_llm_task_policy("generic_chat")


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    OPENROUTER_REASONING_EXCLUDE=True,
)
def test_openrouter_combines_reasoning_effort_and_exclusion(monkeypatch):
    captured = {}
    payload = {
        "model": "test/model",
        "choices": [
            {
                "message": {"content": '{"ok":true}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {},
    }

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(payload)

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    openrouter.request_openrouter(
        messages=_messages(),
        max_tokens=100,
        timeout_seconds=5,
        response_format={"type": "json_schema"},
        provider={
            "zdr": True,
            "data_collection": "deny",
            "require_parameters": True,
        },
        reasoning_effort="low",
    )

    assert captured["body"]["reasoning"] == {"effort": "low", "exclude": True}
    assert captured["body"]["provider"] == {
        "zdr": True,
        "data_collection": "deny",
        "require_parameters": True,
    }


@pytest.mark.django_db
@override_settings(**TASK_SETTINGS)
def test_prepare_task_reserves_context_user_global_quota_without_content(owner):
    prepared = _prepare_delivery(owner)

    run = prepared.run
    assert run.task_type == LLMTaskRun.TaskType.DELIVERY_FIELD_DRAFT
    assert run.field_key == "mvp_scope"
    assert run.source_hash == SOURCE_HASH
    assert run.input_chars == sum(len(item["content"]) for item in _messages())
    assert run.expires_at > timezone.now() + timedelta(days=89)

    quotas = LLMTaskQuota.objects.order_by("scope")
    assert quotas.count() == 3
    assert all(quota.calls == 1 for quota in quotas)

    field_names = {field.name for field in LLMTaskRun._meta.fields}
    assert not {
        "prompt",
        "messages",
        "domain_content",
        "raw_response",
        "draft_text",
        "findings",
    }.intersection(field_names)


@pytest.mark.django_db
@override_settings(
    **{
        **TASK_SETTINGS,
        "LLM_DELIVERY_FIELD_DRAFT_MAX_INPUT_CHARS": "10",
    }
)
def test_oversized_input_fails_before_run_or_quota(owner):
    with pytest.raises(llm_tasks.LLMTaskError) as exc_info:
        _prepare_delivery(owner, messages=_messages("x" * 50))

    assert exc_info.value.code == "input_too_large"
    assert LLMTaskRun.objects.count() == 0
    assert LLMTaskQuota.objects.count() == 0


@pytest.mark.django_db
@override_settings(**TASK_SETTINGS)
def test_runtime_forwards_privacy_reasoning_and_records_only_metadata(
    owner,
    monkeypatch,
    caplog,
):
    captured = {}
    sensitive_input = "SEHR-VERTRAULICHER-INPUT"
    sensitive_output = "SEHR-VERTRAULICHER-OUTPUT"
    result = OpenRouterResult(
        content=f'{{"draft_text":"{sensitive_output}"}}',
        model="provider/model",
        usage={
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "cost": 0.001,
        },
        output_chars=32,
        finish_reason="stop",
    )

    def fake_request_openrouter(**kwargs):
        captured.update(kwargs)
        return result

    monkeypatch.setattr(llm_tasks, "request_openrouter", fake_request_openrouter)
    caplog.set_level(logging.INFO, logger="ki_radar.core.llm_tasks")
    prepared = _prepare_delivery(owner, messages=_messages(sensitive_input))

    returned = llm_tasks.request_llm_task_provider(
        prepared,
        response_format={"type": "json_schema", "json_schema": {"strict": True}},
    )

    assert returned is result
    assert captured["reasoning_effort"] == "low"
    assert captured["provider"] == llm_tasks.FIRST_WAVE_PROVIDER_POLICY
    assert captured["max_tokens"] == 16384
    assert captured["timeout_seconds"] == 60
    assert captured["temperature"] == 0.1

    prepared.run.refresh_from_db()
    assert prepared.run.status == LLMTaskRun.Status.RUNNING
    assert prepared.run.model_name == "provider/model"
    assert prepared.run.total_tokens == 15
    assert not hasattr(prepared.run, "content")

    llm_tasks.mark_llm_task_success(run_id=prepared.run.pk)
    prepared.run.refresh_from_db()
    assert prepared.run.status == LLMTaskRun.Status.SUCCESS
    assert sensitive_input not in caplog.text
    assert sensitive_output not in caplog.text


@pytest.mark.django_db
@override_settings(**TASK_SETTINGS)
def test_provider_error_fails_run_without_retry(owner, monkeypatch):
    calls = 0

    def fail_provider(**kwargs):
        nonlocal calls
        calls += 1
        raise OpenRouterUnavailable("timeout", code="timeout")

    monkeypatch.setattr(llm_tasks, "request_openrouter", fail_provider)
    prepared = _prepare_delivery(owner)

    with pytest.raises(llm_tasks.LLMTaskError) as exc_info:
        llm_tasks.request_llm_task_provider(
            prepared,
            response_format={"type": "json_schema"},
        )

    assert exc_info.value.code == "timeout"
    assert calls == 1
    prepared.run.refresh_from_db()
    assert prepared.run.status == LLMTaskRun.Status.FAILED
    assert prepared.run.error_code == "timeout"


@pytest.mark.django_db
@override_settings(**TASK_SETTINGS)
def test_fourth_context_call_is_blocked_atomically(owner):
    for _index in range(3):
        _prepare_delivery(owner)

    with pytest.raises(llm_tasks.LLMTaskQuotaExceeded) as exc_info:
        _prepare_delivery(owner)

    assert exc_info.value.code == "context_quota_exceeded"
    assert LLMTaskRun.objects.count() == 3
    context = LLMTaskQuota.objects.get(scope=LLMTaskQuota.Scope.CONTEXT)
    user = LLMTaskQuota.objects.get(scope=LLMTaskQuota.Scope.USER)
    global_quota = LLMTaskQuota.objects.get(scope=LLMTaskQuota.Scope.GLOBAL)
    assert context.calls == user.calls == global_quota.calls == 3


@pytest.mark.django_db
@override_settings(
    **{
        **TASK_SETTINGS,
        "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY": "2",
        "LLM_TASK_MAX_CALLS_PER_USER_DAY": "2",
    }
)
def test_user_quota_is_shared_across_first_wave_tasks(owner):
    _prepare_delivery(owner)
    _prepare_consistency(owner)

    with pytest.raises(llm_tasks.LLMTaskQuotaExceeded) as exc_info:
        _prepare_delivery(
            owner,
            object_id="44444444-4444-4444-4444-444444444444",
        )

    assert exc_info.value.code == "user_quota_exceeded"
    assert LLMTaskRun.objects.count() == 2
    assert LLMTaskQuota.objects.get(scope=LLMTaskQuota.Scope.USER).calls == 2


@pytest.mark.django_db
@override_settings(
    **{
        **TASK_SETTINGS,
        "LLM_TASK_MAX_CALLS_PER_CONTEXT_DAY": "2",
        "LLM_TASK_MAX_CALLS_PER_USER_DAY": "2",
        "LLM_TASK_MAX_CALLS_GLOBAL_DAY": "2",
    }
)
def test_global_quota_is_shared_across_users(owner, other_owner):
    _prepare_delivery(owner)
    _prepare_consistency(other_owner)

    with pytest.raises(llm_tasks.LLMTaskQuotaExceeded) as exc_info:
        _prepare_delivery(
            owner,
            object_id="55555555-5555-5555-5555-555555555555",
        )

    assert exc_info.value.code == "global_quota_exceeded"
    assert LLMTaskRun.objects.count() == 2
    assert LLMTaskQuota.objects.get(scope=LLMTaskQuota.Scope.GLOBAL).calls == 2


@pytest.mark.django_db
@override_settings(**TASK_SETTINGS)
def test_cleanup_command_removes_only_expired_llm_task_runs(owner):
    expired = _prepare_delivery(
        owner,
        object_id="22222222-2222-2222-2222-222222222222",
    ).run
    current = _prepare_delivery(
        owner,
        object_id="33333333-3333-3333-3333-333333333333",
    ).run
    LLMTaskRun.objects.filter(pk=expired.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    call_command("cleanup_expired_llm_task_runs")

    assert not LLMTaskRun.objects.filter(pk=expired.pk).exists()
    assert LLMTaskRun.objects.filter(pk=current.pk).exists()
