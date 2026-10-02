from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse

from ki_radar.accelerator.investigation_models import InvestigationRun, InvestigationSourceFolder
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    start_investigation,
)
from ki_radar.accelerator.investigation_tools import (
    InvestigationToolError,
    SnapshotRequest,
    create_source_snapshot,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name="Issue 117 activation"):
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
        pain_points="Manuelle Zuordnung",
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
        business_rules="Fallbezogene Prüfung",
        handoffs="Keine",
        bottlenecks="Manuelle Zuordnung",
        diagnostic_observations="Explizite Zuordnung erforderlich",
        cause_hypotheses="",
        confirmed_causes="",
        constraints="",
        exceptions="",
        baseline_metrics="Offen",
        analyzed_by=owner,
    )


def register_csv_folder(*, owner, process, root: Path):
    (root / "cases.csv").write_text(
        "case_id,decision\nE01,standard\nE02,manual_review\nE03,manual_review\n",
        encoding="utf-8",
    )
    return InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Fallquellen",
        root_path=str(root),
        registered_by=owner,
    )


def mapping_spec(*, case_keys=("E01", "E02", "E03")):
    return {
        "source_filename": "cases.csv",
        "case_key_column": "case_id",
        "case_keys": list(case_keys),
        "mapping_dimension": "review routing",
        "exhaustive": True,
    }


def create_mapping_snapshot(*, owner, process, folder, specs=None):
    return create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Ordne alle autorisierten Fälle einem Prüfpfad zu.",
            run_limits={},
            structured_mapping_specs=tuple(specs if specs is not None else (mapping_spec(),)),
        ),
    )


@pytest.mark.django_db
def test_snapshot_mapping_spec_auto_activates_normal_run_start(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)
    snapshot_result = create_mapping_snapshot(owner=owner, process=process, folder=folder)

    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot_result.snapshot_id,
            idempotency_key="issue117-snapshot-auto-activation",
            decision_brief_required=True,
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    obligations = run.execution_snapshot["structured_mapping_obligations"]

    assert len(obligations) == 1
    obligation = obligations[0]
    assert obligation["case_keys"] == ["E01", "E02", "E03"]
    assert obligation["case_key_column"] == "case_id"
    assert obligation["mapping_dimension"] == "review routing"
    assert obligation["exhaustive"] is True
    assert obligation["snapshot_id"] == str(run.source_snapshot_id)
    assert obligation["manifest_hash"] == run.manifest_hash
    source = run.source_snapshot.sources.get(filename="cases.csv")
    assert obligation["source_id"] == str(source.pk)
    assert obligation["source_revision_hash"] == source.content_sha256


@pytest.mark.django_db
def test_snapshot_mapping_contract_rejects_request_override(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)
    snapshot_result = create_mapping_snapshot(owner=owner, process=process, folder=folder)
    snapshot = process.investigation_source_snapshots.get(pk=snapshot_result.snapshot_id)
    source = snapshot.sources.get(filename="cases.csv")
    frozen = snapshot.process_context["structured_mapping_specs"][0]

    with pytest.raises(InvestigationRunError) as exc_info:
        start_investigation(
            actor=owner,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.pk,
                idempotency_key="issue117-conflicting-override",
                structured_mapping_obligations=(
                    {
                        "obligation_id": frozen["obligation_id"],
                        "source_id": str(source.pk),
                        "case_key_column": "case_id",
                        "case_keys": ["E01", "E02"],
                        "mapping_dimension": "review routing",
                        "exhaustive": True,
                    },
                ),
            ),
        )

    assert exc_info.value.code == "snapshot_mapping_contract_conflict"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "spec",
    [
        {
            "source_filename": "missing.csv",
            "case_key_column": "case_id",
            "case_keys": ["E01"],
            "mapping_dimension": "routing",
            "exhaustive": True,
        },
        {
            "source_filename": "cases.csv",
            "case_key_column": "missing_column",
            "case_keys": ["E01"],
            "mapping_dimension": "routing",
            "exhaustive": True,
        },
        {
            "source_filename": "cases.csv",
            "case_key_column": "case_id",
            "case_keys": ["E01", "E01"],
            "mapping_dimension": "routing",
            "exhaustive": True,
        },
        {
            "source_filename": "cases.csv",
            "case_key_column": "case_id",
            "case_keys": ["E99"],
            "mapping_dimension": "routing",
            "exhaustive": True,
        },
    ],
)
def test_invalid_snapshot_mapping_specs_fail_before_authorization(
    owner,
    business_unit,
    tmp_path,
    spec,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)

    with pytest.raises(InvestigationToolError) as exc_info:
        create_mapping_snapshot(owner=owner, process=process, folder=folder, specs=(spec,))

    assert exc_info.value.code == "invalid_structured_mapping_spec"
    assert process.investigation_source_snapshots.count() == 0


@pytest.mark.django_db
def test_snapshot_without_mapping_spec_keeps_existing_product_path(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)
    snapshot_result = create_mapping_snapshot(
        owner=owner,
        process=process,
        folder=folder,
        specs=(),
    )

    handle = start_investigation(
        actor=owner,
        request=StartInvestigationRequest(
            snapshot_id=snapshot_result.snapshot_id,
            idempotency_key="issue117-no-mapping-spec",
        ),
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)

    assert run.source_snapshot.process_context["structured_mapping_specs"] == []
    assert run.execution_snapshot["structured_mapping_obligations"] == []


@pytest.mark.django_db
def test_authorization_ui_freezes_explicit_mapping_scope(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:investigation_authorize", kwargs={"process_pk": process.pk}),
        {
            "folder_id": str(folder.pk),
            "decision_question": "Ordne alle Fälle einem Prüfpfad zu.",
            "mapping_source_filename": "cases.csv",
            "mapping_case_key_column": "case_id",
            "mapping_dimension": "review routing",
            "mapping_case_keys": "E01\nE02, E03",
        },
    )

    assert response.status_code == 302
    snapshot = process.investigation_source_snapshots.latest("created_at")
    specs = snapshot.process_context["structured_mapping_specs"]
    assert len(specs) == 1
    spec = specs[0]
    assert spec["source_filename"] == "cases.csv"
    assert spec["case_keys"] == ["E01", "E02", "E03"]
    assert spec["case_key_column"] == "case_id"
    assert spec["mapping_dimension"] == "review routing"
    source = snapshot.sources.get(filename="cases.csv")
    assert spec["source_content_sha256"] == source.content_sha256
    assert "value" not in spec


@pytest.mark.django_db
def test_authorization_ui_rejects_partial_mapping_scope(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    folder = register_csv_folder(owner=owner, process=process, root=tmp_path)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:investigation_authorize", kwargs={"process_pk": process.pk}),
        {
            "folder_id": str(folder.pk),
            "decision_question": "Ordne alle Fälle einem Prüfpfad zu.",
            "mapping_source_filename": "cases.csv",
            "mapping_case_key_column": "case_id",
            "mapping_dimension": "",
            "mapping_case_keys": "E01\nE02",
        },
    )

    assert response.status_code == 200
    assert process.investigation_source_snapshots.count() == 0
    assert "gemeinsam angegeben" in response.content.decode("utf-8")
