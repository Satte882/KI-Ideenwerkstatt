from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun, SolutionQualityRun
from ki_radar.accelerator.solution_generation_contract import (
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
)
from ki_radar.accelerator.solution_quality_runs import (
    SolutionQualityRunError,
    mark_solution_quality_step_failed,
    mark_solution_quality_step_success,
    reserve_solution_quality_step,
)
from ki_radar.accounts.models import User
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(owner, business_unit) -> ProcessAnalysis:
    stream = ValueStream.objects.create(
        name="Beschaffung Quality Run",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Bedarf freigegeben",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        description="Angebote vergleichen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Quality-Run-Prozess",
        current_flow="Angebote werden manuell verglichen.",
        analyzed_by=owner,
    )


def make_generation_run(owner, business_unit, *, status=SolutionGenerationRun.Status.SUCCESS):
    process = make_process(owner, business_unit)
    finished_at = timezone.now() if status != SolutionGenerationRun.Status.RUNNING else None
    return SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=process.version,
        source_hash="a" * 64,
        requested_by=owner,
        status=status,
        provider="openrouter",
        model_name="test/generator",
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        started_at=timezone.now() - timedelta(seconds=1),
        finished_at=finished_at,
        preview_payload={"options": {"present": True}},
        expires_at=timezone.now() + timedelta(days=30),
    )


def reserve(run, owner, *, step_type=SolutionQualityRun.StepType.INITIAL_CRITIC):
    return reserve_solution_quality_step(
        solution_generation_run_id=run.pk,
        actor=owner,
        step_type=step_type,
        input_hash="b" * 64,
        prompt_version="1.0",
        output_schema_version="1.0",
        input_chars=321,
    )


@pytest.mark.django_db
def test_quality_step_types_are_fixed() -> None:
    expected = ("initial_critic", "repair", "final_critic")
    assert tuple(SolutionQualityRun.StepType.values) == expected


@pytest.mark.django_db
def test_reservation_records_running_step(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)

    reservation = reserve(generation_run, owner)

    assert reservation.created is True
    quality_run = reservation.run
    assert quality_run.solution_generation_run == generation_run
    assert quality_run.requested_by == owner
    assert quality_run.step_type == SolutionQualityRun.StepType.INITIAL_CRITIC
    assert quality_run.status == SolutionQualityRun.Status.RUNNING
    assert quality_run.input_hash == "b" * 64
    assert quality_run.prompt_version == "1.0"
    assert quality_run.output_schema_version == "1.0"
    assert quality_run.input_chars == 321
    assert quality_run.finished_at is None


@pytest.mark.django_db
def test_duplicate_reservation_keeps_first_snapshot(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    first = reserve(generation_run, owner)

    second = reserve_solution_quality_step(
        solution_generation_run_id=generation_run.pk,
        actor=owner,
        step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        input_hash="c" * 64,
        prompt_version="9.9",
        output_schema_version="9.9",
        input_chars=999,
    )

    assert first.created is True
    assert second.created is False
    assert second.run.pk == first.run.pk
    second.run.refresh_from_db()
    assert second.run.input_hash == "b" * 64
    assert second.run.prompt_version == "1.0"
    assert second.run.output_schema_version == "1.0"
    assert second.run.input_chars == 321
    assert SolutionQualityRun.objects.filter(solution_generation_run=generation_run).count() == 1


@pytest.mark.django_db
def test_each_fixed_step_is_one_shot(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)

    reservations = [
        reserve(generation_run, owner, step_type=step_type)
        for step_type in SolutionQualityRun.StepType.values
    ]
    duplicates = [
        reserve(generation_run, owner, step_type=step_type)
        for step_type in SolutionQualityRun.StepType.values
    ]

    assert all(item.created for item in reservations)
    assert not any(item.created for item in duplicates)
    assert SolutionQualityRun.objects.filter(solution_generation_run=generation_run).count() == 3


@pytest.mark.django_db
def test_invalid_reservation_contract_creates_no_row(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    cases = (
        ("unknown", "b" * 64, "invalid_quality_step"),
        (SolutionQualityRun.StepType.INITIAL_CRITIC, "not-a-hash", "invalid_quality_input_hash"),
    )

    for step_type, input_hash, expected_code in cases:
        with pytest.raises(SolutionQualityRunError) as exc_info:
            reserve_solution_quality_step(
                solution_generation_run_id=generation_run.pk,
                actor=owner,
                step_type=step_type,
                input_hash=input_hash,
                prompt_version="1.0",
                output_schema_version="1.0",
            )
        assert exc_info.value.code == expected_code

    assert not SolutionQualityRun.objects.filter(solution_generation_run=generation_run).exists()


@pytest.mark.django_db
def test_non_success_generation_is_rejected(owner, business_unit) -> None:
    for status in (SolutionGenerationRun.Status.RUNNING, SolutionGenerationRun.Status.FAILED):
        generation_run = make_generation_run(owner, business_unit, status=status)

        with pytest.raises(SolutionQualityRunError) as exc_info:
            reserve(generation_run, owner)

        assert exc_info.value.code == "quality_preview_unavailable"
        quality_exists = SolutionQualityRun.objects.filter(
            solution_generation_run=generation_run,
        ).exists()
        assert not quality_exists


@pytest.mark.django_db
def test_empty_success_preview_is_rejected(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    generation_run.preview_payload = {}
    generation_run.save(update_fields=["preview_payload", "updated_at"])

    with pytest.raises(SolutionQualityRunError) as exc_info:
        reserve(generation_run, owner)

    assert exc_info.value.code == "quality_preview_unavailable"


@pytest.mark.django_db
def test_failed_step_consumes_one_shot(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    reservation = reserve(generation_run, owner)

    failed = mark_solution_quality_step_failed(
        run_id=reservation.run.pk,
        error_code="provider_unavailable",
    )
    repeated = reserve(generation_run, owner)

    assert failed.status == SolutionQualityRun.Status.FAILED
    assert failed.finished_at is not None
    assert failed.error_code == "provider_unavailable"
    assert repeated.created is False
    assert repeated.run.pk == failed.pk
    assert repeated.run.status == SolutionQualityRun.Status.FAILED
    assert SolutionQualityRun.objects.filter(solution_generation_run=generation_run).count() == 1


@pytest.mark.django_db
def test_success_stores_provider_metadata(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    reservation = reserve(generation_run, owner)

    completed = mark_solution_quality_step_success(
        run_id=reservation.run.pk,
        result_payload={"findings": []},
        model_name="test/critic",
        output_chars=77,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost=Decimal("0.000123"),
    )

    assert completed.status == SolutionQualityRun.Status.SUCCESS
    assert completed.finished_at is not None
    assert completed.duration_ms is not None
    assert completed.duration_ms >= 0
    assert completed.model_name == "test/critic"
    assert completed.output_chars == 77
    assert completed.prompt_tokens == 10
    assert completed.completion_tokens == 20
    assert completed.total_tokens == 30
    assert completed.cost == Decimal("0.000123")
    assert completed.result_payload == {"findings": []}


@pytest.mark.django_db
def test_terminal_step_cannot_finalize_twice(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    reservation = reserve(generation_run, owner)
    mark_solution_quality_step_failed(run_id=reservation.run.pk, error_code="timeout")

    with pytest.raises(SolutionQualityRunError) as exc_info:
        mark_solution_quality_step_success(
            run_id=reservation.run.pk,
            result_payload={"findings": []},
        )

    assert exc_info.value.code == "quality_step_terminal"


@pytest.mark.django_db
def test_database_rejects_duplicate_step(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    first = reserve(generation_run, owner).run

    with pytest.raises(IntegrityError), transaction.atomic():
        SolutionQualityRun.objects.create(
            solution_generation_run=generation_run,
            requested_by=owner,
            step_type=first.step_type,
            prompt_version="1.0",
            output_schema_version="1.0",
            input_hash="c" * 64,
        )


@pytest.mark.django_db
def test_database_rejects_invalid_terminal_state(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)

    with pytest.raises(IntegrityError), transaction.atomic():
        SolutionQualityRun.objects.create(
            solution_generation_run=generation_run,
            requested_by=owner,
            step_type=SolutionQualityRun.StepType.REPAIR,
            status=SolutionQualityRun.Status.FAILED,
            prompt_version="1.0",
            output_schema_version="1.0",
            input_hash="d" * 64,
        )


@pytest.mark.django_db(transaction=True)
def test_parallel_reservation_is_one_shot(owner, business_unit) -> None:
    generation_run = make_generation_run(owner, business_unit)
    barrier = Barrier(2)

    def reserve_once():
        close_old_connections()
        actor = User.objects.get(pk=owner.pk)
        barrier.wait()
        try:
            return reserve_solution_quality_step(
                solution_generation_run_id=generation_run.pk,
                actor=actor,
                step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
                input_hash="e" * 64,
                prompt_version="1.0",
                output_schema_version="1.0",
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reserve_once) for _ in range(2)]
        results = [future.result() for future in futures]

    assert sum(result.created for result in results) == 1
    assert len({result.run.pk for result in results}) == 1
    assert (
        SolutionQualityRun.objects.filter(
            solution_generation_run=generation_run,
            step_type=SolutionQualityRun.StepType.INITIAL_CRITIC,
        ).count()
        == 1
    )
