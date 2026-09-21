import json
from unittest.mock import patch

import pytest

from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accelerator.solution_generation_contract import (
    EXPECTED_VALUE_RULE,
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
    QUANTITATIVE_GROUNDING_RULE,
    SOLUTION_GENERATION_SYSTEM_PROMPT,
    build_solution_generation_messages,
)
from ki_radar.accelerator.solution_generation_service import generate_solution_preview
from ki_radar.accelerator.solution_generation_sources import require_solution_generation_ready
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

QUALITATIVE_EXPECTED_VALUES = {
    "organizational": "Vereinheitlicht die Bearbeitung und reduziert unnötige Abstimmungsschritte.",
    "rule_automation": "Reduziert manuelle Übertragungsarbeit durch regelbasierte Verarbeitung.",
    "assistant": (
        "Die dokumentierte Ausgangslage liegt bei 11 Minuten pro Vergleich; der mögliche Nutzen "
        "wird mangels belegter Zielgröße qualitativ als Entlastung bei der Gegenüberstellung "
        "beschrieben."
    ),
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


def provider_result(payload):
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={"prompt_tokens": 120, "completion_tokens": 350, "total_tokens": 470},
        output_chars=len(content),
        finish_reason="stop",
    )


def add_manual_option(process, owner):
    return SolutionOption.objects.create(
        process_analysis=process,
        name="Bereits vorhandene manuelle Option",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Manuell angelegte Alternative.",
        expected_value="Vergleichswert für die bestehende Auswahl.",
        created_by=owner,
    )


@pytest.mark.django_db
def test_baseline_metrics_reach_provider_and_prompt_matches_fail_closed_numeric_contract(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)

    context = require_solution_generation_ready(process)
    baseline_fact = next(
        fact.as_dict() for fact in context.facts if fact.source_id == "process.baseline_metrics"
    )
    messages = build_solution_generation_messages(context)
    generation_input = json.loads(messages[1]["content"])

    assert baseline_fact == {
        "source_id": "process.baseline_metrics",
        "field": "baseline_metrics",
        "value": "11 Minuten pro Vergleich",
    }
    assert baseline_fact in generation_input["untrusted_source_data"]["facts"]
    assert generation_input["generation_rules"]["quantitative_grounding"] == (
        QUANTITATIVE_GROUNDING_RULE
    )
    assert generation_input["generation_rules"]["expected_value"] == EXPECTED_VALUE_RULE
    assert QUANTITATIVE_GROUNDING_RULE in SOLUTION_GENERATION_SYSTEM_PROMPT
    assert EXPECTED_VALUE_RULE in SOLUTION_GENERATION_SYSTEM_PROMPT
    assert GENERATION_PROMPT_VERSION == "1.2"


@pytest.mark.django_db
def test_reported_unbacked_expected_value_numbers_remain_fail_closed_with_existing_option(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    add_manual_option(process, owner)
    payload = valid_payload()
    payload["options"]["organizational"]["expected_value"] = statement(
        "Eine Standardisierung reduziert die Bearbeitungszeit um 20%.",
        "process.baseline_metrics",
    )
    payload["options"]["rule_automation"]["expected_value"] = statement(
        "Regelbasierte Automatisierung spart 4 Minuten und 30% Aufwand.",
        "process.baseline_metrics",
    )
    payload["options"]["assistant"]["expected_value"] = statement(
        "Assistenz reduziert den manuellen Aufwand um 30%.",
        "process.baseline_metrics",
    )

    with pytest.raises(SolutionGenerationContractError) as exc_info:
        validate_solution_generation_payload(payload, require_solution_generation_ready(process))

    message = str(exc_info.value)
    assert "$.options.organizational.expected_value.text" in message
    assert "20%" in message
    assert "$.options.rule_automation.expected_value.text" in message
    assert "4" in message
    assert "30%" in message
    assert "$.options.assistant.expected_value.text" in message
    assert SolutionOption.objects.filter(process_analysis=process).count() == 1


@pytest.mark.django_db
def test_same_existing_option_case_succeeds_with_prompt_compliant_expected_values(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    add_manual_option(process, owner)
    payload = valid_payload()

    payload["options"]["organizational"]["expected_value"] = statement(
        QUALITATIVE_EXPECTED_VALUES["organizational"],
        "process.bottlenecks",
    )
    payload["options"]["rule_automation"]["expected_value"] = statement(
        QUALITATIVE_EXPECTED_VALUES["rule_automation"],
        "process.bottlenecks",
    )
    payload["options"]["assistant"]["expected_value"] = statement(
        QUALITATIVE_EXPECTED_VALUES["assistant"],
        "process.baseline_metrics",
    )

    with patch(
        "ki_radar.accelerator.solution_generation_service.request_openrouter",
        return_value=provider_result(payload),
    ) as provider_mock:
        run = generate_solution_preview(actor=owner, process_analysis_id=process.pk)

    assert provider_mock.call_count == 1
    assert run.status == SolutionGenerationRun.Status.SUCCESS
    actual_expected_values = {
        lane: run.preview_payload["options"][lane]["expected_value"]["text"]
        for lane in OPTION_LANES
    }
    assert actual_expected_values == QUALITATIVE_EXPECTED_VALUES
    assert any(
        fact["source_id"] == "process.baseline_metrics"
        and fact["value"] == "11 Minuten pro Vergleich"
        for fact in run.preview_payload["source_context"]["facts"]
    )
    assert SolutionOption.objects.filter(process_analysis=process).count() == 1
