from __future__ import annotations

from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command

from ki_radar.accelerator.management.commands.probe_openrouter_reasoning import (
    PROBE_RESPONSE_FORMAT,
)
from ki_radar.core.openrouter import OpenRouterProbeResult


@pytest.mark.django_db
def test_reasoning_probe_compares_only_effort_with_same_transport(monkeypatch):
    monkeypatch.setattr(
        settings,
        "OPENROUTER_MODEL",
        "deepseek/deepseek-v4.1-flash",
        raising=False,
    )
    calls = []

    def fake_probe(**kwargs):
        calls.append(kwargs)
        effort = kwargs["reasoning_effort"]
        return OpenRouterProbeResult(
            content=(
                '{"recommendation":"hybrid","reason_1":"a","reason_2":"b",'
                '"reason_3":"c","human_escalation_required":true,'
                '"tested_llm_correct":21,"tested_llm_total":25}'
            ),
            model="deepseek/deepseek-v4.1-flash",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "reasoning_tokens": 20 if effort == "medium" else 5,
                "cost": 0.001,
            },
            finish_reason="stop",
            duration_seconds=10.0 if effort == "medium" else 4.0,
            headers_seconds=0.2,
            first_event_seconds=1.0,
            first_content_seconds=8.0 if effort == "medium" else 2.0,
            event_count=4,
            bytes_received=500,
            generation_id=f"gen-{effort}",
            request_id=f"req-{effort}",
        )

    monkeypatch.setattr(
        "ki_radar.accelerator.management.commands.probe_openrouter_reasoning."
        "probe_openrouter_stream",
        fake_probe,
    )
    out = StringIO()

    call_command(
        "probe_openrouter_reasoning",
        "--efforts",
        "medium,low",
        "--timeout",
        "210",
        "--max-tokens",
        "8192",
        stdout=out,
    )

    assert [item["reasoning_effort"] for item in calls] == ["medium", "low"]
    assert all(item["max_tokens"] == 8192 for item in calls)
    assert all(item["timeout_seconds"] == 210 for item in calls)
    assert calls[0]["messages"] == calls[1]["messages"]
    assert calls[0]["response_format"] == calls[1]["response_format"]
    assert calls[0]["response_format"] == PROBE_RESPONSE_FORMAT
    assert calls[0]["provider"] == calls[1]["provider"]
    assert calls[0]["temperature"] == calls[1]["temperature"] == 0.1

    output = out.getvalue()
    assert "## effort=medium" in output
    assert "## effort=low" in output
    assert "first_content_seconds=8.0" in output
    assert "first_content_seconds=2.0" in output
    assert "reasoning_tokens=20" in output
    assert "reasoning_tokens=5" in output
    assert "schema_result=" in output
