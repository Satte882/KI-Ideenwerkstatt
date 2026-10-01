from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.investigation_activity import build_activity
from ki_radar.accelerator.investigation_execution import (
    claim_execution,
    execution_health,
    fail_execution,
    reap_executions,
    renew_execution,
    request_execution,
)
from ki_radar.accelerator.investigation_models import InvestigationModelCall, InvestigationRun
from ki_radar.accelerator.investigation_runtime import (
    StartInvestigationRequest,
    abort_investigation,
    execute_tool_step,
    start_investigation,
)
from tests.test_issue_3_investigation_runtime import make_process, snapshot_for_root


@pytest.fixture
def product(owner, business_unit, tmp_path):
    process = make_process(owner=owner, business_unit=business_unit, name="Live Untersuchung")
    (tmp_path / "notes.txt").write_text("Freigabedauer ist noch unbekannt.", encoding="utf-8")
    _, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
    return process, snapshot


def start(owner, product, *, dispatch=True):
    _, snapshot = product
    with transaction.atomic():
        handle = start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.snapshot_id,
                idempotency_key="live-start",
                decision_brief_required=True,
            ),
        )
        if dispatch:
            request_execution(actor=owner, handle=handle)
    return handle


def model_call(run, role="planner", **kwargs):
    return InvestigationModelCall.objects.create(
        run=run,
        role=role,
        executor_generation=run.executor_generation,
        prompt_version="test",
        prompt_hash="a" * 64,
        instruction_template="PRIVATE PROMPT",
        schema_version="test",
        **kwargs,
    )


@pytest.mark.django_db
def test_start_commits_dispatch_and_immediately_opens_live_page(
    client, owner, product, monkeypatch
):
    def forbidden(**kwargs):
        raise AssertionError("Web request must never call a provider")

    monkeypatch.setattr("ki_radar.accelerator.investigation_loop.run_until_boundary", forbidden)
    client.force_login(owner)
    response = client.post(
        reverse("accelerator:investigation_start", args=[product[0].pk]),
        {"idempotency_key": "live-ui"},
    )
    run = InvestigationRun.objects.get()
    assert response.url == reverse("accelerator:investigation_activity", args=[run.pk])
    assert run.execution_requested_at and run.execution_requested_by == owner
    assert run.model_calls.count() == 0
    page = client.get(response.url)
    assert page.status_code == 200
    assert "Untersuchungsstart angefordert" in page.content.decode()
    assert "Untersuchung läuft" not in page.content.decode()
    assert "Hintergrundausführung wird zugewiesen" in page.content.decode()
    response = client.post(
        reverse("accelerator:investigation_start", args=[product[0].pk]),
        {"idempotency_key": "live-ui"},
    )
    assert InvestigationRun.objects.count() == 1
    assert response.url.endswith("/activity/")


@pytest.mark.django_db
def test_overdue_unclaimed_dispatch_is_an_actionable_technical_blocker(client, owner, product):
    handle = start(owner, product)
    now = timezone.now()
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        execution_requested_at=now - timedelta(seconds=31)
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    activity = build_activity(run, now=now)

    assert activity["execution_state"] == "unavailable"
    assert activity["attention_required"] is True
    assert activity["attention_title"] == "Hintergrundausführung nicht verfügbar"
    assert "keine bestätigte Analyse" in activity["description"]
    assert "nicht erneut" in activity["required_action"]
    assert activity["duration_label"] == "Wartezeit seit Startanforderung"

    client.force_login(owner)
    page = client.get(reverse("accelerator:investigation_activity", args=[run.pk]))
    content = page.content.decode()
    assert page.status_code == 200
    assert "Hintergrundausführung nicht verfügbar" in content
    assert "keine bestätigte Analyse" in content
    assert "Wartezeit seit Startanforderung" in content


@pytest.mark.django_db
def test_dispatch_rolls_back_with_start(owner, product):
    with pytest.raises(RuntimeError), transaction.atomic():
        start(owner, product)
        raise RuntimeError("transaction interrupted")
    assert not InvestigationRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("age,state", [(29, "pending"), (30, "pending"), (31, "unavailable")])
def test_assignment_boundary_never_claims_running_analysis(owner, product, age, state):
    handle = start(owner, product)
    now = timezone.now()
    InvestigationRun.objects.filter(pk=handle.run_id).update(
        execution_requested_at=now - timedelta(seconds=age)
    )
    activity = build_activity(InvestigationRun.objects.get(pk=handle.run_id), now=now)
    assert activity["execution_state"] == state
    assert "läuft" not in activity["title"]
    assert "läuft im Hintergrund" not in activity["description"]


@pytest.mark.django_db
def test_running_title_requires_current_generation_and_unexpired_lease(owner, product):
    handle = start(owner, product)
    claim_execution(uuid.uuid4())
    run = InvestigationRun.objects.get(pk=handle.run_id)
    now = timezone.now()
    assert build_activity(run, now=now)["title"] == "Untersuchung läuft"
    run.execution_lease_until = now
    assert build_activity(run, now=now)["execution_state"] == "unconfirmed"
    assert "läuft" not in build_activity(run, now=now)["title"]
    run.execution_lease_until = now + timedelta(seconds=30)
    run.executor_generation += 1
    activity = build_activity(run, now=now)
    assert activity["execution_state"] == "pending"
    assert "läuft" not in activity["title"]


@pytest.mark.django_db
def test_claim_fencing_reuse_and_browser_independence(owner, product):
    handle = start(owner, product)
    worker = uuid.uuid4()
    assert claim_execution(worker) == (handle.run_id, handle.executor_generation)
    assert claim_execution(uuid.uuid4()) is None
    assert renew_execution(handle.run_id, handle.executor_generation, worker)
    assert not renew_execution(handle.run_id, handle.executor_generation, uuid.uuid4())
    start(owner, product)
    run = InvestigationRun.objects.get()
    assert run.execution_worker_id == worker
    abort_investigation(actor=owner, run_id=run.pk)
    assert not fail_execution(run.pk, handle.executor_generation, worker)
    assert not renew_execution(run.pk, handle.executor_generation, worker)
    run.refresh_from_db()
    assert run.status == "aborted"


@pytest.mark.django_db
def test_orphan_is_failed_without_replay(owner, product):
    handle = start(owner, product)
    worker = uuid.uuid4()
    claim_execution(worker)
    run = InvestigationRun.objects.get()
    call = model_call(run)
    run.execution_lease_until = timezone.now() - timedelta(seconds=1)
    run.save(update_fields=["execution_lease_until"])
    assert execution_health()["orphaned"] == 1
    assert build_activity(run)["execution_state"] == "unconfirmed"
    reap_executions()
    run.refresh_from_db()
    call.refresh_from_db()
    assert run.status == "failed" and run.finished_at
    assert run.executor_generation > handle.executor_generation
    assert call.status == "discarded"
    assert claim_execution(worker) is None
    assert not any(item["status"] == "running" for item in build_activity(run)["entries"])


@pytest.mark.django_db
def test_stale_reaper_observation_does_not_fail_renewed_execution(owner, product):
    handle = start(owner, product)
    worker = uuid.uuid4()
    claim_execution(worker)
    assert renew_execution(handle.run_id, handle.executor_generation, worker)
    assert not fail_execution(
        handle.run_id, handle.executor_generation, worker, only_if_expired=True
    )
    assert InvestigationRun.objects.get().status == "running"


@pytest.mark.django_db(transaction=True)
def test_worker_command_executes_only_claimed_generation(owner, product, monkeypatch):
    handle = start(owner, product)
    worker = uuid.uuid4()
    claim_execution(worker)
    calls = []

    def boundary(**kwargs):
        calls.append(kwargs["run_id"])
        InvestigationRun.objects.filter(pk=kwargs["run_id"]).update(status="waiting_human")

    monkeypatch.setattr(
        "ki_radar.accelerator.management.commands.run_investigation_worker.run_until_boundary",
        boundary,
    )
    call_command(
        "run_investigation_worker",
        run_id=str(handle.run_id),
        generation=handle.executor_generation,
        worker_id=str(uuid.uuid4()),
    )
    assert not calls
    call_command(
        "run_investigation_worker",
        run_id=str(handle.run_id),
        generation=handle.executor_generation,
        worker_id=str(worker),
    )
    assert calls == [handle.run_id]
    assert InvestigationRun.objects.get().status == "waiting_human"


@pytest.mark.django_db(transaction=True)
def test_worker_revoked_actor_is_a_technical_failure(owner, product):
    handle = start(owner, product)
    worker = uuid.uuid4()
    claim_execution(worker)
    owner.is_active = False
    owner.save(update_fields=["is_active"])
    call_command(
        "run_investigation_worker",
        run_id=str(handle.run_id),
        generation=handle.executor_generation,
        worker_id=str(worker),
    )
    assert InvestigationRun.objects.get().status == "failed"


@pytest.mark.django_db
def test_global_capacity_is_two_products(owner, business_unit, tmp_path):
    handles = []
    (tmp_path / "notes.txt").write_text("Beleg", encoding="utf-8")
    for index in range(3):
        process = make_process(owner=owner, business_unit=business_unit, name=f"Kapazität {index}")
        _, snapshot = snapshot_for_root(owner=owner, process=process, root=tmp_path)
        handles.append(start(owner, (process, snapshot)))
    assert claim_execution(uuid.uuid4())
    assert claim_execution(uuid.uuid4())
    assert claim_execution(uuid.uuid4()) is None
    InvestigationRun.objects.filter(execution_worker_id__isnull=True).update(
        execution_requested_at=timezone.now() - timedelta(seconds=60)
    )
    waiting_run = InvestigationRun.objects.get(execution_worker_id__isnull=True)
    assert build_activity(waiting_run)["execution_state"] == "queued"
    assert build_activity(waiting_run)["title"] == "Untersuchung wartet auf freien Ausführungsplatz"
    assert execution_health() == {"healthy": True, "pending": 1, "overdue": 0, "orphaned": 0}


@pytest.mark.django_db
def test_unrequested_run_is_never_claimed(owner, product):
    start(owner, product, dispatch=False)
    assert claim_execution(uuid.uuid4()) is None


@pytest.mark.django_db
def test_live_projection_includes_active_calls_and_repeated_work(owner, product):
    handle = start(owner, product)
    claim_execution(uuid.uuid4())
    run = InvestigationRun.objects.get()
    first = model_call(run, "synthesizer", status="success", finished_at=timezone.now())
    second = model_call(run, "verifier", status="success", finished_at=timezone.now())
    third = model_call(run, "synthesizer")
    activity = build_activity(run)
    assert activity["execution_state"] == "confirmed"
    entries = {item["id"]: item for item in activity["entries"]}
    assert entries[f"call-{first.pk}"]["label"] == "Decision Brief erstellt"
    assert entries[f"call-{second.pk}"]["label"] == "Prüfung durchgeführt"
    assert entries[f"call-{third.pk}"]["status"] == "running"
    assert entries[f"call-{third.pk}"]["label"] == "Decision Brief wird aktualisiert"
    assert not activity["ready"] and activity["brief_url"] is None
    assert "PRIVATE PROMPT" not in str(activity)
    abort_investigation(actor=owner, run_id=handle.run_id)
    run.refresh_from_db()
    assert not any(item["status"] == "running" for item in build_activity(run)["entries"])


@pytest.mark.django_db
def test_status_endpoints_scope_cache_and_terminal_states(client, owner, reader, product):
    handle = start(owner, product)
    url = reverse("accelerator:investigation_activity_status", args=[handle.run_id])
    client.force_login(reader)
    assert client.get(url).status_code == 403
    client.force_login(owner)
    response = client.get(url)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "executor_token" not in response.content.decode()
    run = InvestigationRun.objects.get()
    run.status = "ready"
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at"])
    response = client.get(url)
    assert not response.json()["ready"]  # READY flag alone is never enough.
    assert response.json()["brief_url"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["failed", "aborted", "waiting_human"])
def test_boundaries_stop_all_activity_and_use_product_language(owner, product, status):
    start(owner, product)
    claim_execution(uuid.uuid4())
    run = InvestigationRun.objects.get()
    model_call(run)
    run.status = status
    if status != "waiting_human":
        run.finished_at = timezone.now()
    run.clarification_payload = {
        "impact": "Planner-/Schema-Vertrag wurde verletzt.",
        "required_action": "Planner-/Loop-Verhalten technisch prüfen.",
    }
    run.save(update_fields=["status", "finished_at", "clarification_payload"])
    activity = build_activity(run)
    assert not any(entry["status"] == "running" for entry in activity["entries"])
    assert not activity["ready"]
    if status == "failed":
        assert "Planner" not in activity["impact"]
        assert "Planner" not in activity["required_action"]


@pytest.mark.django_db
def test_clarification_continues_same_run_with_new_generation(client, owner, product):
    handle = start(owner, product)
    worker = uuid.uuid4()
    claim_execution(worker)
    run = InvestigationRun.objects.get()
    run.status = "waiting_human"
    run.clarification_reason = "missing_evidence"
    run.clarification_payload = {"question": "Welcher Zeitraum?", "needed_evidence": "Messzeitraum"}
    run.save(update_fields=["status", "clarification_reason", "clarification_payload"])
    client.force_login(owner)
    response = client.get(reverse("accelerator:investigation_activity", args=[run.pk]))
    assert "Welcher Zeitraum?" in response.content.decode()
    response = client.post(
        reverse("accelerator:investigation_continue", args=[run.pk]), {"answer": "September"}
    )
    assert response.url.endswith("/activity/")
    run.refresh_from_db()
    assert run.status == "running" and run.input_revisions.count() == 1
    assert run.execution_generation != run.executor_generation
    assert claim_execution(uuid.uuid4()) == (run.pk, run.executor_generation)
    assert not fail_execution(run.pk, handle.executor_generation, worker)
    assert "Klärung beantwortet" in [item["label"] for item in build_activity(run)["entries"]]


@pytest.mark.django_db
def test_tool_retry_preserves_attempt_duration_and_failure(owner, product, monkeypatch):
    from ki_radar.accelerator.investigation_runtime import InvestigationRunError

    handle = start(owner, product)
    calls = 0

    def tool(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InvestigationRunError(
                "Source temporarily unreadable", code="source_path_unreadable"
            )
        return {"sources": []}

    monkeypatch.setattr("ki_radar.accelerator.investigation_runtime.run_tool", tool)
    params = dict(
        actor=owner,
        run_id=handle.run_id,
        executor_token=handle.executor_token,
        tool_name="list_sources",
        parameters={},
    )
    with pytest.raises(InvestigationRunError):
        execute_tool_step(**params)
    run = InvestigationRun.objects.get()
    first_finished = run.steps.get().finished_at
    execute_tool_step(**params)
    step = run.steps.get()
    assert step.attempts == 2 and len(step.attempt_history) == 2
    assert step.attempt_history[0]["finished_at"] == first_finished.isoformat()
    entries = [entry for entry in build_activity(run)["entries"] if entry["id"].startswith("step-")]
    assert [entry["status"] for entry in entries] == ["failed", "success"]
    assert len({entry["id"] for entry in entries}) == 2


@pytest.mark.django_db(transaction=True)
def test_two_supervisors_cannot_claim_same_product(owner, product):
    if connection.vendor != "postgresql":
        pytest.skip("Real PostgreSQL row/advisory locks required")
    start(owner, product)
    barrier = Barrier(2)

    def claim():
        close_old_connections()
        barrier.wait()
        try:
            return claim_execution(uuid.uuid4())
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(result is not None for result in results) == 1


def test_activity_client_opens_brief_only_on_running_to_ready_transition():
    script = Path("static/js/investigation-activity.js").read_text(encoding="utf-8")
    assert 'state.status === "running" && next.status === "ready"' in script
    assert "next.ready && next.brief_url" in script
    assert "window.location.assign(next.brief_url)" in script
    assert "next.attention_required" in script
    assert "next.duration_label" in script
