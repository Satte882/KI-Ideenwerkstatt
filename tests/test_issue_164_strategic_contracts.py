"""Version boundary and synthetic capture-to-draft regression; no model calls."""

import copy
import hashlib
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.analysis_service import canonical_answer_hash
from ki_radar.accelerator.architect_contract import (
    DISCOVERY_SCHEMA_VERSION_V2,
    DiscoveryContractError,
    build_discovery_json_schema,
    validate_discovery_payload,
)
from ki_radar.accelerator.architect_service import execute_autonomous_business_discovery
from ki_radar.accelerator.catalogs import (
    CaptureAnswerValidationError,
    get_capture_catalog,
    validate_answer_document,
)
from ki_radar.accelerator.extraction_validation import execute_capture_analysis
from ki_radar.accelerator.investigation_models import InvestigationRun
from ki_radar.accelerator.investigation_runtime import (
    StartInvestigationRequest,
    recover_investigation,
    start_investigation,
)
from ki_radar.accelerator.models import (
    SolutionGenerationRun,
)
from ki_radar.accelerator.services import (
    complete_capture_session,
    create_capture_session,
    save_capture_session,
)
from ki_radar.accelerator.solution_critic_service import (
    _source_context_from_generation_run,
    run_final_solution_critic,
    run_initial_solution_critic,
)
from ki_radar.accelerator.solution_generation_adoption import (
    SolutionGenerationAdoptionError,
    adopt_solution_generation_bundle,
)
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    OPTION_LANES,
    build_solution_generation_json_schema,
    build_solution_generation_messages,
)
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_preview import build_solution_generation_preview_state
from ki_radar.accelerator.solution_generation_service import generate_solution_preview
from ki_radar.accelerator.solution_generation_sources import (
    LEGACY_SOURCE_SCHEMA_VERSION,
    SOURCE_SCHEMA_VERSION,
    SolutionGenerationSourceContext,
    SourceFact,
    _source_hash,
    build_solution_generation_source_context,
    source_version_for_run,
)
from ki_radar.accelerator.solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_repair_contract import build_solution_repair_plan
from ki_radar.accelerator.solution_repair_service import run_targeted_solution_repair
from ki_radar.accelerator.structured_adoption_orchestrator import commit_structured_batch
from ki_radar.accelerator.structured_process_adoption import (
    StructuredProcessError,
    _validate_process_values,
)
from ki_radar.accelerator.structured_review import (
    StructuredReviewAction,
    decide_review_item,
    get_or_create_review_batch,
)
from ki_radar.architecture.discovery_materialization import (
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.investigation_adoption import adopt_investigation_drafts
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, SolutionSelectionDecision
from ki_radar.use_cases.outcome_contract import set_discovery_path
from tests.test_block7_solution_generation_sources import make_process
from tests.test_block7_solution_generation_validation import VALID_LIMITS, provider_result
from tests.test_evaluated_solution_workflow_targeted_repair import (
    VALID_LIMITS as QUALITY_LIMITS,
)
from tests.test_evaluated_solution_workflow_targeted_repair import (
    _critic_findings,
    _repair_payload,
)
from tests.test_issue_3_investigation_runtime import snapshot_for_root
from tests.test_issue_98_autonomous_business_discovery import (
    _draft,
    _result,
    _session_and_snapshot,
    _verifier,
)


def _potential(process, owner, **overrides):
    return set_discovery_path(
        process=process,
        actor=owner,
        path="strategic",
        origin_basis="Menschlich dokumentiertes Geschäftsziel",
        strategic_potential=overrides.get(
            "strategic_potential", "Verständlichere Angebotsentscheidung"
        ),
        validation_step=overrides.get(
            "validation_step", "Mit Einkauf an einem Beispielsfall prüfen"
        ),
    )


def _payload(context):
    schema, prompt = context.generation_versions
    return {
        "schema_version": schema,
        "prompt_version": prompt,
        "options": {
            lane: {
                field: {
                    "text": f"{lane} {field}: könnte zum dokumentierten Ziel beitragen",
                    "source_ids": ["process.current_flow"],
                    "assumptions": [],
                    "open_evidence": ["Beitrag am Beispielsfall prüfen"],
                    "uncertainty": {"level": "high", "reason": "Wirkung noch offen"},
                }
                for field in GENERATED_OPTION_FIELDS
            }
            for lane in OPTION_LANES
        },
    }


def test_v1_catalog_and_hashes_are_frozen():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/accelerator/issue164_legacy.json").read_text()
    )
    catalog = get_capture_catalog("value_stream", "1.0")
    serialized = json.dumps(
        asdict(catalog), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(serialized.encode()).hexdigest() == fixture["catalog_hash"]
    assert canonical_answer_hash(fixture["answers"]) == fixture["answer_hash"]
    context = SolutionGenerationSourceContext(
        **fixture["context"], facts=tuple(SourceFact(**fact) for fact in fixture["facts"])
    )
    assert context.provider_payload() == fixture["source_payload"]
    assert (
        _source_hash(
            process_analysis=SimpleNamespace(
                pk=context.process_analysis_id, version=context.process_version
            ),
            facts=context.facts,
        )
        == context.source_hash
    )
    snapshot = build_solution_quality_snapshot(
        preview_payload=fixture["preview"], source_context=context
    )
    assert snapshot.snapshot_hash == fixture["quality_hash"]
    assert (
        build_validated_effective_solution_payload(fixture["preview"], context)
        == fixture["preview"]
    )
    schema = build_solution_generation_json_schema(context)
    assert schema["properties"]["prompt_version"]["const"] == "1.3"
    assert (
        "discovery_path.path"
        not in schema["properties"]["options"]["properties"]["assistant"]["properties"][
            "description"
        ]["properties"]["source_ids"]["items"]["enum"]
    )
    assert "strategischen Pfad" not in build_solution_generation_messages(context)[0]["content"]


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
@pytest.mark.parametrize("path", ["strategic", "problem"])
def test_guided_capture_through_human_adoption_and_source_readiness(owner, business_unit, path):
    # Answers carry reported process facts, while path authority remains at the process.
    template = make_process(owner, business_unit)
    stream, stage = template.stage.value_stream, template.stage
    values = {
        field: getattr(template, field)
        for field in (
            "name",
            "scope_start",
            "scope_end",
            "trigger",
            "outcome",
            "current_flow",
            "roles",
            "systems",
            "data_objects",
        )
    }
    template.delete()
    session = create_capture_session(actor=owner, capture_type="value_stream")
    session.target_value_stream = stream
    session.save(update_fields=["target_value_stream"])
    catalog = get_capture_catalog("value_stream", session.catalog_version)
    assert catalog.version == "2.0"
    answers = {key: "Berichteter Kontext" for key in catalog.required_question_keys}
    source_questions = {
        field: "process_operating_model"
        if field in {"roles", "systems", "data_objects"}
        else "process_scope_flow"
        for field in values
    }
    for question in set(source_questions.values()):
        answers[question] = "\n".join(
            value for field, value in values.items() if source_questions[field] == question
        )
    # Do not add a diagnosis or a baseline, including no n/a placeholder.
    session = save_capture_session(
        actor=owner,
        session_id=session.pk,
        expected_revision=session.revision,
        answer_updates=answers,
    )
    session = complete_capture_session(
        actor=owner, session_id=session.pk, expected_revision=session.revision
    )
    extraction = {
        "schema_version": "1.0",
        "prompt_version": "2.0",
        "open_questions": [],
        "contradictions": [],
        "suggestions": [
            {
                "target_object_type": "process_analysis",
                "target_field": f"process_analysis.{field}",
                "target_group_key": None,
                "field_type": "text",
                "suggested_value": value,
                "source_question": source_questions[field],
                "source_excerpt": value,
                "uncertainty": "low",
                "uncertainty_reason": "Wörtlicher Bericht",
            }
            for field, value in values.items()
        ],
    }
    with patch(
        "ki_radar.accelerator.analysis_service.request_openrouter",
        return_value=provider_result(extraction),
    ) as provider:
        analysis = execute_capture_analysis(actor=owner, session_id=session.pk)
    assert analysis.prompt_version == "2.0"
    assert (
        "Übertrage sie nicht in bottlenecks" in provider.call_args.kwargs["messages"][0]["content"]
    )
    batch = get_or_create_review_batch(analysis_id=analysis.pk, actor=owner)
    assert batch.interpretation_version == "2"
    item = batch.items.get()
    decide_review_item(
        batch_id=batch.pk,
        item_id=item.pk,
        actor=owner,
        action=StructuredReviewAction.CONFIRM,
        stage_reference=f"existing:{stage.pk}",
    )
    batch.refresh_from_db()
    commit_structured_batch(batch_id=batch.pk, actor=owner, idempotency_key=batch.idempotency_key)
    process = ProcessAnalysis.objects.get(stage=stage)
    assert (process.bottlenecks, process.baseline_metrics, process.confirmed_causes) == ("", "", "")
    assert not process.discovery_path_decisions.exists()
    if path == "strategic":
        decision = _potential(process, owner)
        context = build_solution_generation_source_context(process)
        assert context.is_ready
        facts = {fact.source_id: fact.value for fact in context.facts}
        assert facts["discovery_path.id"] == str(decision.pk)
        assert facts["discovery_path.revision"] == str(decision.revision)
        assert facts["discovery_path.strategic_potential"] == decision.strategic_potential
        payload = _payload(context)
        payload["options"]["organizational"]["bottleneck_coverage"]["source_ids"] = [
            "discovery_path.strategic_potential"
        ]
        with patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=provider_result(payload),
        ):
            run = generate_solution_preview(actor=owner, process_analysis_id=process.pk)
        assert (run.generation_schema_version, run.prompt_version) == ("2.0", "2.0")
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)
        assert process.solution_options.count() == 3
        assert set(process.solution_options.values_list("evaluation_status", flat=True)) == {
            "draft"
        }
        assert set(process.solution_options.values_list("recommendation", flat=True)) == {
            "candidate"
        }
        assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()
        assert all(not option.outcome_effect for option in process.solution_options.all())
    else:
        set_discovery_path(
            process=process, actor=owner, path="problem", origin_basis="Berichtetes Problem"
        )
        context = build_solution_generation_source_context(process)
        assert set(context.missing_required) == {"bottlenecks", "baseline_metrics"}
    process.refresh_from_db()
    assert (process.bottlenecks, process.baseline_metrics, process.confirmed_causes) == ("", "", "")


@pytest.mark.django_db
def test_strategic_readiness_needs_human_potential_and_validation_step(owner, business_unit):
    process = make_process(
        owner, business_unit, bottlenecks="", baseline_metrics="", confirmed_causes=""
    )
    _potential(process, owner, strategic_potential="", validation_step="")
    context = build_solution_generation_source_context(process)
    assert set(context.missing_required) == {
        "discovery_path.strategic_potential",
        "discovery_path.validation_step",
    }
    legacy = build_solution_generation_source_context(
        process, source_schema_version=LEGACY_SOURCE_SCHEMA_VERSION
    )
    assert set(legacy.missing_required) == {"bottlenecks", "baseline_metrics"}


@pytest.mark.django_db
def test_path_revision_invalidates_only_new_sources(owner, business_unit):
    process = make_process(owner, business_unit)
    legacy = build_solution_generation_source_context(
        process, source_schema_version=LEGACY_SOURCE_SCHEMA_VERSION
    )
    before = build_solution_generation_source_context(process)
    _potential(process, owner)
    assert build_solution_generation_source_context(process).source_hash != before.source_hash
    assert (
        build_solution_generation_source_context(
            process, source_schema_version=LEGACY_SOURCE_SCHEMA_VERSION
        ).source_hash
        == legacy.source_hash
    )
    assert _source_hash(process_analysis=process, facts=legacy.facts) == legacy.source_hash


@pytest.mark.django_db
@pytest.mark.parametrize("source_version", [LEGACY_SOURCE_SCHEMA_VERSION, SOURCE_SCHEMA_VERSION])
def test_old_and_new_runs_remain_readable_and_adoptable(
    owner, business_unit, other_owner, source_version
):
    process = make_process(owner, business_unit)
    context = build_solution_generation_source_context(
        process, source_schema_version=source_version
    )
    payload = {**_payload(context), "source_context": context.provider_payload(), "edits": {}}
    run = SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=process.version,
        source_hash=context.source_hash,
        requested_by=owner,
        status="success",
        generation_schema_version=context.generation_versions[0],
        prompt_version=context.generation_versions[1],
        preview_payload=payload,
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
    )
    frozen = copy.deepcopy(run.preview_payload)
    assert _source_context_from_generation_run(run).provider_payload() == context.provider_payload()
    assert not build_solution_generation_preview_state(run).stale
    with pytest.raises(PermissionDenied):
        adopt_solution_generation_bundle(actor=other_owner, run_id=run.pk)
    if source_version == SOURCE_SCHEMA_VERSION:
        _potential(process, owner)
        assert build_solution_generation_preview_state(run).stale
        with pytest.raises(SolutionGenerationAdoptionError, match="geändert"):
            adopt_solution_generation_bundle(actor=owner, run_id=run.pk)
    else:
        _potential(process, owner)
        assert not build_solution_generation_preview_state(run).stale
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)
    run.refresh_from_db()
    assert run.preview_payload["options"] == frozen["options"]
    assert run.preview_payload["source_context"] == frozen["source_context"]
    assert source_version_for_run(run) == source_version


@pytest.mark.django_db
@pytest.mark.parametrize("contract_version,expected", [("1.0", "draft"), ("2.0", "assessed")])
def test_investigation_adoption_pins_shared_comparison_policy(
    owner, business_unit, contract_version, expected
):
    process = make_process(owner, business_unit)
    result = adopt_investigation_drafts(
        actor=owner,
        process_analysis_id=process.pk,
        expected_process_version=process.version,
        base_process={},
        base_options={},
        process_fields={},
        contract_version=contract_version,
        solution_proposals=[
            {
                "name": "Organisatorische Klärung",
                "option_type": "organizational",
                "description": "Gemeinsam prüfen",
                "expected_value": "Qualitatives Potenzial",
                "bottleneck_coverage": "Bedingter Potenzialbezug",
                "risks": "Wirkung offen",
                "architecture_fit": "Zuständigkeit klären",
                "feasibility": "low",
                "time_to_value": "unknown",
            }
        ],
    )
    option = SolutionOption.objects.get(pk=result.created_solution_option_ids[0])
    assert option.evaluation_status == expected
    assert option.recommendation == "candidate"
    assert not option.outcome_effect
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("historical", [False, True])
def test_recovery_keeps_frozen_adoption_contract(owner, business_unit, tmp_path, historical):
    process = make_process(owner, business_unit)
    (tmp_path / "notes.txt").write_text("Berichteter Ablauf", encoding="utf-8")
    _, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    from ki_radar.accelerator.investigation_runtime import base_execution_snapshot

    def frozen_snapshot(*args, **kwargs):
        document = base_execution_snapshot(*args, **kwargs)
        if historical:
            document.pop("adoption_contract_version")
        return document

    with patch(
        "ki_radar.accelerator.investigation_runtime.base_execution_snapshot",
        side_effect=frozen_snapshot,
    ):
        handle = start_investigation(
            actor=owner, request=StartInvestigationRequest(snapshot.snapshot_id, "issue164")
        )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    assert run.execution_snapshot.get("adoption_contract_version", "1.0") == (
        "1.0" if historical else "2.0"
    )
    frozen = copy.deepcopy(run.execution_snapshot)
    recover_investigation(actor=owner, run_id=run.pk)
    run.refresh_from_db()
    assert run.execution_snapshot == frozen
    assert run.execution_snapshot.get("adoption_contract_version", "1.0") == (
        "1.0" if historical else "2.0"
    )


@pytest.mark.django_db
def test_new_discovery_accepts_missing_diagnosis_old_schema_still_rejects(
    owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    session.catalog_version = "2.0"
    session.save(update_fields=["catalog_version"])
    draft = _draft()
    draft["process_analysis"]["bottlenecks"] = ""
    draft["process_analysis"]["baseline_metrics"] = ""
    with pytest.raises(DiscoveryContractError):
        validate_discovery_payload(draft, allowed_refs={"U0", "S1", "S2"}, evidence_text="11 2")
    draft["schema_version"] = DISCOVERY_SCHEMA_VERSION_V2
    monkeypatch.setattr(
        "ki_radar.accelerator.architect_service._provider_call",
        lambda **kwargs: _result(_verifier() if "verifier" in kwargs["schema_name"] else draft),
    )
    analysis = execute_autonomous_business_discovery(
        actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
    )
    assert analysis.extraction_schema_version == "ap1-discovery-v2"
    assert analysis.prompt_version == "ap1-methodology-v14"
    assert analysis.result_payload["draft"]["process_analysis"]["bottlenecks"] == ""
    assert (
        build_discovery_json_schema()["properties"]["process_analysis"]["properties"][
            "bottlenecks"
        ]["minLength"]
        == 1
    )
    assert (
        build_discovery_json_schema(DISCOVERY_SCHEMA_VERSION_V2)["properties"]["process_analysis"][
            "properties"
        ]["bottlenecks"].get("minLength", 0)
        == 0
    )
    result = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert (process.bottlenecks, process.baseline_metrics, process.confirmed_causes) == ("", "", "")
    assert not process.discovery_path_decisions.exists()


@pytest.mark.django_db
@override_settings(**QUALITY_LIMITS)
@pytest.mark.parametrize("version", [LEGACY_SOURCE_SCHEMA_VERSION, SOURCE_SCHEMA_VERSION])
def test_critic_repair_final_critic_keep_the_bound_cohort(owner, business_unit, version):
    process = make_process(owner, business_unit)
    context = build_solution_generation_source_context(process, source_schema_version=version)
    payload = {**_payload(context), "source_context": context.provider_payload(), "edits": {}}
    run = SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=process.version,
        source_hash=context.source_hash,
        requested_by=owner,
        status="success",
        generation_schema_version=context.generation_versions[0],
        prompt_version=context.generation_versions[1],
        preview_payload=payload,
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
    )
    critic_version, repair_version = (
        ("2.0", "1.4") if version == LEGACY_SOURCE_SCHEMA_VERSION else ("2.1", "1.5")
    )
    before = build_solution_quality_snapshot(preview_payload=payload, source_context=context)
    critic_payload = {
        "schema_version": "1.0",
        "prompt_version": critic_version,
        "findings": _critic_findings(),
    }
    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result(critic_payload),
    ):
        critic = run_initial_solution_critic(solution_generation_run_id=run.pk)
    assert critic.status == "success"
    assert critic.prompt_version == critic_version
    assert critic.input_hash == before.snapshot_hash
    assert (
        build_solution_repair_plan(generation_run=run, initial_critic_run=critic).snapshot_hash
        == before.snapshot_hash
    )
    repair_payload = _repair_payload()
    repair_payload["prompt_version"] = repair_version
    with patch(
        "ki_radar.accelerator.solution_repair_service.request_openrouter",
        return_value=provider_result(repair_payload),
    ):
        repair = run_targeted_solution_repair(solution_generation_run_id=run.pk, actor=owner)
    assert repair.status == "success"
    assert repair.prompt_version == repair_version
    run.refresh_from_db()
    assert run.preview_payload["options"] == payload["options"]
    assert run.preview_payload["source_context"] == payload["source_context"]
    with patch(
        "ki_radar.accelerator.solution_critic_service.request_openrouter",
        return_value=provider_result({**critic_payload, "findings": []}),
    ):
        final = run_final_solution_critic(solution_generation_run_id=run.pk)
    assert final.status == "success"
    assert final.input_hash == repair.result_payload["output_snapshot_hash"]
    assert final.prompt_version == critic_version


def test_old_capture_and_interpretation_keep_their_required_diagnosis():
    old = get_capture_catalog("value_stream", "1.0")
    new = get_capture_catalog("value_stream", "2.0")
    answers = {key: "Kontext" for key in new.required_question_keys}
    assert validate_answer_document(new, answers, require_complete=True) == answers
    with pytest.raises(CaptureAnswerValidationError):
        validate_answer_document(old, answers, require_complete=True)
    with pytest.raises(StructuredProcessError):
        _validate_process_values(local_key="process", values={"name": "Name"})


@pytest.mark.django_db
def test_cross_cohort_generation_versions_fail_closed(owner, business_unit):
    process = make_process(owner, business_unit)
    current = build_solution_generation_source_context(process)
    legacy = build_solution_generation_source_context(
        process, source_schema_version=LEGACY_SOURCE_SCHEMA_VERSION
    )
    for context, wrong in [(current, legacy), (legacy, current)]:
        with pytest.raises(SolutionGenerationContractError):
            validate_solution_generation_payload(_payload(wrong), context, allow_historical=True)
