from __future__ import annotations

import copy
from datetime import timedelta

import pytest
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_critic_contract import validate_solution_critic_payload
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
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
    SolutionRepairTarget,
    build_solution_repair_plan,
    reserve_solution_repair_attempt,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

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
        name="Beschaffung Repair",
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
    validated = validate_solution_generation_payload(
        _valid_generation_payload(),
        source_context,
    )
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


def _critic_findings(*, repairable: bool = True) -> list[dict[str, object]]:
    return [
        {
            "criterion": "bottleneck_fit",
            "option": "assistant",
            "field": "bottleneck_coverage",
            "finding": "Der Engpassbezug sollte präziser formuliert werden.",
            "source_ids": ["process.bottlenecks"],
            "repairable": repairable,
            "related_targets": (
                [
                    {
                        "option": "rule_automation",
                        "field": "bottleneck_coverage",
                    }
                ]
                if repairable
                else []
            ),
        },
        {
            "criterion": "evidence_discipline",
            "option": "organizational",
            "field": "expected_value",
            "finding": "Diese Evidenzlücke bleibt bewusst manuell zu prüfen.",
            "source_ids": ["process.bottlenecks"],
            "repairable": False,
            "related_targets": [],
        },
    ]


def _make_initial_critic(
    run: SolutionGenerationRun,
    *,
    repairable: bool = True,
) -> SolutionQualityRun:
    source_context = build_solution_generation_source_context(run.process_analysis)
    snapshot = build_solution_quality_snapshot(
        preview_payload=run.preview_payload,
        source_context=source_context,
    )
    result_payload = validate_solution_critic_payload(
        {
            "schema_version": CRITIC_SCHEMA_VERSION,
            "prompt_version": CRITIC_PROMPT_VERSION,
            "findings": _critic_findings(repairable=repairable),
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


@pytest.mark.django_db
def test_repair_plan_uses_all_repairable_findings_and_only_explicit_targets(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)

    plan = build_solution_repair_plan(
        generation_run=run,
        initial_critic_run=critic,
    )

    assert len(plan.finding_ids) == 1
    assert plan.targets == (
        SolutionRepairTarget(
            option="rule_automation",
            field="bottleneck_coverage",
        ),
        SolutionRepairTarget(
            option="assistant",
            field="bottleneck_coverage",
        ),
    )
    assert SolutionRepairTarget(option="organizational", field="expected_value") not in plan.targets


@pytest.mark.django_db
def test_human_edit_on_repair_target_blocks_whole_repair(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    update_solution_generation_preview_edits(
        run_id=run.pk,
        edits={
            "assistant": {
                "bottleneck_coverage": "Vom Menschen präzisierter Engpassbezug.",
            }
        },
    )
    run.refresh_from_db()
    critic = _make_initial_critic(run)

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "human_edit_conflict"


@pytest.mark.django_db
def test_human_edit_after_critic_fails_whole_preview_cas(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)

    update_solution_generation_preview_edits(
        run_id=run.pk,
        edits={
            "organizational": {
                "description": "Nach dem Critic manuell geänderte Beschreibung.",
            }
        },
    )
    run.refresh_from_db()

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "repair_stale"
    assert exc_info.value.stale_reason == "quality_snapshot_changed"


@pytest.mark.django_db
def test_source_change_after_critic_is_explicitly_stale(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)
    process = run.process_analysis
    process.bottlenecks = "Geänderter Engpass nach der Qualitätsprüfung."
    process.version += 1
    process.save(update_fields=["bottlenecks", "version", "updated_at"])
    run.refresh_from_db()

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "repair_stale"
    assert exc_info.value.stale_reason == "source_context_changed"


@pytest.mark.django_db
def test_critic_contract_version_change_is_explicitly_stale(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)
    critic.prompt_version = "0.9"
    critic.save(update_fields=["prompt_version", "updated_at"])

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "repair_stale"
    assert exc_info.value.stale_reason == "critic_prompt_version_changed"


@pytest.mark.django_db
def test_repair_contract_version_drift_is_bound_to_snapshot(owner, business_unit, monkeypatch):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)

    monkeypatch.setattr(
        "ki_radar.accelerator.solution_quality_snapshot.REPAIR_PROMPT_VERSION",
        "9.9",
    )
    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "repair_stale"
    assert exc_info.value.stale_reason == "quality_snapshot_changed"


@pytest.mark.django_db
def test_no_repairable_findings_do_not_create_repair_scope(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run, repairable=False)

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "no_repairable_findings"


@pytest.mark.django_db
def test_tampered_persisted_finding_id_fails_closed(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)
    tampered = copy.deepcopy(critic.result_payload)
    tampered["findings"][0]["finding_id"] = "finding_tampered"
    critic.result_payload = tampered
    critic.save(update_fields=["result_payload", "updated_at"])

    with pytest.raises(SolutionRepairContractError) as exc_info:
        build_solution_repair_plan(
            generation_run=run,
            initial_critic_run=critic,
        )

    assert exc_info.value.code == "invalid_initial_critic_result"


@pytest.mark.django_db
def test_repair_reservation_is_one_shot_and_reuses_ap3_state_machine(owner, business_unit):
    run = _make_generation_run(owner, business_unit)
    critic = _make_initial_critic(run)

    reservation = reserve_solution_repair_attempt(
        solution_generation_run_id=run.pk,
        actor=owner,
    )

    assert reservation.run.step_type == SolutionQualityRun.StepType.REPAIR
    assert reservation.run.status == SolutionQualityRun.Status.RUNNING
    assert reservation.run.input_hash == critic.input_hash
    assert reservation.run.prompt_version == REPAIR_PROMPT_VERSION
    assert reservation.run.output_schema_version == REPAIR_SCHEMA_VERSION
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=run,
            step_type=SolutionQualityRun.StepType.REPAIR,
        ).count()
        == 1
    )

    with pytest.raises(SolutionRepairContractError) as exc_info:
        reserve_solution_repair_attempt(
            solution_generation_run_id=run.pk,
            actor=owner,
        )

    assert exc_info.value.code == "repair_attempt_consumed"
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=run,
            step_type=SolutionQualityRun.StepType.REPAIR,
        ).count()
        == 1
    )
