import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import (
    AcceleratorLLMQuota,
    SolutionGenerationRun,
    SolutionQualityRun,
)
from ki_radar.accelerator.solution_critic_service import run_initial_solution_critic
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import validate_solution_generation_payload
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "4096",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "5",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "20",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "4",
    "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS": "100000",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "30",
}

FIELD_SOURCES = {
    "name": "process.current_flow",
    "description": "process.current_flow",
    "expected_value": "process.bottlenecks",
    "bottleneck_coverage": "process.bottlenecks",
    "data_requirements": "process.data_objects",
    "application_impact": "process.systems",
    "integration_impact": "process.systems",
    "technology_constraints": "value_stream.constraints",
    "risks": "process.exceptions",
    "architecture_fit": "process.target_state_principles",
}

LANE_LABELS = {
    "organizational": "Organisatorischer Ansatz",
    "rule_automation": "Regelbasierte Automatisierung",
    "assistant": "Assistenzsystem",
}


def make_process(owner, business_unit) -> ProcessAnalysis:
    stream = ValueStream.objects.create(
        name="Beschaffung Critic",
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


def statement(text: str, source_id: str) -> dict[str, object]:
    return {
        "text": text,
        "source_ids": [source_id],
        "assumptions": [],
        "open_evidence": [],
        "uncertainty": {
            "level": "low",
            "reason": "Direkt aus der angegebenen Quelle abgeleitet.",
        },
    }


def valid_generation_payload() -> dict[str, object]:
    options = {}
    for lane in OPTION_LANES:
        label = LANE_LABELS[lane]
        option = {}
        for field_name in GENERATED_OPTION_FIELDS:
            option[field_name] = statement(
                f"{label}: {field_name.replace('_', ' ')}",
                FIELD_SOURCES[field_name],
            )
        option["name"]["text"] = label
        options[lane] = option
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": options,
    }


def make_generation_run(owner, business_unit) -> SolutionGenerationRun:
    process = make_process(owner, business_unit)
    source_context = build_solution_generation_source_context(process)
    validated = validate_solution_generation_payload(valid_generation_payload(), source_context)
    preview_payload = {
        "schema_version": validated["schema_version"],
        "prompt_version": validated["prompt_version"],
        "source_context": source_context.provider_payload(),
        "options": validated["options"],
        "edits": {},
    }
    return SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=source_context.process_version,
        source_hash=source_context.source_hash,
        requested_by=owner,
        status=SolutionGenerationRun.Status.SUCCESS,
        provider="openrouter",
        model_name="test/generator",
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=timezone.now(),
        preview_payload=preview_payload,
        expires_at=timezone.now() + timedelta(days=30),
    )


def critic_payload() -> dict[str, object]:
    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "findings": [
            {
                "criterion": "bottleneck_fit",
                "option": "assistant",
                "finding": "Der Engpassbezug sollte fachlich präziser beschrieben werden.",
                "source_ids": ["process.bottlenecks"],
                "repairable": False,
                "related_targets": [],
            }
        ],
    }


def provider_result(payload=None, *, finish_reason="stop") -> OpenRouterResult:
    body = json.dumps(payload or critic_payload(), ensure_ascii=False)
    return OpenRouterResult(
        content=body,
        model="test/critic",
        usage={
            "prompt_tokens": 150,
            "completion_tokens": 90,
            "total_tokens": 240,
            "cost": "0.000321",
        },
        output_chars=len(body),
        finish_reason=finish_reason,
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_initial_critic_uses_one_structured_provider_call_and_persists_findings(
    owner,
    business_unit,
):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        quality_run = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert request_mock.call_count == 1
    kwargs = request_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 4096
    assert kwargs["timeout_seconds"] == 17
    assert kwargs["temperature"] is None
    assert kwargs["provider"] == {"require_parameters": True}
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    source_id_enum = kwargs["response_format"]["json_schema"]["schema"]["properties"]["findings"][
        "items"
    ]["properties"]["source_ids"]["items"]["enum"]
    assert source_id_enum == sorted(
        fact["source_id"] for fact in generation_run.preview_payload["source_context"]["facts"]
    )

    quality_run.refresh_from_db()
    generation_run.refresh_from_db()
    assert quality_run.status == SolutionQualityRun.Status.SUCCESS
    assert quality_run.step_type == SolutionQualityRun.StepType.INITIAL_CRITIC
    assert quality_run.prompt_version == CRITIC_PROMPT_VERSION
    assert quality_run.output_schema_version == CRITIC_SCHEMA_VERSION
    assert quality_run.model_name == "test/critic"
    assert quality_run.prompt_tokens == 150
    assert quality_run.completion_tokens == 90
    assert quality_run.total_tokens == 240
    assert str(quality_run.cost) == "0.000321"
    finding = quality_run.result_payload["findings"][0]
    assert finding["finding_id"].startswith("finding_")
    assert finding["criterion"] == "bottleneck_fit"
    assert generation_run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_initial_critic_is_one_shot_before_a_second_provider_call(owner, business_unit):
    generation_run = make_generation_run(owner, business_unit)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        first = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)
        second = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert request_mock.call_count == 1
    assert first.pk == second.pk
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=generation_run,
            step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        ).count()
        == 1
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_provider_failure_preserves_valid_generation_preview_and_consumes_attempt(
    owner,
    business_unit,
):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        side_effect=OpenRouterUnavailable("Provider timeout", code="timeout"),
    ) as request_mock:
        failed = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    generation_run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "timeout"
    assert generation_run.status == SolutionGenerationRun.Status.SUCCESS
    assert generation_run.preview_payload == preview_before

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as retry_mock:
        repeated = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_user_quota_failure_rolls_back_partial_quota_and_preserves_preview(owner, business_unit):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)
    AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.USER,
        quota_date=timezone.localdate(),
        user=owner,
        calls=5,
    )

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        failed = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    generation_run.refresh_from_db()
    assert request_mock.call_count == 0
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "user_quota_exceeded"
    assert generation_run.preview_payload == preview_before
    assert not AcceleratorLLMQuota.objects.filter(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        process_analysis=generation_run.process_analysis,
    ).exists()
    user_quota = AcceleratorLLMQuota.objects.get(
        scope=AcceleratorLLMQuota.Scope.USER,
        user=owner,
    )
    assert user_quota.calls == 5


@pytest.mark.django_db
@override_settings(
    **{
        **VALID_LIMITS,
        "ACCELERATOR_LLM_MAX_INPUT_CHARS": "1",
        "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS": "100000",
    }
)
def test_initial_critic_uses_its_dedicated_validated_snapshot_limit(owner, business_unit):
    generation_run = make_generation_run(owner, business_unit)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        quality_run = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert request_mock.call_count == 1
    assert quality_run.status == SolutionQualityRun.Status.SUCCESS


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_invalid_critic_contract_is_terminal_without_touching_preview(owner, business_unit):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)
    invalid_payload = critic_payload()
    invalid_payload["findings"][0]["source_ids"] = ["process.fabricated"]

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(invalid_payload),
    ):
        failed = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    generation_run.refresh_from_db()
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "invalid_critic_payload"
    assert failed.model_name == "test/critic"
    assert failed.total_tokens == 240
    assert generation_run.preview_payload == preview_before


@pytest.mark.django_db(transaction=True)
@override_settings(**VALID_LIMITS)
def test_successful_generation_persistence_schedules_initial_critic(owner, business_unit):
    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as request_mock:
        generation_run = make_generation_run(owner, business_unit)

    assert request_mock.call_count == 1
    quality_run = SolutionQualityRun.objects.get(
        solution_generation_run=generation_run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )
    assert generation_run.status == SolutionGenerationRun.Status.SUCCESS
    assert quality_run.status == SolutionQualityRun.Status.SUCCESS


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_initial_critic_truncated_output_is_terminal_and_preserves_preview(owner, business_unit):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(finish_reason="length"),
    ) as request_mock:
        failed = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    generation_run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "output_truncated"
    assert generation_run.preview_payload == preview_before

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as retry_mock:
        repeated = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
@pytest.mark.parametrize("content", ["{", "[]"])
def test_initial_critic_invalid_response_is_terminal_and_preserves_preview(
    owner,
    business_unit,
    content,
):
    generation_run = make_generation_run(owner, business_unit)
    preview_before = copy.deepcopy(generation_run.preview_payload)
    invalid_result = OpenRouterResult(
        content=content,
        model="test/critic",
        usage={},
        output_chars=len(content),
        finish_reason="stop",
    )

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=invalid_result,
    ) as request_mock:
        failed = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    generation_run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "invalid_response"
    assert generation_run.preview_payload == preview_before

    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(),
    ) as retry_mock:
        repeated = run_initial_solution_critic(solution_generation_run_id=generation_run.pk)

    assert retry_mock.call_count == 0
    assert repeated.pk == failed.pk
    assert repeated.status == SolutionQualityRun.Status.FAILED
