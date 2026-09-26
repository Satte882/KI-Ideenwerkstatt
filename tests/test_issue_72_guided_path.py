from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.investigation_models import (
    InvestigationBriefRevision,
    InvestigationEvidenceCampaign,
    InvestigationMaterialization,
    InvestigationRun,
    InvestigationSourceFolder,
)
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import SnapshotRequest, create_source_snapshot
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name="Guided Path"):
    stream = ValueStream.objects.create(
        name=f"{name} Value Stream",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Prüfung startet",
        outcome="Entscheidung ist dokumentiert",
        scope_in="Prüfung bis Entscheidung",
        status=ValueStream.Status.ACTIVE,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Prüfung",
        description="Fall prüfen.",
        actors="Fachbereich",
        systems="Workflow",
        documents="Fallunterlagen",
        pain_points="Unterschiedliche Laufzeiten",
        baseline_metrics="Offen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name=name,
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Fall liegt vor",
        scope_end="Entscheidung liegt vor",
        trigger="Fall wird eingereicht",
        outcome="Nachvollziehbare Entscheidung",
        current_flow="Prüfen und entscheiden.",
        roles="Fachbereich",
        systems="Workflow",
        data_objects="Fallunterlagen",
        business_rules="Keine",
        handoffs="Keine",
        bottlenecks="Unterschiedliche Laufzeiten",
        diagnostic_observations="Laufzeiten schwanken",
        cause_hypotheses="",
        confirmed_causes="",
        constraints="",
        exceptions="",
        baseline_metrics="Offen",
        analyzed_by=owner,
    )


def registered_folder(*, owner, process, root: Path, name="A-Fall"):
    (root / "notes.txt").write_text("Beleg für den Guided Path.", encoding="utf-8")
    return InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name=name,
        root_path=str(root),
        registered_by=owner,
    )


def authorize_snapshot(*, owner, process, folder):
    return create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Welche Ursache und Lösungsrichtung trägt die Evidenz?",
            run_limits={},
        ),
    )


def evidence_campaign(*, owner, process):
    return InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key=f"issue72-{uuid.uuid4().hex}",
        limits={},
        usage={},
        authorized_by=owner,
    )


def start_evidence(*, owner, snapshot, campaign, key="issue72-evidence"):
    return start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.pk,
            idempotency_key=key,
            evidence_campaign_id=campaign.pk,
            evidence_metadata={
                "provider_mode": "stub",
                "phase": "post_fix",
                "variant": "B",
            },
            decision_brief_required=True,
        ),
    )


@pytest.mark.django_db
def test_authorization_is_business_first_and_returns_to_visible_start(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = registered_folder(owner=owner, process=process, root=tmp_path)
    client.force_login(owner)

    authorize_url = reverse("accelerator:investigation_authorize", args=[process.pk])
    response = client.get(authorize_url)
    body = response.content.decode()

    assert response.status_code == 200
    assert "Untersuchungsgrundlage festlegen" in body
    assert 'name="decision_question"' in body
    assert "Editierbar:" in body
    assert "Systemseitige technische Limits anzeigen" in body
    assert "max_model_calls" in body
    assert "keine fachliche Eingabe" in body
    assert "A-Fall" not in body
    assert "Quellenbasis für „Guided Path“" in body

    question = "Welche Ursache ist belegt und welche Lösungsrichtung folgt daraus?"
    response = client.post(
        authorize_url,
        {
            "folder_id": str(folder.pk),
            "decision_question": question,
        },
    )
    assert response.status_code == 302
    assert response["Location"].endswith(f"{process.get_absolute_url()}#evidence-investigation")

    snapshot = process.investigation_source_snapshots.get()
    assert snapshot.folder_id == folder.pk
    assert snapshot.decision_question == question
    assert snapshot.run_limits == {}

    detail = client.get(process.get_absolute_url())
    body = detail.content.decode()
    assert detail.status_code == 200
    assert "Untersuchungsgrundlage autorisiert." in body
    assert question in body
    assert "Quellenbasis für „Guided Path“" in body
    assert "notes.txt" in body
    assert "Untersuchung starten" in body
    assert "Systemseitige technische Limits" in body
    assert "A-Fall" not in body


@pytest.mark.django_db
def test_waiting_evidence_run_does_not_occupy_product_guided_path(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = registered_folder(owner=owner, process=process, root=tmp_path)
    snapshot = authorize_snapshot(owner=owner, process=process, folder=folder)
    campaign = evidence_campaign(owner=owner, process=process)
    evidence_handle = start_evidence(
        owner=owner,
        snapshot=snapshot,
        campaign=campaign,
    )
    InvestigationRun.objects.filter(pk=evidence_handle.run_id).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason="missing_evidence",
        clarification_payload={
            "required_input": "Fehlende Bezugsgröße",
            "impact": "Entscheidung kann sonst nicht belastbar getroffen werden.",
        },
    )
    client.force_login(owner)

    response = client.get(process.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert "Untersuchungsgrundlage autorisiert." in body
    assert "Untersuchung starten" in body
    assert str(evidence_handle.run_id) not in body
    assert "Klärung fortsetzen" not in body

    product_handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.pk,
            idempotency_key="issue72-product",
            decision_brief_required=True,
        ),
    )
    InvestigationRun.objects.filter(pk=product_handle.run_id).update(
        status=InvestigationRun.Status.WAITING_HUMAN,
        clarification_reason="missing_evidence",
        clarification_payload={
            "required_input": "Fachliche Bezugsgröße",
            "impact": "Die Produktuntersuchung wartet auf eine Entscheidung.",
        },
    )

    response = client.get(process.get_absolute_url())
    body = response.content.decode()
    assert response.status_code == 200
    assert "Aktuelle Untersuchung:" in body
    assert "Wartet auf Klärung" in body
    assert "Klärung fortsetzen" in body
    assert str(product_handle.run_id) in body
    assert "Untersuchung starten" not in body


@pytest.mark.django_db
def test_product_and_evidence_active_runs_coexist_but_same_scope_still_blocks(
    owner,
    coordinator,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = registered_folder(owner=owner, process=process, root=tmp_path)
    snapshot = authorize_snapshot(owner=owner, process=process, folder=folder)
    campaign = evidence_campaign(owner=owner, process=process)

    evidence = start_evidence(
        owner=owner,
        snapshot=snapshot,
        campaign=campaign,
        key="issue72-evidence-main",
    )
    evidence_retry = start_evidence(
        owner=owner,
        snapshot=snapshot,
        campaign=campaign,
        key="issue72-evidence-main",
    )
    assert evidence_retry.reused is True
    assert evidence_retry.run_id == evidence.run_id

    product = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.pk,
            idempotency_key="issue72-product-main",
        ),
    )
    product_retry = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot.pk,
            idempotency_key="issue72-product-main",
        ),
    )
    assert product_retry.reused is True
    assert product_retry.run_id == product.run_id

    assert (
        InvestigationRun.objects.filter(
            process_analysis=process,
            status__in=InvestigationRun.ACTIVE_STATUSES,
        ).count()
        == 2
    )

    with pytest.raises(InvestigationRunError) as product_exc:
        start_investigation(
            actor=coordinator,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.pk,
                idempotency_key="issue72-product-second",
            ),
        )
    assert product_exc.value.code == "active_run_exists"
    assert product_exc.value.existing_run_id == product.run_id

    with pytest.raises(InvestigationRunError) as evidence_exc:
        start_evidence(
            owner=coordinator,
            snapshot=snapshot,
            campaign=campaign,
            key="issue72-evidence-second",
        )
    assert evidence_exc.value.code == "active_run_exists"
    assert evidence_exc.value.existing_run_id == evidence.run_id

    with pytest.raises(InvestigationRunError) as scope_exc:
        start_evidence(
            owner=owner,
            snapshot=snapshot,
            campaign=campaign,
            key="issue72-product-main",
        )
    assert scope_exc.value.code == "idempotency_scope_conflict"
    assert scope_exc.value.existing_run_id == product.run_id


@pytest.mark.django_db
def test_masked_benchmark_source_choices_remain_distinguishable_by_snapshot_contents(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit, name="Mehrere Quellen")
    roots = []
    for folder_name, evidence_name in [
        ("A-Fall", "02_counterevidence.md"),
        ("B-Fall", "02_report.md"),
        ("C-Fall", "02_system_note.md"),
    ]:
        root = tmp_path / folder_name
        root.mkdir()
        (root / evidence_name).write_text("Beleg", encoding="utf-8")
        folder = InvestigationSourceFolder.objects.create(
            process_analysis=process,
            name=folder_name,
            root_path=str(root),
            registered_by=owner,
        )
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Welche Richtung ist belegt?",
                run_limits={},
            ),
        )
        roots.append((folder_name, evidence_name))

    client.force_login(owner)
    response = client.get(reverse("accelerator:investigation_authorize", args=[process.pk]))
    body = response.content.decode()

    assert response.status_code == 200
    for folder_name, evidence_name in roots:
        assert folder_name not in body
        assert evidence_name in body
    assert body.count("Quellenbasis für „Mehrere Quellen“") == 3


@pytest.mark.django_db(transaction=True)
def test_parallel_product_and_evidence_starts_use_separate_active_slots(
    owner,
    coordinator,
    business_unit,
    tmp_path,
):
    if connection.vendor != "postgresql":
        pytest.skip("Parallel row-lock semantics are validated on PostgreSQL.")

    process = make_process(owner=owner, business_unit=business_unit, name="Parallel Guided Path")
    folder = registered_folder(owner=owner, process=process, root=tmp_path)
    snapshot = authorize_snapshot(owner=owner, process=process, folder=folder)
    campaign = evidence_campaign(owner=owner, process=process)
    barrier = Barrier(2)

    def attempt(actor_id, evidence_mode):
        close_old_connections()
        from ki_radar.accounts.models import User

        actor = User.objects.get(pk=actor_id)
        barrier.wait()
        try:
            request_kwargs = {
                "snapshot_id": snapshot.pk,
                "idempotency_key": (
                    "issue72-parallel-evidence" if evidence_mode else "issue72-parallel-product"
                ),
            }
            if evidence_mode:
                request_kwargs.update(
                    {
                        "evidence_campaign_id": campaign.pk,
                        "evidence_metadata": {
                            "provider_mode": "stub",
                            "phase": "post_fix",
                            "variant": "B",
                        },
                    }
                )
            handle = start_investigation(
                actor=actor,
                request=StartInvestigationRequest(**request_kwargs),
            )
            return ("created", str(handle.run_id))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda item: attempt(*item),
                [(owner.pk, False), (coordinator.pk, True)],
            )
        )

    assert [result[0] for result in results] == ["created", "created"]
    assert (
        InvestigationRun.objects.filter(
            process_analysis=process,
            status__in=InvestigationRun.ACTIVE_STATUSES,
            evidence_campaign__isnull=True,
        ).count()
        == 1
    )
    assert (
        InvestigationRun.objects.filter(
            process_analysis=process,
            status__in=InvestigationRun.ACTIVE_STATUSES,
            evidence_campaign__isnull=False,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_evidence_materialization_does_not_switch_product_workspace_to_audit_mode(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = registered_folder(owner=owner, process=process, root=tmp_path)
    snapshot = authorize_snapshot(owner=owner, process=process, folder=folder)
    campaign = evidence_campaign(owner=owner, process=process)
    evidence_handle = start_evidence(
        owner=owner,
        snapshot=snapshot,
        campaign=campaign,
        key="issue72-evidence-materialization",
    )
    InvestigationRun.objects.filter(pk=evidence_handle.run_id).update(
        status=InvestigationRun.Status.READY,
        finished_at=timezone.now(),
    )
    run = InvestigationRun.objects.get(pk=evidence_handle.run_id)
    brief = InvestigationBriefRevision.objects.create(
        run=run,
        revision=1,
        payload={},
        content_hash="issue72-brief",
        operation_key="issue72-brief-op",
        process_version=process.version,
    )
    InvestigationMaterialization.objects.create(
        run=run,
        brief_revision=brief,
        operation_key="issue72-materialization-op",
        outcome=InvestigationMaterialization.Outcome.APPLIED,
        base_domain_hash="issue72-base",
        resulting_domain_hash="issue72-result",
        materialized_by=owner,
    )
    client.force_login(owner)

    response = client.get(process.get_absolute_url())
    body = response.content.decode()

    assert response.status_code == 200
    assert "Der fachliche Kern wurde bereits übernommen." not in body
    assert "Evidenzgestützte Vertiefung" in body
    assert "Untersuchung starten" in body
