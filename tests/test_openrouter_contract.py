from __future__ import annotations

import json

import pytest
from django.conf import settings

from ki_radar.core.openrouter import OpenRouterUnavailable, request_openrouter


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

    assert error.code == "empty_response"
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
    assert "internal reasoning omitted from diagnostics" not in json.dumps(diagnostics)
