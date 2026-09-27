from __future__ import annotations

import json

import pytest
from django.conf import settings

from ki_radar.core.openrouter import (
    OpenRouterUnavailable,
    probe_openrouter_stream,
    request_openrouter,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit: int) -> bytes:
        return self._payload


def test_empty_response_keeps_content_free_provider_diagnostics(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(
        settings,
        "OPENROUTER_MODEL",
        "deepseek/deepseek-v4.1-flash",
        raising=False,
    )
    payload = {
        "model": "deepseek/deepseek-v4.1-flash",
        "usage": {
            "prompt_tokens": 2376,
            "completion_tokens": 4096,
            "total_tokens": 6472,
            "cost": 0.00042,
        },
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning": "internal reasoning omitted from diagnostics",
                    "reasoning_details": [{"type": "reasoning.text"}],
                    "refusal": None,
                },
            }
        ],
    }
    monkeypatch.setattr(
        "ki_radar.core.openrouter.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    with pytest.raises(OpenRouterUnavailable) as exc_info:
        request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=4096,
            timeout_seconds=60,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "test",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"status": {"type": "string"}},
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                },
            },
            provider={
                "order": ["deepinfra/fp8"],
                "allow_fallbacks": False,
                "require_parameters": True,
            },
            reasoning_effort="medium",
        )

    error = exc_info.value
    diagnostics = error.diagnostics

    assert error.code == "output_truncated"
    assert diagnostics["returned_model"] == "deepseek/deepseek-v4.1-flash"
    assert diagnostics["choices_count"] == 1
    assert diagnostics["finish_reason"] == "length"
    assert diagnostics["message_type"] == "dict"
    assert diagnostics["message_keys"] == [
        "content",
        "reasoning",
        "reasoning_details",
        "refusal",
        "role",
    ]
    assert diagnostics["content_type"] == "str"
    assert diagnostics["content_length"] == 0
    assert diagnostics["has_reasoning"] is True
    assert diagnostics["reasoning_type"] == "str"
    assert diagnostics["reasoning_length"] == len(payload["choices"][0]["message"]["reasoning"])
    assert diagnostics["has_reasoning_details"] is True
    assert diagnostics["reasoning_details_count"] == 1
    assert diagnostics["usage_prompt_tokens"] == 2376
    assert diagnostics["usage_completion_tokens"] == 4096
    assert diagnostics["usage_total_tokens"] == 6472
    assert diagnostics["usage_cost"] == 0.00042
    assert "internal reasoning omitted from diagnostics" not in json.dumps(diagnostics)


def test_productive_reasoning_effort_excludes_reasoning_from_response(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "OPENROUTER_REASONING_EXCLUDE", True, raising=False)
    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured["body"] = json.loads(request.data)
        return _FakeResponse({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})

    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", fake_urlopen)
    request_openrouter(
        messages=[{"role": "system", "content": "structured"}],
        max_tokens=8192,
        timeout_seconds=90,
        reasoning_effort="medium",
    )
    assert captured["body"]["reasoning"] == {"effort": "medium", "exclude": True}


def test_streamed_response_obeys_total_wall_clock_deadline(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    clock = {"now": 0.0}
    socket_timeouts = []

    class Socket:
        def settimeout(self, seconds):
            socket_timeouts.append(seconds)

    class Raw:
        _sock = Socket()

    class FP:
        raw = Raw()

    class SlowResponse:
        fp = FP()
        reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read1(self, _limit):
            self.reads += 1
            clock["now"] += 2.0
            return b" "

    response = SlowResponse()
    monkeypatch.setattr(
        "ki_radar.core.openrouter.urllib.request.urlopen",
        lambda *_args, **_kwargs: response,
    )
    monkeypatch.setattr("ki_radar.core.openrouter.time.monotonic", lambda: clock["now"])

    with pytest.raises(OpenRouterUnavailable) as exc_info:
        request_openrouter(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=8192,
            timeout_seconds=5,
        )

    assert exc_info.value.code == "timeout"
    assert response.reads == 3
    assert socket_timeouts == [5.0, 3.0, 1.0]


def test_stream_probe_measures_first_content_and_usage_without_exposing_reasoning(
    monkeypatch,
):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(
        settings,
        "OPENROUTER_MODEL",
        "deepseek/deepseek-v4.1-flash",
        raising=False,
    )
    monkeypatch.setattr(settings, "OPENROUTER_REASONING_EXCLUDE", True, raising=False)
    clock = {"now": 0.0}
    captured = {}

    class Headers:
        def get(self, name):
            return {
                "X-Generation-Id": "gen-header-1",
                "X-Request-Id": "req-1",
            }.get(name)

    class FakeStreamResponse:
        headers = Headers()
        fp = None

        def __init__(self):
            self.lines = iter(
                [
                    b'data: {"id":"gen-body-1","model":"deepseek/deepseek-v4.1-flash",'
                    b'"choices":[{"delta":{"content":""},"finish_reason":null}]}\n',
                    b'data: {"choices":[{"delta":{"content":"{\"recommendation\":'
                    b'\"hybrid\","},"finish_reason":null}]}\n',
                    b'data: {"choices":[{"delta":{"content":"\"reasons\":[\"a\",'
                    b'\"b\",\"c\"],\"human_escalation_required\":true,'
                    b'\"tested_llm_correct\":21,\"tested_llm_total\":25}"},'
                    b'"finish_reason":"stop"}]}\n',
                    b'data: {"choices":[],"usage":{"prompt_tokens":100,"completion_tokens":55,'
                    b'"total_tokens":155,"completion_tokens_details":{"reasoning_tokens":34}}}\n',
                    b"data: [DONE]\n",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            clock["now"] += 2.0
            return next(self.lines, b"")

    def fake_urlopen(request, **_kwargs):
        captured["body"] = json.loads(request.data)
        return FakeStreamResponse()

    monkeypatch.setattr(
        "ki_radar.core.openrouter.urllib.request.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr("ki_radar.core.openrouter.time.monotonic", lambda: clock["now"])

    result = probe_openrouter_stream(
        messages=[{"role": "user", "content": "probe"}],
        max_tokens=8192,
        timeout_seconds=30,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "probe",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        provider={
            "order": ["deepinfra/fp8"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        reasoning_effort="low",
    )

    assert captured["body"]["stream"] is True
    assert captured["body"]["stream_options"] == {"include_usage": True}
    assert captured["body"]["reasoning"] == {"effort": "low", "exclude": True}
    assert captured["body"]["provider"]["order"] == ["deepinfra/fp8"]
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert result.first_event_seconds == 2.0
    assert result.first_content_seconds == 4.0
    assert result.duration_seconds == 10.0
    assert result.event_count == 4
    assert result.generation_id == "gen-header-1"
    assert result.request_id == "req-1"
    assert result.usage["prompt_tokens"] == 100
    assert result.usage["completion_tokens"] == 55
    assert result.usage["reasoning_tokens"] == 34
    assert "reasoning" not in result.content


def test_stream_probe_timeout_reports_transport_progress(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key", raising=False)
    clock = {"now": 0.0}

    class Headers:
        def get(self, _name):
            return ""

    class SlowStreamResponse:
        headers = Headers()
        fp = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            clock["now"] += 6.0
            return b": keepalive\n"

    monkeypatch.setattr(
        "ki_radar.core.openrouter.urllib.request.urlopen",
        lambda *_args, **_kwargs: SlowStreamResponse(),
    )
    monkeypatch.setattr("ki_radar.core.openrouter.time.monotonic", lambda: clock["now"])

    with pytest.raises(OpenRouterUnavailable) as exc_info:
        probe_openrouter_stream(
            messages=[{"role": "user", "content": "probe"}],
            max_tokens=8192,
            timeout_seconds=5,
            response_format={"type": "json_object"},
            provider={"order": ["deepinfra/fp8"]},
            reasoning_effort="medium",
        )

    error = exc_info.value
    assert error.code == "timeout"
    assert error.diagnostics["probe_stage"] == "stream"
    assert error.diagnostics["headers_seconds"] == 0.0
    assert error.diagnostics["first_event_seconds"] is None
    assert error.diagnostics["first_content_seconds"] is None
    assert error.diagnostics["bytes_received"] > 0
    assert error.diagnostics["reasoning_effort"] == "medium"
