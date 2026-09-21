from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings

from ki_radar.accelerator.solution_generation_contract import SOLUTION_GENERATION_SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]


def test_block7_default_budget_and_local_compose_forwarding_are_aligned():
    base_settings = (ROOT / "config" / "settings" / "base.py").read_text(encoding="utf-8")
    compose = (ROOT / "compose.local.yml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert '"ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS",\n    "16384"' in base_settings
    assert (
        "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS: "
        "${ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS:-16384}"
    ) in compose
    assert "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS=16384" in env_example
    assert "ACCELERATOR_LLM_TIMEOUT_SECONDS: ${ACCELERATOR_LLM_TIMEOUT_SECONDS:-60}" in compose


def test_block7_prompt_explicitly_caps_verbosity_without_dropping_comparison_fields():
    assert "pro Feld höchstens drei kurze Sätze" in SOLUTION_GENERATION_SYSTEM_PROMPT
    assert "höchstens zwei kurze Einträge" in SOLUTION_GENERATION_SYSTEM_PROMPT


@override_settings(
    ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS="16384",
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_MODEL="test/model",
    OPENROUTER_API_URL="https://openrouter.ai/api/v1/chat/completions",
    OPENROUTER_MAX_RESPONSE_BYTES="8000000",
    OPENROUTER_REASONING_EXCLUDE=True,
)
def test_runtime_policy_command_exposes_effective_solution_generation_and_provider_config():
    output = StringIO()

    call_command("show_accelerator_llm_policy", stdout=output)

    rendered = output.getvalue()
    assert "solution_generation_max_output_tokens=16384" in rendered
    assert "openrouter_api_key_configured=yes" in rendered
    assert "openrouter_model=test/model" in rendered
    assert "openrouter_api_url=https://openrouter.ai/api/v1/chat/completions" in rendered
    assert "capture_max_output_tokens=32768" in rendered
    assert "max_response_bytes=8000000" in rendered
    assert "reasoning_response_excluded=yes" in rendered
    assert "test-key" not in rendered
