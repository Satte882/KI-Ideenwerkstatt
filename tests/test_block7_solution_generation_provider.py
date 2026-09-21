import json
from unittest.mock import patch

import pytest
from django.test import override_settings

from ki_radar.accelerator.models import AcceleratorLLMQuota, SolutionGenerationRun
from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationError,
    prepare_solution_generation_run,
    request_solution_generation_provider,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "8000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "700",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "5",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "20",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "30",
}


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="EU-Datenhaltung und menschliche Freigabe",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=2,
        name="Angebote vergleichen",
        description="Angebote fachlich vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manueller Vergleich",
        baseline_metrics="11 Minuten pro Vergleich",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell gegenübergestellt.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterienkatalog",
        business_rules="Vier-Augen-Prinzip bei Freigabe",
        handoffs="Einkauf übergibt an Fachbereich",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        exceptions="Fehlende Pflichtangaben werden nachgefordert.",
        baseline_metrics="11 Minuten pro Vergleich",
        target_state_principles="Nachvollziehbar und assistierend",
        analyzed_by=owner,
    )


def provider_result(*, content='{"options": {}}', finish_reason="stop"):
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={
            "prompt_tokens": 120,
            "completion_tokens": 80,
            "total_tokens": 200,
            "cost": "0.001234",
        },
        output_chars=len(content),
        finish_reason=finish_reason,
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_generation_uses_exactly_one_structured_openrouter_call(owner, business_unit):
    process = make_process(owner, business_unit)
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    with patch(
        "ki_radar.accelerator.solution_generation_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        provider_payload = request_solution_generation_provider(prepared)

    assert provider_payload.payload == {"options": {}}
    assert request_mock.call_count == 1
    kwargs = request_mock.call_args.kwargs
    assert kwargs["messages"] == prepared.messages
    assert kwargs["max_tokens"] == 8192
    assert kwargs["timeout_seconds"] == 17
    assert kwargs["temperature"] is None
    assert kwargs["provider"] == {"require_parameters": True}
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert set(kwargs["response_format"]["json_schema"]["schema"]["properties"]["options"])

    prepared.run.refresh_from_db()
    assert prepared.run.status == SolutionGenerationRun.Status.RUNNING
    assert prepared.run.input_chars == sum(len(item["content"]) for item in prepared.messages)
    assert prepared.run.model_name == "test/model"
    assert prepared.run.output_chars == len(provider_result().content)
    assert prepared.run.prompt_tokens == 120
    assert prepared.run.completion_tokens == 80
    assert prepared.run.total_tokens == 200
    assert str(prepared.run.cost) == "0.001234"
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
@override_settings(**{**VALID_LIMITS, "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100"})
def test_input_limit_blocks_before_run_and_quota(owner, business_unit):
    process = make_process(owner, business_unit)

    with pytest.raises(SolutionGenerationError) as exc_info:
        prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    assert exc_info.value.code == "input_too_large"
    assert not SolutionGenerationRun.objects.filter(process_analysis=process).exists()
    assert AcceleratorLLMQuota.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error_code",
    [
        "rate_limit",
        "provider_unavailable",
        "timeout",
        "not_configured",
        "provider_schema_unsupported",
    ],
)
@override_settings(**VALID_LIMITS)
def test_provider_failures_are_terminal_without_retry_or_options(
    owner,
    business_unit,
    error_code,
):
    process = make_process(owner, business_unit)
    original_flow = process.current_flow
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    failure = OpenRouterUnavailable("Providerfehler", code=error_code)
    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            side_effect=failure,
        ) as request_mock,
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        request_solution_generation_provider(prepared)

    assert exc_info.value.code == error_code
    assert request_mock.call_count == 1
    prepared.run.refresh_from_db()
    process.refresh_from_db()
    assert prepared.run.status == SolutionGenerationRun.Status.FAILED
    assert prepared.run.error_code == error_code
    assert process.current_flow == original_flow
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_output_truncation_is_terminal_and_records_provider_metadata(owner, business_unit):
    process = make_process(owner, business_unit)
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=provider_result(finish_reason="length"),
        ) as request_mock,
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        request_solution_generation_provider(prepared)

    assert exc_info.value.code == "output_truncated"
    assert request_mock.call_count == 1
    prepared.run.refresh_from_db()
    assert prepared.run.status == SolutionGenerationRun.Status.FAILED
    assert prepared.run.model_name == "test/model"
    assert prepared.run.total_tokens == 200
    assert not SolutionOption.objects.filter(process_analysis=process).exists()

    retry = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    assert retry.run.pk != prepared.run.pk
    assert retry.run.status == SolutionGenerationRun.Status.RUNNING


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_invalid_json_is_terminal_without_retry_or_partial_options(owner, business_unit):
    process = make_process(owner, business_unit)
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=provider_result(content="not-json"),
        ) as request_mock,
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        request_solution_generation_provider(prepared)

    assert exc_info.value.code == "invalid_response"
    assert request_mock.call_count == 1
    prepared.run.refresh_from_db()
    assert prepared.run.status == SolutionGenerationRun.Status.FAILED
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_non_object_json_is_terminal(owner, business_unit):
    process = make_process(owner, business_unit)
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    result = provider_result(content=json.dumps(["not", "an", "object"]))

    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=result,
        ),
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        request_solution_generation_provider(prepared)

    assert exc_info.value.code == "invalid_response"
    prepared.run.refresh_from_db()
    assert prepared.run.status == SolutionGenerationRun.Status.FAILED
