from __future__ import annotations

import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_preview import (
    update_solution_generation_preview_edits,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import validate_solution_generation_payload
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_repair_contract import (
    SolutionRepairContractError,
    build_solution_repair_plan,
)
from ki_radar.accelerator.solution_repair_output import (
    SolutionRepairPayloadError,
    validate_solution_repair_payload,
)
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
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


def _make_process(owner, business_unit) -> ProcessAnalysis:
    stream = ValueStream.objects.create(
        name="Beschaffung Targeted Repair",
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


def _statement(text: str, source_id: str) -> dict[str, object]:
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


def _valid_generation_payload() -> dict[str, object]:
    options: dict[str, dict[str, object]] = {}
    for lane in OPTION_LANES:
        option: dict[str, object] = {}
        for field_name in GENERATED_OPTION_FIELDS:
            option[field_name] = _statement(
                f"{lane}: {field_name.replace('_', ' ')}",
                FIELD_SOURCES[field_name],
            )
        option["name"]["text"] = f"Option {lane}"
        options[lane] = option
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": options,
    }


def _make_generation_run(owner, business_unit) -> SolutionGenerationRun:
    process = _make_process(owner, business_unit)
    source_context = build_solution_generation_source_context(process)
    validated = validate_solution_generation_payload(_valid_generation_payload(), source_context)
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


def _critic_findings() -> list[dict[str, object]]:
    return [
        {
            "criterion": "bottleneck_fit",
            "option": "assistant",
            "field": "bottleneck_coverage",
            "finding": "Der Engpassbezug sollte für beide technischen Varianten präziser sein.",
            "source_ids": ["process.bottlenecks"],
            "repairable": True,
            "related_targets": [
                {
                    "option": "rule_automation",
                    "field": "bottleneck_coverage",
                }
            ],
        },
        {
            "criterion": "evidence_discipline",
            "option": "organizational",
            "field": "expected_value",
            "finding": "Diese Evidenzlücke bleibt manuell zu prüfen.",
            "source_ids": ["process.bottlenecks"],
            "repairable": False,
            "related_targets": [],
        },
    ]


def _make_initial_critic(run: SolutionGenerationRun) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    result_payload = validate_solution_critic_payload(
        {
            "schema_version": CRITIC_SCHEMA_VERSION,
            "prompt_version": CRITIC_PROMPT_VERSION,
            "findings": _critic_findings(),
        },
        source_context,
    )
    return SolutionQualityRun.objects.create(
        solution_generation_run=run,
        requested_by=run.requested_by,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        status=SolutionQualityRun.Status.SUCCESS,
        provider="openrouter",
        model_name="test/critic",
        prompt_version=CRITIC_PROMPT_VERSION,
        output_schema_version=CRITIC_SCHEMA_VERSION,
        input_hash=snapshot.snapshot_hash,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=timezone.now(),
        result_payload=result_payload,
    )


def _repair_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "prompt_version": REPAIR_PROMPT_VERSION,
        "patches": [
            {
                "option": "rule_automation",
                "field": "bottleneck_coverage",
                "statement": _statement(
                    "Regelbasierte Automatisierung reduziert die manuelle Übertragung im Engpass.",
                    "process.bottlenecks",
                ),
            },
            {
                "option": "assistant",
                "field": "bottleneck_coverage",
                "statement": _statement(
                    "Das Assistenzsystem unterstützt gezielt die manuelle Übertragung im Engpass.",
                    "process.bottlenecks",
                ),
            },
        ],
    }


def _provider_result(payload=None, *, finish_reason="stop") -> OpenRouterResult:
    body = json.dumps(payload or _repair_payload(), ensure_ascii=False)
    return OpenRouterResult(
        content=body,
        model="test/repair",
        usage={
            "prompt_tokens": 180,
            "completion_tokens": 110,
            "total_tokens": 290,
            "cost": "0.000456",
        },
        output_chars=len(body),
        finish_reason=finish_reason,
    )


def _plan_context(run: SolutionGenerationRun):
    critic = SolutionQualityRun.objects.get(
        solution_generation_run=run,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
    )
    plan = build_solution_repair_plan(
        generation_run=run,
        initial_critic_run=critic,
    )
    source_context = build_solution_generation_source_context(run.process_analysis)
    effective = build_validated_effective_solution_payload(run.preview_payload, source_context)
    return plan, source_context, effective


@pytest.mark.django_db
def test_repair_payload_requires_exact_bound_target_set(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    plan, source_context, effective = _plan_context(run)
    payload = _repair_payload()
    payload["patches"][0]["option"] = "organizational"

    with pytest.raises(SolutionRepairPayloadError) as exc_info:
        validate_solution_repair_payload(
            payload,
            plan=plan,
            effective_payload=effective,
            source_context=source_context,
        )

    assert "Nicht freigegebenes Repair-Ziel" in str(exc_info.value)
    assert "Repair-Ziel rule_automation.bottleneck_coverage fehlt" in str(exc_info.value)


@pytest.mark.django_db
def test_repair_payload_rejects_missing_and_duplicate_targets(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    plan, source_context, effective = _plan_context(run)
    payload = _repair_payload()
    payload["patches"][1] = copy.deepcopy(payload["patches"][0])

    with pytest.raises(SolutionRepairPayloadError) as exc_info:
        validate_solution_repair_payload(
            payload,
            plan=plan,
            effective_payload=effective,
            source_context=source_context,
        )

    assert "Doppeltes Repair-Ziel" in str(exc_info.value)
    assert "Repair-Ziel assistant.bottleneck_coverage fehlt" in str(exc_info.value)


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_targeted_repair_uses_one_provider_call_and_activates_only_bound_statements(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(),
    ) as request_mock:
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert request_mock.call_count == 1
    kwargs = request_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 4096
    assert kwargs["timeout_seconds"] == 17
    assert kwargs["temperature"] is None
    assert kwargs["provider"] == {"require_parameters": True}
    schema = kwargs["response_format"]["json_schema"]["schema"]
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert schema["properties"]["patches"]["minItems"] == 2
    assert schema["properties"]["patches"]["maxItems"] == 2

    run.refresh_from_db()
    repair_run.refresh_from_db()
    assert repair_run.status == SolutionQualityRun.Status.SUCCESS
    assert repair_run.step_type == SolutionQualityRun.StepType.REPAIR
    assert repair_run.model_name == "test/repair"
    assert repair_run.prompt_tokens == 180
    assert repair_run.completion_tokens == 110
    assert repair_run.total_tokens == 290
    assert str(repair_run.cost) == "0.000456"
    assert repair_run.input_chars > 0
    assert run.preview_payload["options"] == preview_before["options"]
    assert run.preview_payload["edits"] == preview_before["edits"]
    assert run.preview_payload["machine_repair"]["quality_run_id"] == str(repair_run.pk)
    assert run.preview_payload["machine_repair"]["input_hash"] == repair_run.input_hash
    assert repair_run.result_payload["input_hash"] == repair_run.input_hash
    assert repair_run.result_payload["output_snapshot_hash"] != repair_run.input_hash

    source_context = build_solution_generation_source_context(run.process_analysis)
    effective = build_validated_effective_solution_payload(run.preview_payload, source_context)
    assert (
        effective["options"]["rule_automation"]["bottleneck_coverage"]["text"]
        == "Regelbasierte Automatisierung reduziert die manuelle Übertragung im Engpass."
    )
    assert (
        effective["options"]["assistant"]["bottleneck_coverage"]["text"]
        == "Das Assistenzsystem unterstützt gezielt die manuelle Übertragung im Engpass."
    )
    assert effective["options"]["organizational"] == preview_before["options"]["organizational"]


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_repair_with_invalid_quantitative_claim_is_discarded_atomically(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)
    invalid_payload = _repair_payload()
    invalid_payload["patches"][1]["statement"]["text"] = (
        "Das Assistenzsystem reduziert den Engpass um 50%."
    )

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(invalid_payload),
    ) as request_mock:
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert repair_run.status == SolutionQualityRun.Status.FAILED
    assert repair_run.error_code == "invalid_repair_payload"
    assert run.preview_payload == preview_before
    assert "machine_repair" not in run.preview_payload


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_provider_failure_preserves_original_preview_and_consumes_one_shot(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        side_effect=OpenRouterUnavailable("Provider timeout", code="timeout"),
    ) as request_mock:
        failed = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "timeout"
    assert run.preview_payload == preview_before

    with (
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_provider_result(),
        ) as retry_mock,
        pytest.raises(SolutionRepairContractError) as exc_info,
    ):
        run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert exc_info.value.code == "repair_attempt_consumed"
    assert retry_mock.call_count == 0


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_human_edit_during_provider_call_wins_and_stale_repair_is_discarded(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)

    def provider_with_human_edit(**kwargs):
        del kwargs
        update_solution_generation_preview_edits(
            run_id=run.pk,
            edits={
                "organizational": {
                    "description": "Menschliche Änderung während des Repair-Aufrufs.",
                }
            },
        )
        return _provider_result()

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        side_effect=provider_with_human_edit,
    ) as request_mock:
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert repair_run.status == SolutionQualityRun.Status.FAILED
    assert repair_run.error_code == "repair_stale"
    assert "machine_repair" not in run.preview_payload
    assert (
        run.preview_payload["edits"]["organizational"]["description"]
        == "Menschliche Änderung während des Repair-Aufrufs."
    )


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_later_human_review_overrides_repaired_text_without_destroying_repair_provenance(
    owner,
    business_unit,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(),
    ):
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert repair_run.status == SolutionQualityRun.Status.SUCCESS
    update_solution_generation_preview_edits(
        run_id=run.pk,
        edits={
            "assistant": {
                "bottleneck_coverage": "Vom Menschen nach dem Repair final präzisiert.",
            }
        },
    )
    run.refresh_from_db()
    machine_repair_before = copy.deepcopy(run.preview_payload["machine_repair"])
    source_context = build_solution_generation_source_context(run.process_analysis)
    effective = build_validated_effective_solution_payload(run.preview_payload, source_context)

    assert (
        effective["options"]["assistant"]["bottleneck_coverage"]["text"]
        == "Vom Menschen nach dem Repair final präzisiert."
    )
    assert run.preview_payload["machine_repair"] == machine_repair_before


@pytest.mark.django_db
@override_settings(
    **{
        **VALID_LIMITS,
        "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS": "1",
    }
)
def test_repair_input_limit_fails_before_provider_and_preserves_preview(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(),
    ) as request_mock:
        failed = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 0
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "input_too_large"
    assert run.preview_payload == preview_before


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_repair_truncated_output_is_terminal_and_preserves_preview(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=_provider_result(finish_reason="length"),
    ) as request_mock:
        failed = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "output_truncated"
    assert run.preview_payload == preview_before
    assert "machine_repair" not in run.preview_payload

    with (
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_provider_result(),
        ) as retry_mock,
        pytest.raises(SolutionRepairContractError) as exc_info,
    ):
        run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert exc_info.value.code == "repair_attempt_consumed"
    assert retry_mock.call_count == 0


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
@pytest.mark.parametrize("content", ["{", "[]"])
def test_repair_invalid_response_is_terminal_and_preserves_preview(
    owner,
    business_unit,
    content,
):
    run = _make_generation_run(owner, business_unit)
    _make_initial_critic(run)
    preview_before = copy.deepcopy(run.preview_payload)
    invalid_result = OpenRouterResult(
        content=content,
        model="test/repair",
        usage={},
        output_chars=len(content),
        finish_reason="stop",
    )

    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=invalid_result,
    ) as request_mock:
        failed = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    run.refresh_from_db()
    assert request_mock.call_count == 1
    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.error_code == "invalid_response"
    assert run.preview_payload == preview_before
    assert "machine_repair" not in run.preview_payload

    with (
        patch(
            "ki_radar.accelerator.solution_repair_service.request_openrouter",
            return_value=_provider_result(),
        ) as retry_mock,
        pytest.raises(SolutionRepairContractError) as exc_info,
    ):
        run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert exc_info.value.code == "repair_attempt_consumed"
    assert retry_mock.call_count == 0
