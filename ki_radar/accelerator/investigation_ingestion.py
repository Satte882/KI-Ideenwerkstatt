from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream, can_manage_architecture
from ki_radar.use_cases.idea_discovery import idea_origin_id

from .investigation_models import InvestigationSourceFolder
from .investigation_tools import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    InvestigationToolError,
    inspect_source_folder,
)
from .models import CaptureSession


class InvestigationSourceUploadError(RuntimeError):
    pass


def idea_origin_upload(session: CaptureSession) -> SimpleUploadedFile:
    origin_id = idea_origin_id(session.answers)
    if origin_id is None:
        raise InvestigationSourceUploadError("Für die Ideenquelle fehlt die Ursprungsidee.")
    origin = session.answers["origin"]
    filename = f"ideenbox-{origin_id}.md"
    content = (
        "Typ: Nutzerangabe aus Ideen-Box\n"
        "Status: berichtete Ausgangsinformation, nicht unabhängig bestätigt\n\n"
        f"Titel: {origin['title']}\n"
        f"Problem / Beobachtung / Ziel: {session.answers['problem_statement']}\n"
        f"Geschäftskontext: {session.answers.get('business_context', '')}\n"
        f"Quelle / ursprünglicher Einreicher: {origin['source_note']}\n"
    ).encode()
    origin["origin_source_filename"] = filename
    origin["origin_source_sha256"] = hashlib.sha256(content).hexdigest()
    session.save(update_fields=["answers", "updated_at"])
    return SimpleUploadedFile(filename, content, content_type="text/markdown")


def _managed_source_root() -> Path:
    configured = getattr(settings, "INVESTIGATION_SOURCE_UPLOAD_ROOT", None)
    root = (
        Path(configured)
        if configured
        else Path(settings.BASE_DIR) / "var" / "investigation-sources"
    )
    return root.resolve()


def _safe_upload_name(raw_name: str) -> str:
    normalized = str(raw_name or "").replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1].strip()
    if not filename or filename in {".", ".."}:
        raise InvestigationSourceUploadError("Mindestens eine Datei hat keinen gültigen Namen.")
    return filename


def _assert_editable(actor, process: ProcessAnalysis) -> None:
    if (
        actor is None
        or getattr(actor, "pk", None) is None
        or process.status != ProcessAnalysis.Status.DRAFT
        or not can_edit_value_stream(actor, process.stage.value_stream)
    ):
        raise PermissionDenied("Die Quellenbasis ist nicht bearbeitbar.")


def _assert_autonomous_capture_editable(actor, session: CaptureSession) -> None:
    if (
        actor is None
        or getattr(actor, "pk", None) is None
        or session.owner_id != actor.pk
        or session.capture_type != CaptureSession.CaptureType.VALUE_STREAM
        or session.mode != CaptureSession.Mode.AUTONOMOUS
        or session.status != CaptureSession.Status.DRAFT
        or not can_manage_architecture(actor)
    ):
        raise PermissionDenied("Die Discovery-Quellenbasis ist nicht bearbeitbar.")


def _store_managed_folder(
    *,
    actor,
    owner_path: str,
    display_name: str,
    uploads,
    process: ProcessAnalysis | None = None,
    capture_session: CaptureSession | None = None,
) -> InvestigationSourceFolder:
    upload_list = list(uploads or [])
    if not upload_list:
        raise InvestigationSourceUploadError("Bitte mindestens eine Quelldatei auswählen.")
    if len(upload_list) > MAX_FILES:
        raise InvestigationSourceUploadError(
            f"Eine Quellenbasis darf höchstens {MAX_FILES} Dateien enthalten."
        )
    if len(display_name) > 200:
        raise InvestigationSourceUploadError(
            "Der Name der Quellenbasis darf höchstens 200 Zeichen lang sein."
        )

    folder_id = uuid.uuid4()
    root = _managed_source_root() / owner_path / str(folder_id)
    try:
        root.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise InvestigationSourceUploadError(
            "Der verwaltete Quellenbereich konnte nicht angelegt werden."
        ) from exc

    try:
        seen_names: set[str] = set()
        total_bytes = 0
        for upload in upload_list:
            filename = _safe_upload_name(getattr(upload, "name", ""))
            key = filename.casefold()
            if key in seen_names:
                raise InvestigationSourceUploadError(
                    f"Die Datei „{filename}“ wurde mehrfach ausgewählt."
                )
            seen_names.add(key)

            target = root / filename
            file_bytes = 0
            with target.open("xb") as handle:
                for chunk in upload.chunks():
                    file_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if file_bytes > MAX_FILE_BYTES:
                        raise InvestigationSourceUploadError(
                            f"Die Datei „{filename}“ überschreitet das Größenlimit."
                        )
                    if total_bytes > MAX_TOTAL_BYTES:
                        raise InvestigationSourceUploadError(
                            "Die ausgewählten Dateien überschreiten das Gesamtgrößenlimit."
                        )
                    handle.write(chunk)

        # One authoritative validation path for ProcessAnalysis and Discovery:
        # UTF-8, allowed suffixes, CSV shape/limits and filesystem safety.
        inspect_source_folder(str(root))

        with transaction.atomic():
            return InvestigationSourceFolder.objects.create(
                id=folder_id,
                process_analysis=process,
                capture_session=capture_session,
                name=display_name,
                root_path=str(root),
                is_active=True,
                registered_by=actor,
            )
    except (InvestigationSourceUploadError, InvestigationToolError):
        shutil.rmtree(root, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise InvestigationSourceUploadError(
            "Die Quelldateien konnten nicht sicher gespeichert werden."
        ) from exc
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def create_managed_source_folder(
    *,
    actor,
    process_analysis_id,
    name: str,
    uploads,
) -> InvestigationSourceFolder:
    process = ProcessAnalysis.objects.select_related("stage__value_stream").get(
        pk=process_analysis_id
    )
    _assert_editable(actor, process)
    display_name = str(name or "").strip() or f"Quellenbasis - {process.name}"
    return _store_managed_folder(
        actor=actor,
        owner_path=str(process.pk),
        display_name=display_name,
        uploads=uploads,
        process=process,
    )


def create_managed_discovery_source_folder(
    *,
    actor,
    capture_session_id,
    name: str,
    uploads,
) -> InvestigationSourceFolder:
    session = CaptureSession.objects.select_related("owner").get(pk=capture_session_id)
    _assert_autonomous_capture_editable(actor, session)
    display_name = str(name or "").strip() or f"Discovery-Quellen - {session.working_title}"
    return _store_managed_folder(
        actor=actor,
        owner_path=f"capture-{session.pk}",
        display_name=display_name,
        uploads=uploads,
        capture_session=session,
    )
