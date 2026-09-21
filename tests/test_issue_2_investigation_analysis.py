from __future__ import annotations

from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from ki_radar.accelerator.investigation_models import (
    InvestigationSourceFolder,
    InvestigationToolResult,
)
from ki_radar.accelerator.investigation_tools import (
    CompareGroupsRequest,
    CsvProfileRequest,
    FilterSpec,
    InvestigationToolError,
    SnapshotRequest,
    compare_groups,
    create_source_snapshot,
    get_tool_result,
    list_sources,
    profile_csv,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name="Analysefall"):
    stream = ValueStream.objects.create(
        name=f"{name} Value Stream",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Prüfung startet",
        outcome="Entscheidung ist nachvollziehbar",
        scope_in="Prüfung bis Entscheidung",
        status=ValueStream.Status.ACTIVE,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Prüfung",
        description="Fälle prüfen.",
        actors="Fachbereich",
        systems="Workflow",
        documents="Berichte",
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
        data_objects="Berichte",
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


def snapshot_for_root(*, owner, process, root: Path, name="Analysequellen"):
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name=name,
        root_path=str(root),
        registered_by=owner,
    )
    created = create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Welche Unterschiede sind im Bestand belegt?",
            run_limits={"max_tool_calls": 10},
        ),
    )
    return folder, created


def source_by_name(*, owner, snapshot_id, filename):
    sources = list_sources(actor=owner, snapshot_id=snapshot_id).sources
    return next(source for source in sources if source.filename == filename)


@pytest.mark.django_db
def test_profile_csv_reports_types_missing_values_and_duplicates(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "profile.csv").write_text(
        "group,value,note\nA,10,ok\nA,,missing\nB,oops,text\nA,10,ok\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = source_by_name(
        owner=owner,
        snapshot_id=snapshot.snapshot_id,
        filename="profile.csv",
    )

    result = profile_csv(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=CsvProfileRequest(source_id=source.source_id),
    )

    assert result.row_count == 4
    assert result.duplicate_rows == 1
    assert result.columns["value"]["missing"] == 1
    assert result.columns["value"]["type"] == "mixed"
    assert any("gemischte Typen" in finding for finding in result.findings)
    assert any("Dublettenzeilen" in finding for finding in result.findings)

    stored = InvestigationToolResult.objects.get(pk=result.result_id)
    assert stored.source_hash == source.content_sha256
    assert stored.tool_version == "vs1-source-tools-v1"
    assert stored.population["rows_total"] == 4
    assert stored.missing_values["value"] == 1


@pytest.mark.django_db
def test_compare_groups_matches_manual_values_and_null_is_not_zero(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "compare.csv").write_text(
        "group,value,unit,scope\n"
        "A,10,h,keep\n"
        "A,20,h,keep\n"
        "A,,h,keep\n"
        "B,30,h,keep\n"
        "B,50,h,keep\n"
        "B,oops,h,keep\n"
        "B,99,h,drop\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = source_by_name(
        owner=owner,
        snapshot_id=snapshot.snapshot_id,
        filename="compare.csv",
    )
    request = CompareGroupsRequest(
        source_id=source.source_id,
        group_by="group",
        aggregation="mean",
        value_column="value",
        filters=(FilterSpec(column="scope", operator="eq", value="keep"),),
        unit_column="unit",
    )

    first = compare_groups(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=request,
    )
    second = compare_groups(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=request,
    )

    groups = {group["group"]: group for group in first.groups}
    assert groups["A"] == {"group": "A", "value": "15", "population": 2}
    assert groups["B"] == {"group": "B", "value": "40", "population": 2}
    assert first.population["rows_total"] == 7
    assert first.population["filter_matched_rows"] == 6
    assert len(first.population["aggregated_rows"]) == 4
    assert {"row": 3, "reason": "missing_value"} in first.excluded_rows
    assert {"row": 6, "reason": "non_numeric_value"} in first.excluded_rows
    assert first.missing_values["value"] == 1
    assert first.units == {"column": "unit", "values": ["h"], "missing_rows": []}
    assert any(item["delta"] == "25" for item in first.differences)
    assert any(
        "nicht automatisch Kausalität" in value
        for value in [
            InvestigationToolResult.objects.get(pk=first.result_id).result_payload["causality_note"]
        ]
    )

    assert first.groups == second.groups
    assert first.differences == second.differences
    assert first.population == second.population
    assert first.excluded_rows == second.excluded_rows
    assert first.result_id != second.result_id


@pytest.mark.django_db
def test_units_conflict_missing_units_empty_groups_and_missing_columns_are_findings(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "units.csv").write_text(
        "group,value,unit\nA,10,h\nB,20,min\nC,30,\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = source_by_name(
        owner=owner,
        snapshot_id=snapshot.snapshot_id,
        filename="units.csv",
    )

    conflict = compare_groups(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source.source_id,
            group_by="group",
            aggregation="mean",
            value_column="value",
            unit_column="unit",
        ),
    )

    assert conflict.groups == ()
    assert any("Einheitenkonflikt" in finding for finding in conflict.findings)
    assert any("keine eindeutige Einheit" in finding for finding in conflict.findings)

    empty = compare_groups(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source.source_id,
            group_by="group",
            aggregation="count",
            filters=(FilterSpec(column="group", operator="eq", value="Z"),),
        ),
    )
    assert empty.groups == ()
    assert any("Leere Vergleichspopulation" in finding for finding in empty.findings)

    with pytest.raises(InvestigationToolError) as exc_info:
        compare_groups(
            actor=owner,
            snapshot_id=snapshot.snapshot_id,
            request=CompareGroupsRequest(
                source_id=source.source_id,
                group_by="unknown",
                aggregation="count",
            ),
        )
    assert exc_info.value.code == "missing_column"


@pytest.mark.django_db
def test_numeric_filter_type_errors_are_excluded_not_coerced(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "filters.csv").write_text(
        "group,value,threshold\nA,10,5\nA,20,unknown\nB,30,15\n",
        encoding="utf-8",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = source_by_name(
        owner=owner,
        snapshot_id=snapshot.snapshot_id,
        filename="filters.csv",
    )

    result = compare_groups(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source.source_id,
            group_by="group",
            aggregation="sum",
            value_column="value",
            filters=(FilterSpec(column="threshold", operator="gt", value=10),),
        ),
    )

    assert {"row": 2, "reason": "filter_type_error"} in result.excluded_rows
    assert any("nichtnumerischer Filterwerte" in finding for finding in result.findings)
    assert result.groups == ({"group": "B", "value": "30", "population": 1},)


@pytest.mark.django_db
def test_revocation_blocks_stored_result_retrieval_and_result_mutation(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "data.csv").write_text(
        "group,value\nA,1\nB,2\n",
        encoding="utf-8",
    )
    folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = source_by_name(
        owner=owner,
        snapshot_id=snapshot.snapshot_id,
        filename="data.csv",
    )
    result = profile_csv(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=CsvProfileRequest(source_id=source.source_id),
    )

    stored = get_tool_result(actor=owner, result_id=result.result_id)
    assert stored.source_hash == source.content_sha256

    model = InvestigationToolResult.objects.get(pk=result.result_id)
    model.parameters = {"changed": True}
    with pytest.raises(ValidationError):
        model.save()
    with pytest.raises(ValidationError):
        InvestigationToolResult.objects.filter(pk=model.pk).delete()

    folder.is_active = False
    folder.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(PermissionDenied):
        get_tool_result(actor=owner, result_id=result.result_id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("pack", "filename"),
    [
        ("A", "cases.csv"),
        ("B", "cases.csv"),
        ("C", "cases.csv"),
    ],
)
def test_source_packs_are_directly_executable_without_expected_answers_in_room(
    owner,
    business_unit,
    pack,
    filename,
):
    fixture_root = Path(__file__).parent / "fixtures"
    root = fixture_root / "investigation_source_packs" / pack
    process = make_process(
        owner=owner,
        business_unit=business_unit,
        name=f"Fixture {pack}",
    )
    _folder, snapshot = snapshot_for_root(
        owner=owner,
        process=process,
        root=root,
        name=f"Pack {pack}",
    )
    names = {
        source.filename
        for source in list_sources(
            actor=owner,
            snapshot_id=snapshot.snapshot_id,
        ).sources
    }

    assert filename in names
    assert "investigation_expected_v1.json" not in names


@pytest.mark.django_db
def test_pack_a_b_c_expected_numeric_characteristics(
    owner,
    business_unit,
):
    fixture_root = Path(__file__).parent / "fixtures" / "investigation_source_packs"

    process_a = make_process(owner=owner, business_unit=business_unit, name="Pack A")
    _folder_a, snapshot_a = snapshot_for_root(
        owner=owner,
        process=process_a,
        root=fixture_root / "A",
        name="Pack A",
    )
    source_a = source_by_name(
        owner=owner,
        snapshot_id=snapshot_a.snapshot_id,
        filename="cases.csv",
    )
    comparison_a = compare_groups(
        actor=owner,
        snapshot_id=snapshot_a.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source_a.source_id,
            group_by="approver_available",
            aggregation="mean",
            value_column="approval_hours",
            unit_column="unit",
        ),
    )
    groups_a = {item["group"]: item for item in comparison_a.groups}
    assert groups_a["yes"]["value"] == "5"
    assert groups_a["no"]["value"] == "29.5"
    assert groups_a["yes"]["population"] == 2
    assert groups_a["no"]["population"] == 2

    process_b = make_process(owner=owner, business_unit=business_unit, name="Pack B")
    _folder_b, snapshot_b = snapshot_for_root(
        owner=owner,
        process=process_b,
        root=fixture_root / "B",
        name="Pack B",
    )
    source_b = source_by_name(
        owner=owner,
        snapshot_id=snapshot_b.snapshot_id,
        filename="cases.csv",
    )
    profile_b = profile_csv(
        actor=owner,
        snapshot_id=snapshot_b.snapshot_id,
        request=CsvProfileRequest(source_id=source_b.source_id),
    )
    assert profile_b.columns["total_eligible"]["missing"] == 3
    assert profile_b.columns["total_eligible"]["type"] == "empty"

    process_c = make_process(owner=owner, business_unit=business_unit, name="Pack C")
    _folder_c, snapshot_c = snapshot_for_root(
        owner=owner,
        process=process_c,
        root=fixture_root / "C",
        name="Pack C",
    )
    source_c = source_by_name(
        owner=owner,
        snapshot_id=snapshot_c.snapshot_id,
        filename="cases.csv",
    )
    comparison_c = compare_groups(
        actor=owner,
        snapshot_id=snapshot_c.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source_c.source_id,
            group_by="queue_retries",
            aggregation="mean",
            value_column="approval_hours",
            unit_column="unit",
        ),
    )
    groups_c = {item["group"]: item for item in comparison_c.groups}
    assert groups_c["0"]["value"] == "5.5"
    assert groups_c["4"]["value"] == "23"
    assert groups_c["5"]["value"] == "27"
