from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from ki_radar.accelerator.investigation_models import (
    InvestigationSourceFolder,
    InvestigationSourceSnapshot,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(*, owner, business_unit):
    stream = ValueStream.objects.create(
        name="Upload Value Stream",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Unterlagen liegen vor",
        outcome="Richtung ist entschieden",
        scope_in="Prüfung bis Entscheidung",
        status=ValueStream.Status.ACTIVE,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Analyse",
        description="Unterlagen prüfen.",
        actors="Fachbereich",
        systems="Dateiablage",
        documents="Unterlagen",
        pain_points="Manuelle Prüfung",
        baseline_metrics="Noch offen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Echter Upload-Fall",
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Unterlagen liegen vor",
        scope_end="Richtung ist entschieden",
        trigger="Prüfung erforderlich",
        outcome="Nachvollziehbare Entscheidung",
        current_flow="Unterlagen prüfen und Richtung ableiten.",
        roles="Fachbereich",
        systems="Dateiablage",
        data_objects="Unterlagen",
        business_rules="",
        handoffs="",
        bottlenecks="Manuelle Prüfung",
        diagnostic_observations="",
        cause_hypotheses="",
        confirmed_causes="",
        constraints="",
        exceptions="",
        baseline_metrics="Noch offen",
        analyzed_by=owner,
    )


@pytest.mark.django_db
def test_source_upload_creates_managed_folder_and_reuses_snapshot_flow(
    client,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    client.force_login(owner)
    upload_root = tmp_path / "managed"

    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=upload_root):
        detail = client.get(process.get_absolute_url())
        detail_content = detail.content.decode()
        assert detail.status_code == 200
        assert "+ Dateien hinzufügen" in detail_content
        assert "administrativ eine Quellenbasis registriert" not in detail_content

        response = client.post(
            reverse(
                "accelerator:investigation_source_upload",
                kwargs={"process_pk": process.pk},
            ),
            {
                "name": "Angebotsvergleich - Ist-Quellen",
                "files": [
                    SimpleUploadedFile(
                        "interview.md",
                        b"# Interview\nFreigaben dauern zu lange.\n",
                        content_type="text/markdown",
                    ),
                    SimpleUploadedFile(
                        "notizen.txt",
                        b"Rueckfragen entstehen bei unvollstaendigen Angaben.\n",
                        content_type="text/plain",
                    ),
                    SimpleUploadedFile(
                        "kennzahlen.csv",
                        b"status,dauer\noffen,12\ngeschlossen,4\n",
                        content_type="text/csv",
                    ),
                ],
            },
        )

        folder = InvestigationSourceFolder.objects.get(process_analysis=process)
        assert response.status_code == 302
        assert response.url == (
            reverse(
                "accelerator:investigation_authorize",
                kwargs={"process_pk": process.pk},
            )
            + f"?folder_id={folder.pk}"
        )
        assert folder.name == "Angebotsvergleich - Ist-Quellen"
        assert folder.registered_by == owner
        assert Path(folder.root_path).is_relative_to(upload_root.resolve())
        assert sorted(path.name for path in Path(folder.root_path).iterdir()) == [
            "interview.md",
            "kennzahlen.csv",
            "notizen.txt",
        ]

        authorize_page = client.get(response.url)
        content = authorize_page.content.decode()
        assert authorize_page.status_code == 200
        assert "interview.md" in content
        assert "notizen.txt" in content
        assert "kennzahlen.csv" in content

        authorized = client.post(
            reverse(
                "accelerator:investigation_authorize",
                kwargs={"process_pk": process.pk},
            ),
            {
                "folder_id": str(folder.pk),
                "decision_question": "Welche Lösungsrichtung ist durch die Quellen gestützt?",
            },
        )

    assert authorized.status_code == 302
    snapshot = InvestigationSourceSnapshot.objects.get(folder=folder)
    assert sorted(snapshot.sources.values_list("filename", flat=True)) == [
        "interview.md",
        "kennzahlen.csv",
        "notizen.txt",
    ]
    assert snapshot.sources.get(filename="interview.md").content.startswith("# Interview")
    csv_source = snapshot.sources.get(filename="kennzahlen.csv")
    assert csv_source.columns == ["status", "dauer"]
    assert csv_source.row_count == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("angebot.pdf", b"%PDF-test"),
        ("kaputt.txt", b"\xff\xfe"),
        ("kaputt.csv", b"a,b\n1\n"),
    ],
)
def test_source_upload_rejects_invalid_files_without_registering_folder(
    client,
    owner,
    business_unit,
    tmp_path,
    filename,
    payload,
):
    process = make_process(owner=owner, business_unit=business_unit)
    client.force_login(owner)
    upload_root = tmp_path / "managed"

    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=upload_root):
        response = client.post(
            reverse(
                "accelerator:investigation_source_upload",
                kwargs={"process_pk": process.pk},
            ),
            {
                "name": "Ungültige Quellen",
                "files": [SimpleUploadedFile(filename, payload)],
            },
        )

    assert response.status_code == 302
    assert response.url == f"{process.get_absolute_url()}#evidence-investigation"
    assert InvestigationSourceFolder.objects.filter(process_analysis=process).count() == 0
    assert not any(path.is_file() for path in upload_root.rglob("*"))


@pytest.mark.django_db
def test_source_upload_requires_process_edit_permission(
    client,
    reader,
    owner,
    business_unit,
    tmp_path,
):
    process = make_process(owner=owner, business_unit=business_unit)
    client.force_login(reader)

    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        response = client.post(
            reverse(
                "accelerator:investigation_source_upload",
                kwargs={"process_pk": process.pk},
            ),
            {
                "name": "Nicht erlaubt",
                "files": [SimpleUploadedFile("notiz.txt", b"Beleg")],
            },
        )

    assert response.status_code == 403
    assert InvestigationSourceFolder.objects.filter(process_analysis=process).count() == 0
