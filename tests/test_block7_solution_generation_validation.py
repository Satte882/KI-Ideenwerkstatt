import copy
import json
from unittest.mock import patch

import pytest
from django.test import override_settings

from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationError,
    generate_solution_preview,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.accelerator.solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.openrouter import OpenRouterResult

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "17",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "8000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "3000",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "5",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "20",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "2",
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


def statement(text, source_id):
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


def valid_payload():
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


def context_for(process):
    return build_solution_generation_source_context(process)


def provider_result(payload):
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={"prompt_tokens": 120, "completion_tokens": 350, "total_tokens": 470},
        output_chars=len(content),
        finish_reason="stop",
    )


@pytest.mark.django_db
def test_valid_bundle_is_normalized_against_current_source_context(owner, business_unit):
    process = make_process(owner, business_unit)

    validated = validate_solution_generation_payload(valid_payload(), context_for(process))

    assert tuple(validated["options"]) == OPTION_LANES
    assert validated["options"]["assistant"]["name"]["text"] == "Assistenzsystem"
    assert validated["options"]["assistant"]["name"]["source_ids"] == ["process.current_flow"]


@pytest.mark.django_db
def test_unknown_source_id_is_rejected(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    payload["options"]["assistant"]["risks"]["source_ids"] = ["process.fabricated"]

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, context_for(process))

    assert "Unbekannte Source-ID process.fabricated" in str(exc_info.value)


@pytest.mark.django_db
def test_fourth_lane_and_forbidden_assessment_field_are_rejected(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    payload["options"]["fourth_option"] = copy.deepcopy(payload["options"]["assistant"])
    payload["options"]["assistant"]["feasibility"] = statement(
        "Machbarkeit hoch",
        "process.systems",
    )

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, context_for(process))

    message = str(exc_info.value)
    assert "fourth_option" in message
    assert "feasibility" in message


@pytest.mark.django_db
def test_statement_without_source_assumption_or_open_evidence_is_rejected(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    target = payload["options"]["organizational"]["expected_value"]
    target["source_ids"] = []
    target["assumptions"] = []
    target["open_evidence"] = []

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, context_for(process))

    assert "Mindestens Quelle, Annahme oder offene Evidenz" in str(exc_info.value)


@pytest.mark.django_db
def test_unsupported_quantitative_claim_is_rejected_even_with_source(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    target = payload["options"]["assistant"]["expected_value"]
    target["text"] = "Verringert die Bearbeitungszeit um 20 %."
    target["source_ids"] = ["process.bottlenecks"]

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, context_for(process))

    assert "Nicht belegte quantitative Angabe" in str(exc_info.value)
    assert "20%" in str(exc_info.value)


@pytest.mark.django_db
def test_source_backed_quantitative_claim_is_allowed(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    target = payload["options"]["assistant"]["expected_value"]
    target["text"] = "Bezieht sich auf die dokumentierte Baseline von 11 Minuten."
    target["source_ids"] = ["process.baseline_metrics"]

    validated = validate_solution_generation_payload(payload, context_for(process))

    assert "11 Minuten" in validated["options"]["assistant"]["expected_value"]["text"]


@pytest.mark.django_db
def test_degenerate_options_with_only_different_names_are_rejected(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    organizational = payload["options"]["organizational"]
    rule_automation = payload["options"]["rule_automation"]
    for field_name in GENERATED_OPTION_FIELDS:
        if field_name != "name":
            rule_automation[field_name] = copy.deepcopy(organizational[field_name])

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, context_for(process))

    assert "inhaltlich identisch" in str(exc_info.value)


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_full_generation_persists_preview_only_after_complete_validation(owner, business_unit):
    process = make_process(owner, business_unit)
    original_status = process.status
    result = provider_result(valid_payload())

    with patch(
        "ki_radar.accelerator.solution_generation_service.request_openrouter",
        return_value=result,
    ) as request_mock:
        run = generate_solution_preview(actor=owner, process_analysis_id=process.pk)

    assert request_mock.call_count == 1
    assert run.status == SolutionGenerationRun.Status.SUCCESS
    assert run.finished_at is not None
    assert run.error_code == ""
    assert run.preview_payload["schema_version"] == GENERATION_SCHEMA_VERSION
    assert tuple(run.preview_payload["options"]) == OPTION_LANES
    assert run.preview_payload["edits"] == {}
    assert run.preview_payload["source_context"]["facts"]
    process.refresh_from_db()
    assert process.status == original_status
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_existing_manual_option_does_not_affect_generated_bundle_validation(owner, business_unit):
    process = make_process(owner, business_unit)
    SolutionOption.objects.create(
        process_analysis=process,
        name="Bereits vorhandene manuelle Option",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Manuell angelegte Alternative.",
        expected_value="Vergleichswert für die bestehende Auswahl.",
        created_by=owner,
    )

    with patch(
        "ki_radar.accelerator.solution_generation_service.request_openrouter",
        return_value=provider_result(valid_payload()),
    ):
        run = generate_solution_preview(actor=owner, process_analysis_id=process.pk)

    assert run.status == SolutionGenerationRun.Status.SUCCESS
    assert tuple(run.preview_payload["options"]) == OPTION_LANES
    assert SolutionOption.objects.filter(process_analysis=process).count() == 1


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_invalid_bundle_fails_without_preview_or_solution_options(owner, business_unit):
    process = make_process(owner, business_unit)
    payload = valid_payload()
    payload["options"]["assistant"]["risks"]["source_ids"] = ["process.fabricated"]

    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=provider_result(payload),
        ),
        pytest.raises(SolutionGenerationError) as exc_info,
    ):
        generate_solution_preview(actor=owner, process_analysis_id=process.pk)

    assert exc_info.value.code == "invalid_generation_payload"
    assert "Validierungsgrund:" in str(exc_info.value)
    assert "Unbekannte Source-ID process.fabricated" in str(exc_info.value)
    run = SolutionGenerationRun.objects.get(process_analysis=process)
    assert run.status == SolutionGenerationRun.Status.FAILED
    assert run.preview_payload == {}
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
