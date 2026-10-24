"""Replay recorded synthetic A/B responses; no additional provider calls."""

import copy
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_generation_contract import (
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
    OPTION_NAME_MAX_LENGTH,
    build_solution_generation_json_schema,
)
from ki_radar.accelerator.solution_generation_effective import (
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_service import (
    SolutionGenerationError,
    generate_solution_preview,
)
from ki_radar.accelerator.solution_generation_sources import (
    SOURCE_SCHEMA_VERSION,
    SolutionGenerationSourceContext,
    SourceFact,
    build_solution_generation_source_context,
    source_version_for_run,
)
from ki_radar.accelerator.solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_contract import set_discovery_path
from tests.test_block7_solution_generation_validation import VALID_LIMITS, provider_result

RECORDED = json.loads(
    (Path(__file__).parent / "fixtures/issue175_real_model_responses.json").read_text(
        encoding="utf-8"
    )
)["cases"]


def _context(case):
    recorded = RECORDED[case]
    source = recorded["preview_payload"]["source_context"]
    return SolutionGenerationSourceContext(
        process_analysis_id=recorded["original_run_id"],
        source_hash=recorded["source_hash"],
        missing_required=(),
        facts=tuple(SourceFact(**fact) for fact in source["facts"]),
        process_version=source["process_version"],
        validation_state=source["validation_state"],
        source_schema_version=source["source_schema_version"],
    )


def _payload(case, *, current):
    preview = RECORDED[case]["preview_payload"]
    payload = {
        key: copy.deepcopy(preview[key]) for key in ("schema_version", "prompt_version", "options")
    }
    if current:
        payload.update(
            schema_version=GENERATION_SCHEMA_VERSION, prompt_version=GENERATION_PROMPT_VERSION
        )
    return payload


def test_current_schema_bounds_only_titles_including_provenance_branches():
    schema = build_solution_generation_json_schema()
    assert OPTION_NAME_MAX_LENGTH == SolutionOption._meta.get_field("name").max_length == 200
    for lane in OPTION_LANES:
        fields = schema["properties"]["options"]["properties"][lane]["properties"]
        name = fields["name"]
        for branch in [name, *name["anyOf"]]:
            assert branch["properties"]["text"]["maxLength"] == 200
        assert "maxLength" not in fields["description"]["properties"]["text"]


@pytest.mark.parametrize("lane", OPTION_LANES)
@pytest.mark.parametrize("length", [200, 201])
def test_title_boundary_rejects_without_truncating(lane, length):
    payload = _payload("B", current=True)
    payload["options"][lane]["name"]["text"] = "Ä" * length
    original = copy.deepcopy(payload)
    if length == 200:
        assert validate_solution_generation_payload(payload, _context("B")) == payload
    else:
        with pytest.raises(SolutionGenerationContractError, match=rf"{lane}.name.text.*200"):
            validate_solution_generation_payload(payload, _context("B"))
    assert payload == original


def test_recorded_a_is_rejected_as_fresh_output_but_remains_readable():
    fresh = _payload("A", current=True)
    with pytest.raises(SolutionGenerationContractError) as exc:
        validate_solution_generation_payload(fresh, _context("A"))
    assert len(exc.value.errors) == 3
    assert all(".name.text" in error for error in exc.value.errors)
    old = RECORDED["A"]["preview_payload"]
    assert (
        build_validated_effective_solution_payload(old, _context("A"))["options"] == old["options"]
    )
    with pytest.raises(SolutionGenerationContractError):
        validate_solution_generation_payload(_payload("A", current=False), _context("A"))


def _replay_run(owner, business_unit, case):
    """Rebind recorded content to isolated test objects; keep provider statements unchanged."""
    recorded = RECORDED[case]
    preview = copy.deepcopy(recorded["preview_payload"])
    facts = {fact["source_id"]: fact["value"] for fact in preview["source_context"]["facts"]}
    initiative = ImprovementInitiative.objects.create(
        title=f"Synthetic replay {case}",
        created_by=owner,
        updated_by=owner,
        **{
            key.removeprefix("initiative."): value
            for key, value in facts.items()
            if key.startswith("initiative.") and key != "initiative.outcome_revision"
        },
    )
    stream = ValueStream.objects.create(
        name=f"Synthetic replay {case}",
        owner=owner,
        created_by=owner,
        business_unit=business_unit,
        trigger="Synthetic request",
        outcome="Synthetic draft",
        scope_in="Request preparation",
        constraints=facts["value_stream.constraints"],
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name=facts["stage.name"],
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        initiative=initiative,
        analyzed_by=owner,
        **{
            key.removeprefix("process."): value
            for key, value in facts.items()
            if key.startswith("process.")
        },
    )
    set_discovery_path(
        process=process,
        actor=owner,
        path=facts["discovery_path.path"],
        origin_basis=facts["discovery_path.origin_basis"],
        strategic_potential=facts.get("discovery_path.strategic_potential", ""),
        validation_step=facts.get("discovery_path.validation_step", ""),
    )
    context = build_solution_generation_source_context(process)
    assert context.is_ready
    preview["source_context"] = context.provider_payload()
    run = SolutionGenerationRun.objects.create(
        process_analysis=process,
        requested_by=owner,
        status="success",
        process_version=context.process_version,
        source_hash=context.source_hash,
        generation_schema_version=preview["schema_version"],
        prompt_version=preview["prompt_version"],
        preview_payload=preview,
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
    )
    for quality in recorded["quality_runs"]:
        SolutionQualityRun.objects.create(
            solution_generation_run=run,
            requested_by=owner,
            finished_at=timezone.now(),
            **quality,
        )
    assert source_version_for_run(run) == SOURCE_SCHEMA_VERSION
    return run


@pytest.mark.django_db
@override_settings(**{**VALID_LIMITS, "ACCELERATOR_LLM_MAX_INPUT_CHARS": "20000"})
def test_fresh_overlong_response_fails_before_preview_or_critic(owner, business_unit):
    saved = _replay_run(owner, business_unit, "A")
    with (
        patch(
            "ki_radar.accelerator.solution_generation_service.request_openrouter",
            return_value=provider_result(_payload("A", current=True)),
        ) as provider,
        pytest.raises(SolutionGenerationError) as exc,
    ):
        generate_solution_preview(actor=owner, process_analysis_id=saved.process_analysis_id)
    assert exc.value.code == "invalid_generation_payload"
    provider.assert_called_once()
    failed = SolutionGenerationRun.objects.exclude(pk=saved.pk).get()
    assert failed.status == "failed"
    assert failed.preview_payload == {}
    assert not failed.quality_runs.exists()
    assert not failed.process_analysis.solution_options.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["A", "B"])
def test_recorded_preview_edit_and_adoption_preserve_quality_and_gates(
    client,
    owner,
    business_unit,
    case,
):
    with patch(
        "urllib.request.urlopen", side_effect=AssertionError("Replay must stay offline")
    ) as network:
        run = _replay_run(owner, business_unit, case)
        client.force_login(owner)
        url = reverse("accelerator:solution_generation_preview", args=[run.pk])
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["editable"]
        frozen = copy.deepcopy(run.preview_payload)
        quality_before = list(run.quality_runs.values("id", "result_payload", "input_hash"))
        if case == "A":
            assert response.context["quality_state"].findings == ()
            post = {
                f"{lane}__{field}": statement["text"]
                for lane, option in frozen["options"].items()
                for field, statement in option.items()
            }
            # Explicit reviewer titles; never silently truncate the provider response.
            for lane in OPTION_LANES:
                post[f"{lane}__name"] = f"Geprüfter Entwurf: {lane}"
            assert client.post(url, post).status_code == 302
            run.refresh_from_db()
            assert run.preview_payload["edits"] == {
                lane: {"name": post[f"{lane}__name"]} for lane in OPTION_LANES
            }
        else:
            state = response.context["quality_state"]
            assert state.human_review and state.repair_consumed and not state.repair_available
            assert len(state.findings) == 1
            assert state.findings[0]["field"] == "application_impact"
            assert b"adopt-selected-solutions" in response.content
        adopt_url = reverse("accelerator:solution_generation_adopt", args=[run.pk])
        selection = {"selection_mode": "explicit", "selected_lanes": list(OPTION_LANES)}
        assert client.post(adopt_url, selection).status_code == 302
        run.refresh_from_db()
        assert run.preview_payload["adoption"]["lanes"] == list(OPTION_LANES)
        options = list(run.process_analysis.solution_options.all())
        assert len(options) == 3
        assert all(option.evaluation_status == "draft" for option in options)
        assert all(option.recommendation == "candidate" for option in options)
        assert all(option.feasibility == "not_assessed" for option in options)
        assert all(option.integration_effort == "not_assessed" for option in options)
        assert run.preview_payload["options"] == frozen["options"]
        assert run.preview_payload["source_context"] == frozen["source_context"]
        assert run.preview_payload.get("machine_repair") == frozen.get("machine_repair")
        assert list(run.quality_runs.values("id", "result_payload", "input_hash")) == quality_before
        assert client.post(adopt_url, selection).status_code == 302
        assert run.process_analysis.solution_options.count() == 3
        assert not SolutionSelectionDecision.objects.exists()
        assert not UseCase.objects.exists()
        assert client.get(url).context["state"].adopted
        network.assert_not_called()
