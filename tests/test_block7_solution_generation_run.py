from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.models import (
    AcceleratorLLMQuota,
    CaptureAnalysis,
    CaptureSession,
    SolutionGenerationRun,
)
from ki_radar.accelerator.solution_generation_service import (
    RUNNING_RECOVERY_GRACE_SECONDS,
    SolutionGenerationAlreadyRunning,
    SolutionGenerationQuotaExceeded,
    mark_solution_generation_failed,
    prepare_solution_generation_run,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

VALID_LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "12000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "400",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "5",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "20",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS": "8192",
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "2",
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS": "30",
}
CONTEXT_ONE_LIMITS = {
    **VALID_LIMITS,
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT": "1",
}
USER_ONE_LIMITS = {
    **VALID_LIMITS,
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "1",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "1",
}
GLOBAL_ONE_LIMITS = {
    **USER_ONE_LIMITS,
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "1",
}


def make_process(owner, business_unit, *, suffix=""):
    stream = ValueStream.objects.create(
        name=f"Beschaffung bis Zahlung{suffix}",
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


def quota_counts():
    return list(AcceleratorLLMQuota.objects.order_by("scope").values_list("scope", "calls"))


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_prepare_persists_block4_compatible_metadata_and_all_three_quotas(owner, business_unit):
    process = make_process(owner, business_unit)

    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    run = prepared.run

    assert run.status == SolutionGenerationRun.Status.RUNNING
    assert run.process_analysis == process
    assert run.process_version == process.version
    assert run.source_hash == prepared.source_context.source_hash
    assert run.requested_by == owner
    assert run.provider == "openrouter"
    assert run.input_chars == sum(len(item["content"]) for item in prepared.messages)
    assert run.output_chars == 0
    assert run.prompt_tokens is None
    assert run.completion_tokens is None
    assert run.total_tokens is None
    assert run.cost is None
    assert run.expires_at > timezone.now() + timedelta(days=29)

    shared_fields = (
        "provider",
        "model_name",
        "started_at",
        "finished_at",
        "duration_ms",
        "error_code",
        "input_chars",
        "output_chars",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost",
    )
    for field_name in shared_fields:
        run_field = SolutionGenerationRun._meta.get_field(field_name)
        analysis_field = CaptureAnalysis._meta.get_field(field_name)
        assert type(run_field) is type(analysis_field)

    quotas = AcceleratorLLMQuota.objects.filter(quota_date=timezone.localdate())
    assert quotas.count() == 3
    assert quotas.get(scope=AcceleratorLLMQuota.Scope.CONTEXT).process_analysis == process
    assert quotas.get(scope=AcceleratorLLMQuota.Scope.CONTEXT).session is None
    assert quotas.get(scope=AcceleratorLLMQuota.Scope.USER).user == owner
    assert quotas.get(scope=AcceleratorLLMQuota.Scope.GLOBAL).calls == 1


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_running_process_rejects_second_start_before_extra_quota(owner, business_unit):
    process = make_process(owner, business_unit)
    prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    before = quota_counts()

    with pytest.raises(SolutionGenerationAlreadyRunning) as exc_info:
        prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    assert exc_info.value.code == "generation_already_running"
    assert quota_counts() == before
    assert SolutionGenerationRun.objects.filter(process_analysis=process).count() == 1


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_stale_running_generation_is_failed_and_next_start_proceeds(owner, business_unit):
    process = make_process(owner, business_unit)
    first = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    stale_started_at = timezone.now() - timedelta(seconds=15 + RUNNING_RECOVERY_GRACE_SECONDS + 1)
    SolutionGenerationRun.objects.filter(pk=first.run.pk).update(started_at=stale_started_at)

    second = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    first.run.refresh_from_db()
    assert first.run.status == SolutionGenerationRun.Status.FAILED
    assert first.run.error_code == "stale_running_recovered"
    assert second.run.status == SolutionGenerationRun.Status.RUNNING
    assert second.run.pk != first.run.pk


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_database_constraint_allows_at_most_one_running_generation(owner, business_unit):
    process = make_process(owner, business_unit)
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    with pytest.raises(IntegrityError), transaction.atomic():
        SolutionGenerationRun.objects.create(
            process_analysis=process,
            process_version=process.version,
            source_hash="f" * 64,
            requested_by=owner,
            prompt_version=prepared.run.prompt_version,
            generation_schema_version=prepared.run.generation_schema_version,
            expires_at=prepared.run.expires_at,
        )


@pytest.mark.django_db
@override_settings(**CONTEXT_ONE_LIMITS)
def test_context_limit_rolls_back_second_run_and_other_quota_increments(owner, business_unit):
    process = make_process(owner, business_unit)
    first = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)
    mark_solution_generation_failed(run_id=first.run.pk, error_code="test_terminal")

    with pytest.raises(SolutionGenerationQuotaExceeded) as exc_info:
        prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    assert exc_info.value.code == "context_quota_exceeded"
    assert SolutionGenerationRun.objects.filter(process_analysis=process).count() == 1
    context_quota = AcceleratorLLMQuota.objects.get(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        process_analysis=process,
        quota_date=timezone.localdate(),
    )
    user_quota = AcceleratorLLMQuota.objects.get(
        scope=AcceleratorLLMQuota.Scope.USER,
        user=owner,
        quota_date=timezone.localdate(),
    )
    global_quota = AcceleratorLLMQuota.objects.get(
        scope=AcceleratorLLMQuota.Scope.GLOBAL,
        quota_date=timezone.localdate(),
    )
    assert context_quota.calls == 1
    assert user_quota.calls == 1
    assert global_quota.calls == 1


@pytest.mark.django_db
@override_settings(**USER_ONE_LIMITS)
def test_user_limit_applies_across_process_analyses(owner, business_unit):
    first_process = make_process(owner, business_unit, suffix=" A")
    second_process = make_process(owner, business_unit, suffix=" B")
    first = prepare_solution_generation_run(actor=owner, process_analysis_id=first_process.pk)
    mark_solution_generation_failed(run_id=first.run.pk, error_code="test_terminal")

    with pytest.raises(SolutionGenerationQuotaExceeded) as exc_info:
        prepare_solution_generation_run(actor=owner, process_analysis_id=second_process.pk)

    assert exc_info.value.code == "user_quota_exceeded"
    assert not SolutionGenerationRun.objects.filter(process_analysis=second_process).exists()
    assert not AcceleratorLLMQuota.objects.filter(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        process_analysis=second_process,
    ).exists()


@pytest.mark.django_db
@override_settings(**GLOBAL_ONE_LIMITS)
def test_global_limit_applies_across_users(owner, other_owner, business_unit):
    first_process = make_process(owner, business_unit, suffix=" A")
    second_process = make_process(other_owner, business_unit, suffix=" B")
    first = prepare_solution_generation_run(actor=owner, process_analysis_id=first_process.pk)
    mark_solution_generation_failed(run_id=first.run.pk, error_code="test_terminal")

    with pytest.raises(SolutionGenerationQuotaExceeded) as exc_info:
        prepare_solution_generation_run(actor=other_owner, process_analysis_id=second_process.pk)

    assert exc_info.value.code == "global_quota_exceeded"
    assert not SolutionGenerationRun.objects.filter(process_analysis=second_process).exists()
    assert not AcceleratorLLMQuota.objects.filter(
        scope=AcceleratorLLMQuota.Scope.USER,
        user=other_owner,
    ).exists()


@pytest.mark.django_db
def test_existing_capture_session_context_quota_remains_valid(owner):
    session = CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        catalog_version="1.0",
        schema_version="1.0",
        expires_at=timezone.now() + timedelta(days=30),
    )
    quota = AcceleratorLLMQuota.objects.create(
        scope=AcceleratorLLMQuota.Scope.CONTEXT,
        quota_date=timezone.localdate(),
        session=session,
        calls=1,
    )

    assert quota.session == session
    assert quota.process_analysis is None
    assert quota.calls == 1


@pytest.mark.django_db
@override_settings(**VALID_LIMITS)
def test_metadata_logging_does_not_emit_process_source_text(owner, business_unit, caplog):
    sensitive_text = "SEHR-VERTRAULICHER-PROZESSINHALT"
    process = make_process(owner, business_unit)
    process.current_flow = sensitive_text
    process.save(update_fields=["current_flow", "updated_at"])
    prepared = prepare_solution_generation_run(actor=owner, process_analysis_id=process.pk)

    caplog.set_level("INFO", logger="ki_radar.accelerator.solution_generation_service")
    mark_solution_generation_failed(run_id=prepared.run.pk, error_code="test_terminal")

    assert "purpose=solution_generation" in caplog.text
    assert str(process.pk) in caplog.text
    assert sensitive_text not in caplog.text
    assert prepared.source_context.source_hash not in caplog.text
