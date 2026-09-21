import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import override_settings

from ki_radar.core import openrouter
from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.use_cases import copilot

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "5000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "400",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
}


class FakeResponse:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1) -> bytes:
        if isinstance(self.payload, bytes):
            return self.payload[:size] if size >= 0 else self.payload
        encoded = json.dumps(self.payload).encode("utf-8")
        return encoded[:size] if size >= 0 else encoded


def _use_case():
    return SimpleNamespace(pk="use-case-1")


def _success_payload(content: str = "Konsistenz\nPlausibel") -> dict:
    return {
        "model": "provider/returned-model",
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "cost": 0.001,
        },
    }


@override_settings(**VALID_LIMITS)
def test_policy_parses_valid_settings():
    policy = get_accelerator_llm_policy()

    assert policy.timeout_seconds == 15
    assert policy.max_input_chars == 5000
    assert policy.max_output_tokens == 400
    assert policy.max_calls_per_context == 3
    assert policy.solution_critic_max_input_chars == 100000


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("ACCELERATOR_LLM_TIMEOUT_SECONDS", "nicht-numerisch", "ganze Zahl"),
        ("ACCELERATOR_LLM_MAX_INPUT_CHARS", "0", "zwischen"),
        ("ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS", "100001", "zwischen"),
        ("ACCELERATOR_LLM_MAX_OUTPUT_TOKENS", "5000", "zwischen"),
    ],
)
def test_policy_rejects_invalid_numeric_settings(setting, value, message):
    configured = {**VALID_LIMITS, setting: value}

    with override_settings(**configured), pytest.raises(LLMConfigurationError, match=message):
        get_accelerator_llm_policy()


def test_policy_rejects_inconsistent_request_limits():
    configured = {
        **VALID_LIMITS,
        "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "21",
        "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    }

    with (
        override_settings(**configured),
        pytest.raises(
            LLMConfigurationError,
            match="nutzerbezogene Tagesgrenze",
        ),
    ):
        get_accelerator_llm_policy()


@override_settings(OPENROUTER_API_KEY="", **VALID_LIMITS)
def test_copilot_requires_api_key(monkeypatch):
    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"secret": "unused"})

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "not_configured"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **{**VALID_LIMITS, "ACCELERATOR_LLM_MAX_INPUT_CHARS": "10"},
)
def test_copilot_rejects_oversized_input_without_network_call(monkeypatch):
    calls = 0

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(_success_payload())

    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"text": "vertraulich"})
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "input_too_large"
    assert calls == 0


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    OPENROUTER_MODEL="test/model",
    **VALID_LIMITS,
)
def test_copilot_uses_shared_timeout_output_limit_and_returned_model(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(_success_payload())

    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"problem": "klar"})
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    result = copilot.analyze_use_case(_use_case())

    assert result == "Konsistenz\nPlausibel"
    assert captured["timeout"] == 15
    assert captured["body"]["max_tokens"] == 400
    assert captured["body"]["model"] == "test/model"
    assert captured["body"]["reasoning"] == {"exclude": True}
    assert "provider" not in captured["body"]
    assert "response_format" not in captured["body"]


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_copilot_classifies_rate_limit(monkeypatch):
    http_error = openrouter.urllib.error.HTTPError(
        "https://openrouter.example/v1/chat/completions",
        429,
        "Too Many Requests",
        {},
        None,
    )

    def raise_rate_limit(*args, **kwargs):
        raise http_error

    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"problem": "klar"})
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", raise_rate_limit)

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "rate_limit"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_copilot_does_not_retry_after_timeout(monkeypatch):
    calls = 0

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"problem": "klar"})
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "timeout"
    assert calls == 1


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_copilot_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"problem": "klar"})
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"{"),
    )

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "invalid_response"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_copilot_rejects_empty_response(monkeypatch):
    monkeypatch.setattr(copilot, "_payload_for_use_case", lambda use_case: {"problem": "klar"})
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(_success_payload("   ")),
    )

    with pytest.raises(copilot.CopilotUnavailable) as exc_info:
        copilot.analyze_use_case(_use_case())

    assert exc_info.value.code == "empty_response"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    OPENROUTER_MAX_RESPONSE_BYTES="1000000",
    **VALID_LIMITS,
)
def test_transport_rejects_oversized_raw_response(monkeypatch):
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"x" * 1_000_001),
    )

    with pytest.raises(openrouter.OpenRouterUnavailable) as exc_info:
        openrouter.request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10,
            timeout_seconds=5,
        )

    assert exc_info.value.code == "response_too_large"


@override_settings(OPENROUTER_MAX_RESPONSE_BYTES="999999")
def test_transport_rejects_unsafe_response_limit():
    with pytest.raises(openrouter.OpenRouterUnavailable) as exc_info:
        openrouter.max_response_bytes()

    assert exc_info.value.code == "invalid_configuration"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="http://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_requires_https_without_network_call(monkeypatch):
    calls = 0

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(openrouter.OpenRouterUnavailable) as exc_info:
        openrouter.request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10,
            timeout_seconds=5,
        )

    assert exc_info.value.code == "invalid_configuration"
    assert calls == 0


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_copilot_logs_metadata_without_prompt_or_raw_content(monkeypatch, caplog):
    sensitive_content = "SEHR-VERTRAULICHER-INHALT"
    monkeypatch.setattr(
        copilot,
        "_payload_for_use_case",
        lambda use_case: {"problem": sensitive_content},
    )
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(_success_payload("Antwort ohne Rohdaten")),
    )
    caplog.set_level(logging.INFO, logger="ki_radar.use_cases.copilot")

    copilot.analyze_use_case(_use_case())

    log_text = caplog.text
    assert "status=success" in log_text
    assert "total_tokens=30" in log_text
    assert sensitive_content not in log_text
    assert "Antwort ohne Rohdaten" not in log_text


def test_copilot_submit_guard_is_loaded_and_prevents_second_submit():
    repository_root = Path(__file__).resolve().parents[1]
    base_template = (repository_root / "templates" / "base.html").read_text(encoding="utf-8")
    guard_script = (repository_root / "static" / "js" / "copilot-submit-guard.js").read_text(
        encoding="utf-8"
    )

    assert "js/copilot-submit-guard.js" in base_template
    assert 'form[action$="/copilot/"]' in guard_script
    assert 'form.dataset.submitted === "true"' in guard_script
    assert 'button.setAttribute("aria-busy", "true")' in guard_script
    assert "Analyse läuft …" in guard_script


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_forwards_structured_output_requirements_and_finish_reason(monkeypatch):
    captured = {}
    payload = _success_payload('{"schema_version":"1.0"}')
    payload["choices"][0]["finish_reason"] = "stop"

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(payload)

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    result = openrouter.request_openrouter(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
        timeout_seconds=5,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "test", "strict": True, "schema": {"type": "object"}},
        },
        provider={"require_parameters": True},
    )

    assert captured["body"]["provider"] == {"require_parameters": True}
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert result.finish_reason == "stop"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_omits_optional_temperature(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(_success_payload('{"schema_version":"1.0"}'))

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)

    openrouter.request_openrouter(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
        timeout_seconds=5,
        temperature=None,
        response_format={"type": "json_schema"},
        provider={"require_parameters": True},
    )

    assert "temperature" not in captured["body"]
    assert captured["body"]["max_tokens"] == 100
    assert captured["body"]["response_format"] == {"type": "json_schema"}
    assert captured["body"]["provider"] == {"require_parameters": True}


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_accepts_text_content_blocks(monkeypatch):
    payload = _success_payload()
    payload["choices"][0]["message"]["content"] = [
        {"type": "text", "text": '{"schema_version":"1.0"}'},
    ]
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    result = openrouter.request_openrouter(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
        timeout_seconds=5,
    )

    assert result.content == '{"schema_version":"1.0"}'


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_classifies_missing_schema_provider(monkeypatch):
    error_payload = {
        "error": {
            "code": 503,
            "message": "No endpoints found that support the requested parameters.",
            "metadata": {"error_type": "no_available_provider"},
        }
    }
    http_error = openrouter.urllib.error.HTTPError(
        "https://openrouter.example/v1/chat/completions",
        503,
        "Service Unavailable",
        {},
        io.BytesIO(json.dumps(error_payload).encode("utf-8")),
    )

    def raise_schema_error(*args, **kwargs):
        raise http_error

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", raise_schema_error)

    with pytest.raises(openrouter.OpenRouterUnavailable) as exc_info:
        openrouter.request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            timeout_seconds=5,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "test",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            provider={"require_parameters": True},
        )

    assert exc_info.value.code == "provider_schema_unsupported"


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.example/v1/chat/completions",
    **VALID_LIMITS,
)
def test_transport_classifies_provider_invalid_json_schema(monkeypatch):
    error_payload = {
        "error": {
            "code": 400,
            "message": "Provider returned error",
            "metadata": {
                "provider_error_code": "invalid_json_schema",
                "raw": "Invalid schema for response_format",
            },
        }
    }
    http_error = openrouter.urllib.error.HTTPError(
        "https://openrouter.example/v1/chat/completions",
        400,
        "Bad Request",
        {},
        io.BytesIO(json.dumps(error_payload).encode("utf-8")),
    )
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(http_error),
    )

    with pytest.raises(openrouter.OpenRouterUnavailable) as exc_info:
        openrouter.request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            timeout_seconds=5,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "test",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            provider={"require_parameters": True},
        )

    assert exc_info.value.code == "provider_schema_unsupported"
