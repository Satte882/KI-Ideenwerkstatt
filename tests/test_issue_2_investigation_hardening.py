from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied

from ki_radar.accelerator.investigation_models import InvestigationSourceFolder
from ki_radar.accelerator.investigation_tools import (
    MAX_FILES,
    MAX_TOTAL_BYTES,
    CompareGroupsRequest,
    CsvProfileRequest,
    InvestigationToolError,
    ReadRequest,
    SearchRequest,
    SnapshotRequest,
    compare_groups,
    create_source_snapshot,
    list_sources,
    profile_csv,
    read_source,
    search_sources,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit, name="Hardening-Fall"):
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


def register_and_snapshot(*, owner, process, root: Path, name="Hardening-Quellen"):
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name=name,
        root_path=str(root),
        registered_by=owner,
    )
    snapshot = create_source_snapshot(
        actor=owner,
        request=SnapshotRequest(
            process_analysis_id=process.pk,
            folder_id=folder.pk,
            decision_question="Welche Aussage ist im freigegebenen Bestand belegt?",
            run_limits={"max_tool_calls": 10},
        ),
    )
    return folder, snapshot


@pytest.mark.django_db
def test_revocation_between_read_pages_blocks_read_search_and_analysis(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "data.csv").write_text(
        "group,value,unit,note\nA,1,h,needle\nA,2,h,needle\nB,3,h,needle\n",
        encoding="utf-8",
    )
    folder, snapshot = register_and_snapshot(
        owner=owner,
        process=process,
        root=tmp_path,
    )
    source = list_sources(actor=owner, snapshot_id=snapshot.snapshot_id).sources[0]

    first_page = read_source(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=ReadRequest(source_id=source.source_id, limit=1),
    )
    assert first_page.next_cursor == 1

    search_before = search_sources(
        actor=owner,
        snapshot_id=snapshot.snapshot_id,
        request=SearchRequest(query="needle", limit=1),
    )
    assert search_before.next_cursor == 1

    folder.is_active = False
    folder.save(update_fields=["is_active", "updated_at"])

    with pytest.raises(PermissionDenied):
        read_source(
            actor=owner,
            snapshot_id=snapshot.snapshot_id,
            request=ReadRequest(
                source_id=source.source_id,
                cursor=first_page.next_cursor,
                limit=1,
            ),
        )
    with pytest.raises(PermissionDenied):
        search_sources(
            actor=owner,
            snapshot_id=snapshot.snapshot_id,
            request=SearchRequest(
                query="needle",
                cursor=search_before.next_cursor,
                limit=1,
            ),
        )
    with pytest.raises(PermissionDenied):
        profile_csv(
            actor=owner,
            snapshot_id=snapshot.snapshot_id,
            request=CsvProfileRequest(source_id=source.source_id),
        )
    with pytest.raises(PermissionDenied):
        compare_groups(
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


@pytest.mark.django_db
def test_file_count_limit_is_rejected_without_snapshot(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    for index in range(MAX_FILES + 1):
        (tmp_path / f"{index:02d}.txt").write_text("x", encoding="utf-8")
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Zu viele Dateien",
        root_path=str(tmp_path),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Dateilimit prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "file_count_limit"
    assert not folder.snapshots.exists()


@pytest.mark.django_db
def test_total_size_limit_is_rejected_without_silent_truncation(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    per_file = 900 * 1024
    file_count = (MAX_TOTAL_BYTES // per_file) + 1
    assert per_file < 1024 * 1024
    assert file_count <= MAX_FILES

    for index in range(file_count):
        (tmp_path / f"{index:02d}.txt").write_text("x" * per_file, encoding="utf-8")

    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Zu groß",
        root_path=str(tmp_path),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Gesamtgröße prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "total_size_limit"
    assert not folder.snapshots.exists()


@pytest.mark.django_db
def test_invalid_utf8_is_rejected_without_content_leak(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    (tmp_path / "broken.txt").write_bytes(b"prefix-\xff-secret-content")
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Ungültiges UTF-8",
        root_path=str(tmp_path),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Encoding prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "invalid_utf8"
    assert "secret-content" not in str(exc_info.value)
    assert not folder.snapshots.exists()


@pytest.mark.django_db
def test_nested_directory_is_rejected(
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.txt").write_text("nicht zulässig", encoding="utf-8")
    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Mit Unterordner",
        root_path=str(tmp_path),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Rekursion prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "nested_directory"


@pytest.mark.django_db
def test_file_symlink_to_outside_is_rejected(
    owner,
    business_unit,
    tmp_path,
):
    if not hasattr(os, "symlink"):
        pytest.skip("Symlinks are not supported on this platform.")

    process = make_process(owner=owner, business_unit=business_unit)
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("extern", encoding="utf-8")
    linked = root / "linked.txt"

    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is not permitted on this platform.")

    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Datei-Symlink",
        root_path=str(root),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Symlink prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "reparse_point"


@pytest.mark.django_db
def test_resolved_file_path_outside_root_is_rejected(
    owner,
    business_unit,
    tmp_path,
    monkeypatch,
):
    process = make_process(owner=owner, business_unit=business_unit)
    root = tmp_path / "root"
    root.mkdir()
    candidate = root / "escape.txt"
    candidate.write_text("lokaler Inhalt", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("externer Inhalt", encoding="utf-8")

    original_resolve = Path.resolve

    def fake_resolve(path_self, strict=False):
        if path_self.name == "escape.txt":
            return original_resolve(outside, strict=strict)
        return original_resolve(path_self, strict=strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    folder = InvestigationSourceFolder.objects.create(
        process_analysis=process,
        name="Resolve-Escape",
        root_path=str(root),
        registered_by=owner,
    )

    with pytest.raises(InvestigationToolError) as exc_info:
        create_source_snapshot(
            actor=owner,
            request=SnapshotRequest(
                process_analysis_id=process.pk,
                folder_id=folder.pk,
                decision_question="Canonical path prüfen",
                run_limits={},
            ),
        )

    assert exc_info.value.code == "path_escape"
    assert "externer Inhalt" not in str(exc_info.value)


@pytest.mark.django_db
def test_versioned_expected_fixture_matches_a_b_c_results(
    owner,
    business_unit,
):
    fixture_root = Path(__file__).parent / "fixtures"
    expected = json.loads(
        (fixture_root / "investigation_expected_v1.json").read_text(encoding="utf-8")
    )
    packs_root = fixture_root / "investigation_source_packs"

    assert expected["version"] == "vs1-source-packs-v2"

    process_a = make_process(owner=owner, business_unit=business_unit, name="Expected A")
    _folder_a, snapshot_a = register_and_snapshot(
        owner=owner,
        process=process_a,
        root=packs_root / "A",
        name="Expected A",
    )
    source_a = next(
        source
        for source in list_sources(actor=owner, snapshot_id=snapshot_a.snapshot_id).sources
        if source.filename == "cases.csv"
    )
    expected_a = expected["A"]["analysis"]
    result_a = compare_groups(
        actor=owner,
        snapshot_id=snapshot_a.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source_a.source_id,
            group_by=expected_a["group_by"],
            aggregation=expected_a["aggregation"],
            value_column=expected_a["value_column"],
            unit_column=expected_a["unit_column"],
        ),
    )
    groups_a = {item["group"]: item for item in result_a.groups}
    for group, contract in expected_a["groups"].items():
        assert groups_a[group]["value"] == contract["value"]
        assert groups_a[group]["population"] == contract["population"]
    assert list(result_a.excluded_rows) == expected_a["excluded_rows"]
    assert expected_a["expected_difference"] in result_a.differences

    process_b = make_process(owner=owner, business_unit=business_unit, name="Expected B")
    _folder_b, snapshot_b = register_and_snapshot(
        owner=owner,
        process=process_b,
        root=packs_root / "B",
        name="Expected B",
    )
    source_b = next(
        source
        for source in list_sources(actor=owner, snapshot_id=snapshot_b.snapshot_id).sources
        if source.filename == "cases.csv"
    )
    result_b = profile_csv(
        actor=owner,
        snapshot_id=snapshot_b.snapshot_id,
        request=CsvProfileRequest(source_id=source_b.source_id),
    )
    expected_b = expected["B"]["profile"]
    assert result_b.columns[expected_b["column"]]["missing"] == expected_b["missing"]
    assert result_b.columns[expected_b["column"]]["type"] == expected_b["type"]

    process_c = make_process(owner=owner, business_unit=business_unit, name="Expected C")
    _folder_c, snapshot_c = register_and_snapshot(
        owner=owner,
        process=process_c,
        root=packs_root / "C",
        name="Expected C",
    )
    source_c = next(
        source
        for source in list_sources(actor=owner, snapshot_id=snapshot_c.snapshot_id).sources
        if source.filename == "cases.csv"
    )
    expected_c = expected["C"]["analysis"]
    result_c = compare_groups(
        actor=owner,
        snapshot_id=snapshot_c.snapshot_id,
        request=CompareGroupsRequest(
            source_id=source_c.source_id,
            group_by=expected_c["group_by"],
            aggregation=expected_c["aggregation"],
            value_column=expected_c["value_column"],
            unit_column=expected_c["unit_column"],
        ),
    )
    groups_c = {item["group"]: item for item in result_c.groups}
    for group, contract in expected_c["groups"].items():
        assert groups_c[group]["value"] == contract["value"]
        assert groups_c[group]["population"] == contract["population"]


def test_expected_fixture_covers_required_analysis_edge_cases():
    fixture = Path(__file__).parent / "fixtures" / "investigation_expected_v1.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))

    assert set(expected["edge_cases"]) == {
        "null_and_wrong_type",
        "unit_conflict",
        "empty_group",
        "duplicates",
    }
    assert expected["edge_cases"]["null_and_wrong_type"]["excluded_rows"] == [
        {"row": 3, "reason": "missing_value"},
        {"row": 6, "reason": "non_numeric_value"},
    ]
    assert expected["edge_cases"]["unit_conflict"]["groups"] == []
    assert expected["edge_cases"]["empty_group"]["groups"] == []
    assert expected["edge_cases"]["duplicates"]["duplicate_rows"] == 1
