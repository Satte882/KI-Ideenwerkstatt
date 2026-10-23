"""Replay saved real answers through current services; never a new model-quality claim."""

import copy
import json
from pathlib import Path

import pytest
from django.test import override_settings
from test_evaluated_solution_workflow_initial_critic import VALID_LIMITS

from ki_radar.accelerator import (
    solution_critic_service,
    solution_generation_service,
    solution_repair_service,
)
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.core.openrouter import OpenRouterResult

EVIDENCE = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
@pytest.mark.parametrize("case", list("ABCD"))
def test_final_real_answers_reproduce_complete_automatic_correction(
    case, owner, business_unit, monkeypatch
):
    record = json.loads((EVIDENCE / f"{case}-solutions-v19.json").read_text(encoding="utf-8"))
    ledger = json.loads((EVIDENCE / "provider-ledger.json").read_text(encoding="utf-8"))["calls"]
    facts = record["solution_preview"]["source_context"]["facts"]
    by_id = {fact["source_id"]: fact["value"] for fact in facts}
    stream = ValueStream.objects.create(
        name="[SYNTHETIC #133] Replay",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        status="draft",
        constraints=by_id.get("value_stream.constraints", ""),
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream, sequence=1, name=by_id["stage.name"]
    )
    fields = {
        fact["field"]: fact["value"] for fact in facts if fact["source_id"].startswith("process.")
    }
    process = ProcessAnalysis.objects.create(
        stage=stage, analyzed_by=owner, status="draft", **fields
    )
    origin = {"A": 129, "B": 81, "C": 83, "D": 131}[case]
    answers = [next(call for call in ledger if call["call_id"] == origin)] + [
        call for call in ledger if call["case"] == case and call["call_id"] > 185
    ]
    observed = []

    def replay(**kwargs):
        answer = answers.pop(0)
        schema = kwargs["response_format"]["json_schema"]["name"]
        assert answer["status"] == "completed"
        assert schema == answer["schema"]
        observed.append(schema)
        if schema != "accelerator_solution_generation_v1":
            actual, expected = kwargs["messages"], answer["request"]["messages"]
            assert actual[0] == expected[0]
            actual_document = json.loads(actual[1]["content"])
            expected_document = json.loads(expected[1]["content"])
            # Only server snapshot identities differ in this isolated database.
            actual_document.pop("bound_input_hash", None)
            expected_document.pop("bound_input_hash", None)
            assert actual_document == expected_document
        return OpenRouterResult(
            content=answer["content"],
            model="saved-real-provider-answer",
            usage={},
            output_chars=len(answer["content"]),
            finish_reason=answer["finish_reason"],
        )

    for service in (solution_generation_service, solution_critic_service, solution_repair_service):
        monkeypatch.setattr(service, "request_openrouter", replay)
    # Replay the frozen v1 cohort; a saved response is never a fresh v2 answer.
    legacy_context = build_solution_generation_source_context(
        process, source_schema_version="block7_sources_v1"
    )
    monkeypatch.setattr(
        solution_generation_service, "require_solution_generation_ready", lambda _: legacy_context
    )
    monkeypatch.setattr(solution_generation_service, "GENERATION_SCHEMA_VERSION", "1.0")
    monkeypatch.setattr(solution_generation_service, "GENERATION_PROMPT_VERSION", "1.3")
    run = solution_generation_service.generate_solution_preview(
        actor=owner, process_analysis_id=process.pk
    )
    initial = solution_critic_service.run_initial_solution_critic(solution_generation_run_id=run.pk)
    assert initial.status == "success"
    if case != "B":
        assert initial.result_payload["findings"]
        repair = solution_repair_service.run_targeted_solution_repair(
            solution_generation_run_id=run.pk, actor=owner
        )
        assert repair.status == "success"
        final = solution_critic_service.run_final_solution_critic(solution_generation_run_id=run.pk)
        assert final.status == "success"
        assert final.result_payload["findings"] == []
    else:
        assert initial.result_payload["findings"] == []
    assert not answers
    assert len(observed) == (2 if case == "B" else 4)
    run.refresh_from_db()
    effective = build_validated_effective_solution_payload(run.preview_payload, legacy_context)
    expected = copy.deepcopy(record["solution_preview"]["options"])
    for patch in record["solution_preview"].get("machine_repair", {}).get("patches", []):
        expected[patch["option"]][patch["field"]] = patch["statement"]
    assert effective["options"] == expected
    assert process.confirmed_causes == ""
    assert process.status == "draft"
    assert not process.validations.exists()
    assert not record.get("technical_retry_of")
