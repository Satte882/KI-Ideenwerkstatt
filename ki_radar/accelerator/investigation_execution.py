"""Durable product dispatch; the existing run remains the sole execution state."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from .investigation_models import InvestigationRun
from .investigation_runtime import InvestigationRunError, assert_actor_can_edit_run

LEASE_SECONDS = 30
HEARTBEAT_SECONDS = 5
MAX_EXECUTIONS = 2


def pending_execution_state(run, *, now=None):
    """Describe an unclaimed dispatch without pretending that work is running."""
    now = now or timezone.now()
    if not (
        run.status == InvestigationRun.Status.RUNNING
        and run.execution_requested_at
        and run.execution_generation != run.executor_generation
    ):
        return None
    if run.execution_requested_at >= now - timedelta(seconds=LEASE_SECONDS):
        return "pending"
    active_executions = InvestigationRun.objects.filter(
        status=InvestigationRun.Status.RUNNING,
        evidence_campaign__isnull=True,
        execution_generation=F("executor_generation"),
        execution_lease_until__gt=now,
    ).count()
    return "queued" if active_executions >= MAX_EXECUTIONS else "unavailable"


@transaction.atomic
def request_execution(*, actor, handle):
    # Called in the same outer transaction as start/continue. Reused handles do
    # not reset an existing lease or re-dispatch a previously claimed generation.
    run = InvestigationRun.objects.select_for_update().get(pk=handle.run_id)
    assert_actor_can_edit_run(actor, run)
    if run.evidence_campaign_id or run.execution_mode != "adaptive":
        raise InvestigationRunError(
            "Nur Produktuntersuchungen werden beauftragt.", code="invalid_dispatch"
        )
    if run.status != InvestigationRun.Status.RUNNING:
        return
    if run.execution_generation == run.executor_generation or (
        handle.reused and run.execution_requested_at is not None
    ):
        return
    run.execution_requested_at = timezone.now()
    run.execution_requested_by = actor
    run.execution_worker_id = None
    run.execution_lease_until = None
    run.save(
        update_fields=[
            "execution_requested_at",
            "execution_requested_by",
            "execution_worker_id",
            "execution_lease_until",
            "updated_at",
        ]
    )


@transaction.atomic
def claim_execution(worker_id):
    # Serialize the global two-process capacity across supervisor instances.
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [750075])
    now = timezone.now()
    products = InvestigationRun.objects.filter(
        status="running",
        evidence_campaign__isnull=True,
        execution_mode="adaptive",
        execution_requested_at__isnull=False,
    )
    if products.filter(execution_lease_until__gt=now).count() >= MAX_EXECUTIONS:
        return None
    query = (
        products.exclude(execution_generation=F("executor_generation"))
        .filter(
            execution_worker_id__isnull=True,
        )
        .order_by("execution_requested_at")
    )
    run = query.select_for_update().first()
    if run is None:
        return None
    run.execution_generation = run.executor_generation
    run.execution_worker_id = worker_id
    run.execution_lease_until = now + timedelta(seconds=LEASE_SECONDS)
    run.save(
        update_fields=[
            "execution_generation",
            "execution_worker_id",
            "execution_lease_until",
            "updated_at",
        ]
    )
    return run.pk, run.executor_generation


def renew_execution(run_id, generation, worker_id):
    now = timezone.now()
    return (
        InvestigationRun.objects.filter(
            pk=run_id,
            status="running",
            executor_generation=generation,
            execution_generation=generation,
            execution_worker_id=worker_id,
            execution_lease_until__gt=now,
        ).update(execution_lease_until=now + timedelta(seconds=LEASE_SECONDS))
        == 1
    )


@transaction.atomic
def fail_execution(
    run_id, generation, worker_id, code="execution_interrupted", *, only_if_expired=False
):
    """Token-fenced cleanup even if the initiating user's access was revoked."""
    run = InvestigationRun.objects.select_for_update().get(pk=run_id)
    if (
        run.status != "running"
        or run.executor_generation != generation
        or run.execution_generation != generation
        or run.execution_worker_id != worker_id
    ):
        return False
    now = timezone.now()
    if only_if_expired and run.execution_lease_until and run.execution_lease_until > now:
        return False
    run.status = "failed"
    run.finished_at = now
    run.clarification_reason = "technical_failure"
    run.clarification_payload = {
        "error_code": code,
        "impact": (
            "Die Hintergrundausführung wurde unterbrochen. "
            "Es liegt keine bestätigte Entscheidungsgrundlage vor."
        ),
        "required_action": (
            "Hintergrundausführung technisch prüfen und anschließend "
            "aus der Prozessanalyse eine neue Untersuchung starten."
        ),
    }
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.execution_lease_until = None
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "clarification_reason",
            "clarification_payload",
            "executor_generation",
            "executor_token",
            "execution_lease_until",
            "updated_at",
        ]
    )
    run.model_calls.filter(status="running", executor_generation=generation).update(
        status="discarded",
        finished_at=now,
        error_code=code,
    )
    run.steps.filter(status="running", executor_generation=generation).update(
        status="discarded",
        finished_at=now,
        error_code=code,
    )
    return True


def reap_executions():
    expired = InvestigationRun.objects.filter(
        status="running",
        evidence_campaign__isnull=True,
        execution_worker_id__isnull=False,
        execution_lease_until__lte=timezone.now(),
        execution_generation=F("executor_generation"),
    ).values_list("pk", "execution_generation", "execution_worker_id")
    for run_id, generation, worker_id in list(expired):
        fail_execution(run_id, generation, worker_id, only_if_expired=True)


def execution_health():
    now = timezone.now()
    products = InvestigationRun.objects.filter(
        status="running",
        evidence_campaign__isnull=True,
        execution_requested_at__isnull=False,
    )
    pending = products.exclude(execution_generation=F("executor_generation"))
    overdue = pending.filter(
        execution_requested_at__lt=now - timedelta(seconds=LEASE_SECONDS)
    ).count()
    if (
        products.filter(
            execution_generation=F("executor_generation"), execution_lease_until__gt=now
        ).count()
        >= MAX_EXECUTIONS
    ):
        overdue = 0  # An occupied worker pool is legitimate waiting, not a fault.
    orphaned = products.filter(
        execution_generation=F("executor_generation"),
        execution_lease_until__lte=now,
    ).count()
    return {
        "healthy": not (overdue or orphaned),
        "pending": pending.count(),
        "overdue": overdue,
        "orphaned": orphaned,
    }
