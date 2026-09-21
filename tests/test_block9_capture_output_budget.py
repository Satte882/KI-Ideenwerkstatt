from types import SimpleNamespace

import pytest
from django.test import override_settings

from ki_radar.accelerator import analysis_service
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult


@override_settings(
    ACCELERATOR_LLM_MAX_OUTPUT_TOKENS="4096",
    ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS="32768",
    ACCELERATOR_CAPTURE_TEMPERATURE="",
)
def test_capture_has_dedicated_32768_output_budget_without_widening_shared_limit():
    policy = get_accelerator_llm_policy()

    assert policy.max_output_tokens == 4096
    assert policy.capture_max_output_tokens == 32768
    assert policy.capture_temperature is None


@override_settings(ACCELERATOR_CAPTURE_TEMPERATURE="0.0")
def test_capture_temperature_can_be_configured_explicitly():
    assert get_accelerator_llm_policy().capture_temperature == 0.0


@pytest.mark.parametrize("value", ["invalid", "-0.1", "2.1"])
def test_capture_temperature_rejects_invalid_values(settings, value):
    settings.ACCELERATOR_CAPTURE_TEMPERATURE = value

    with pytest.raises(LLMConfigurationError, match="ACCELERATOR_CAPTURE_TEMPERATURE"):
        get_accelerator_llm_policy()


@override_settings(ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS="32769")
def test_capture_output_budget_remains_hard_bounded():
    with pytest.raises(LLMConfigurationError, match="zwischen 1 und 32768"):
        get_accelerator_llm_policy()


def test_capture_provider_forwards_dedicated_output_budget(monkeypatch):
    captured = {}
    catalog = get_capture_catalog("use_case", "1.0")
    prepared = SimpleNamespace(
        catalog=catalog,
        messages=[{"role": "user", "content": "benchmark"}],
        policy=SimpleNamespace(
            capture_max_output_tokens=32768,
            capture_temperature=None,
            timeout_seconds=60,
        ),
    )

    def fake_request_openrouter(**kwargs):
        captured.update(kwargs)
        return OpenRouterResult(
            content="{}",
            model="test/model",
            usage={},
            output_chars=2,
            finish_reason="stop",
        )

    monkeypatch.setattr(analysis_service, "request_openrouter", fake_request_openrouter)

    result = analysis_service.request_capture_provider(prepared)

    assert result.payload == {}
    assert captured["max_tokens"] == 32768
    assert captured["timeout_seconds"] == 60
    assert captured["temperature"] is None
    assert captured["response_format"]["type"] == "json_schema"
