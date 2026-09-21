from __future__ import annotations

import csv
import hashlib
import io
import json
import stat
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream

from .investigation_models import (
    InvestigationSource,
    InvestigationSourceFolder,
    InvestigationSourceSnapshot,
    InvestigationToolResult,
)

TOOL_VERSION = "vs1-source-tools-v1"
MAX_FILES = 12
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 20_000
MAX_CSV_COLUMNS = 50
MAX_SEARCH_RESULTS = 50
MAX_SEARCH_BYTES = 64 * 1024
MAX_READ_ITEMS = 200
MAX_READ_BYTES = MAX_FILE_BYTES + 64 * 1024

_ALLOWED_SUFFIXES = {
    ".txt": InvestigationSource.SourceType.TEXT,
    ".md": InvestigationSource.SourceType.MARKDOWN,
    ".csv": InvestigationSource.SourceType.CSV,
}
_ALLOWED_FILTER_OPERATORS = {
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "is_null",
    "not_null",
}
_ALLOWED_AGGREGATIONS = {"count", "sum", "mean", "median", "min", "max"}


class InvestigationToolError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SnapshotRequest:
    process_analysis_id: UUID | str
    folder_id: UUID | str
    decision_question: str
    run_limits: Mapping[str, int]


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: UUID
    revision: int
    manifest_hash: str
    source_count: int
    total_bytes: int
    process_version: int


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: UUID
    filename: str
    source_type: str
    size_bytes: int
    content_sha256: str
    captured_mtime: str | None
    row_count: int | None
    column_count: int | None
    columns: tuple[str, ...]
    duplicate_of_source_id: UUID | None


@dataclass(frozen=True)
class SourceListResult:
    snapshot_id: UUID
    manifest_hash: str
    sources: tuple[SourceDescriptor, ...]


@dataclass(frozen=True)
class SearchRequest:
    query: str
    cursor: int = 0
    limit: int = 20


@dataclass(frozen=True)
class SearchHit:
    source_id: UUID
    filename: str
    locator: dict[str, Any]
    excerpt: str


@dataclass(frozen=True)
class SearchResult:
    snapshot_id: UUID
    query: str
    hits: tuple[SearchHit, ...]
    next_cursor: int | None
    total_matches: int


@dataclass(frozen=True)
class ReadRequest:
    source_id: UUID | str
    cursor: int = 0
    limit: int = 100
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReadResult:
    snapshot_id: UUID
    source_id: UUID
    source_type: str
    items: tuple[dict[str, Any], ...]
    next_cursor: int | None


@dataclass(frozen=True)
class CsvProfileRequest:
    source_id: UUID | str


@dataclass(frozen=True)
class CsvProfileResult:
    result_id: UUID
    source_id: UUID
    source_hash: str
    row_count: int
    duplicate_rows: int
    columns: dict[str, dict[str, Any]]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class FilterSpec:
    column: str
    operator: str
    value: Any = None


@dataclass(frozen=True)
class CompareGroupsRequest:
    source_id: UUID | str
    group_by: str
    aggregation: str
    value_column: str | None = None
    filters: tuple[FilterSpec, ...] = ()
    unit_column: str | None = None


@dataclass(frozen=True)
class GroupComparisonResult:
    result_id: UUID
    source_id: UUID
    source_hash: str
    population: dict[str, Any]
    groups: tuple[dict[str, Any], ...]
    differences: tuple[dict[str, Any], ...]
    excluded_rows: tuple[dict[str, Any], ...]
    missing_values: dict[str, int]
    units: dict[str, Any]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class StoredToolResult:
    result_id: UUID
    tool_name: str
    source_id: UUID
    source_hash: str
    parameters: dict[str, Any]
    result_payload: dict[str, Any]


@dataclass(frozen=True)
class _ScannedSource:
    filename: str
    source_type: str
    size_bytes: int
    content_sha256: str
    captured_mtime: datetime | None
    content: str
    row_count: int | None
    column_count: int | None
    columns: tuple[str, ...]


def _error(message: str, code: str) -> InvestigationToolError:
    return InvestigationToolError(message, code=code)


def _validate_run_limits(run_limits: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(run_limits, Mapping):
        raise _error(
            "Run-Limits müssen als Schlüssel/Wert-Objekt angegeben werden.",
            "invalid_limits",
        )
    normalized: dict[str, int] = {}
    for key, value in run_limits.items():
        if not isinstance(key, str) or not key.strip():
            raise _error("Run-Limit-Schlüssel müssen nichtleere Strings sein.", "invalid_limits")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1000:
            raise _error(
                "Run-Limits müssen nichtnegative ganze Zahlen bis 1000 sein.",
                "invalid_limits",
            )
        normalized[key.strip()] = value
    return dict(sorted(normalized.items()))


def _authorized_process(*, actor, process_analysis_id, for_update: bool = False):
    queryset = ProcessAnalysis.objects.select_related("stage__value_stream")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        process = queryset.get(pk=process_analysis_id)
    except (ProcessAnalysis.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Die Prozessanalyse ist nicht bearbeitbar.") from exc
    if process.status != ProcessAnalysis.Status.DRAFT:
        raise PermissionDenied("Nur bearbeitbare ProcessAnalysis-Entwürfe sind zulässig.")
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise PermissionDenied("Die Prozessanalyse ist nicht bearbeitbar.")
    return process


def _authorized_snapshot(*, actor, snapshot_id) -> InvestigationSourceSnapshot:
    try:
        snapshot = InvestigationSourceSnapshot.objects.select_related(
            "folder",
            "process_analysis__stage__value_stream",
        ).get(pk=snapshot_id)
    except (InvestigationSourceSnapshot.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Der Quellen-Snapshot ist nicht zugänglich.") from exc
    process = snapshot.process_analysis
    if process.status != ProcessAnalysis.Status.DRAFT:
        raise PermissionDenied("Der gebundene ProcessAnalysis-Entwurf ist nicht mehr bearbeitbar.")
    if not snapshot.folder.is_active:
        raise PermissionDenied("Der Quellenraum wurde entzogen.")
    if snapshot.folder.process_analysis_id != snapshot.process_analysis_id:
        raise PermissionDenied("Der Quellenraum gehört nicht zu diesem Fall.")
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise PermissionDenied("Der Quellen-Snapshot ist nicht zugänglich.")
    return snapshot


def _source_for_snapshot(
    *,
    snapshot: InvestigationSourceSnapshot,
    source_id,
) -> InvestigationSource:
    try:
        return snapshot.sources.get(pk=source_id)
    except (InvestigationSource.DoesNotExist, ValueError) as exc:
        raise _error(
            "Die Source-ID gehört nicht zu diesem Quellen-Snapshot.",
            "source_not_found",
        ) from exc


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise _error(
            "Der Quellenpfad kann nicht sicher geprüft werden.",
            "source_path_unreadable",
        ) from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    file_attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _root_path(raw_path: str) -> Path:
    raw = Path(raw_path)
    if ".." in raw.parts:
        raise _error("Parent-Traversal ist für Quellenordner unzulässig.", "path_traversal")
    if _is_reparse_or_symlink(raw):
        raise _error("Symlinks, Junctions und Reparse-Points sind unzulässig.", "reparse_point")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise _error(
            "Der registrierte Quellenordner ist nicht lesbar.",
            "source_path_unreadable",
        ) from exc
    if not resolved.is_dir():
        raise _error("Der registrierte Quellenpfad ist kein Ordner.", "source_path_invalid")
    return resolved


def _csv_rows(content: str) -> tuple[list[str], list[list[str]]]:
    try:
        parsed = list(csv.reader(io.StringIO(content, newline="")))
    except csv.Error as exc:
        raise _error("Die CSV-Datei ist syntaktisch ungültig.", "invalid_csv") from exc
    if not parsed:
        raise _error("CSV-Dateien benötigen eine Kopfzeile.", "invalid_csv")
    header = [cell.strip() for cell in parsed[0]]
    if not header or any(not cell for cell in header):
        raise _error("CSV-Spalten benötigen eindeutige, nichtleere Namen.", "invalid_csv_header")
    if len(set(header)) != len(header):
        raise _error("Doppelte CSV-Spaltennamen sind unzulässig.", "invalid_csv_header")
    if len(header) > MAX_CSV_COLUMNS:
        raise _error("Die CSV-Datei überschreitet das Spaltenlimit.", "csv_column_limit")
    rows = parsed[1:]
    if len(rows) > MAX_CSV_ROWS:
        raise _error("Die CSV-Datei überschreitet das Zeilenlimit.", "csv_row_limit")
    for row in rows:
        if len(row) != len(header):
            raise _error(
                "CSV-Zeilen müssen exakt der Kopfzeilenbreite entsprechen.",
                "invalid_csv_shape",
            )
    return header, rows


def _scan_folder(root_path: str) -> tuple[_ScannedSource, ...]:
    root = _root_path(root_path)
    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        raise _error(
            "Der Quellenordner kann nicht gelesen werden.",
            "source_path_unreadable",
        ) from exc
    if len(entries) > MAX_FILES:
        raise _error("Der Quellenordner überschreitet das Dateilimit.", "file_count_limit")

    scanned: list[_ScannedSource] = []
    total_bytes = 0
    for candidate in entries:
        if _is_reparse_or_symlink(candidate):
            raise _error("Symlinks, Junctions und Reparse-Points sind unzulässig.", "reparse_point")
        if not candidate.is_file():
            raise _error("Der Quellenraum darf keine Unterordner enthalten.", "nested_directory")
        source_type = _ALLOWED_SUFFIXES.get(candidate.suffix.casefold())
        if source_type is None:
            raise _error("Der Quellenraum enthält einen unzulässigen Dateityp.", "unsupported_type")

        try:
            before = candidate.stat()
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise _error(
                "Eine Quelldatei kann nicht sicher gelesen werden.",
                "source_unreadable",
            ) from exc
        if resolved.parent != root:
            raise _error("Ein Quellenpfad verlässt den registrierten Ordner.", "path_escape")
        if before.st_size > MAX_FILE_BYTES:
            raise _error("Eine Quelldatei überschreitet das Größenlimit.", "file_size_limit")
        total_bytes += before.st_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise _error("Der Quellenraum überschreitet das Gesamtgrößenlimit.", "total_size_limit")

        try:
            raw_bytes = candidate.read_bytes()
            after = candidate.stat()
        except OSError as exc:
            raise _error("Eine Quelldatei kann nicht gelesen werden.", "source_unreadable") from exc
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise _error("Eine Quelldatei wurde während des Snapshots verändert.", "source_changed")
        if len(raw_bytes) != before.st_size:
            raise _error("Eine Quelldatei wurde nicht vollständig gelesen.", "source_changed")
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _error("Quelldateien müssen UTF-8 sein.", "invalid_utf8") from exc

        columns: tuple[str, ...] = ()
        row_count = None
        column_count = None
        if source_type == InvestigationSource.SourceType.CSV:
            header, rows = _csv_rows(text)
            columns = tuple(header)
            row_count = len(rows)
            column_count = len(header)

        captured_mtime = datetime.fromtimestamp(before.st_mtime, tz=UTC)
        scanned.append(
            _ScannedSource(
                filename=candidate.name,
                source_type=source_type,
                size_bytes=before.st_size,
                content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
                captured_mtime=captured_mtime,
                content=text,
                row_count=row_count,
                column_count=column_count,
                columns=columns,
            )
        )
    return tuple(scanned)


def _manifest_hash(scanned: tuple[_ScannedSource, ...]) -> str:
    manifest = [
        {
            "filename": item.filename,
            "source_type": item.source_type,
            "size_bytes": item.size_bytes,
            "content_sha256": item.content_sha256,
            "row_count": item.row_count,
            "column_count": item.column_count,
            "columns": list(item.columns),
        }
        for item in scanned
    ]
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _process_context(process: ProcessAnalysis) -> dict[str, Any]:
    return {
        "process_analysis_id": str(process.pk),
        "process_version": process.version,
        "name": process.name,
        "scope_start": process.scope_start,
        "scope_end": process.scope_end,
        "trigger": process.trigger,
        "outcome": process.outcome,
        "current_flow": process.current_flow,
        "roles": process.roles,
        "systems": process.systems,
        "data_objects": process.data_objects,
        "business_rules": process.business_rules,
        "handoffs": process.handoffs,
        "bottlenecks": process.bottlenecks,
        "diagnostic_observations": process.diagnostic_observations,
        "cause_hypotheses": process.cause_hypotheses,
        "confirmed_causes": process.confirmed_causes,
        "constraints": process.constraints,
        "exceptions": process.exceptions,
        "baseline_metrics": process.baseline_metrics,
        "claim_semantics": (
            "Vorhandene Aussagen sind Angaben ihres Erstellers und keine automatisch "
            "bestätigten Fakten."
        ),
    }


def create_source_snapshot(*, actor, request: SnapshotRequest) -> SnapshotResult:
    question = request.decision_question.strip()
    if not question:
        raise _error("Eine Problem- oder Entscheidungsfrage ist erforderlich.", "missing_question")
    run_limits = _validate_run_limits(request.run_limits)
    process = _authorized_process(
        actor=actor,
        process_analysis_id=request.process_analysis_id,
    )
    try:
        folder = InvestigationSourceFolder.objects.get(pk=request.folder_id)
    except (InvestigationSourceFolder.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Der Quellenordner ist nicht registriert.") from exc
    if folder.process_analysis_id != process.pk or not folder.is_active:
        raise PermissionDenied("Der Quellenordner ist für diesen Fall nicht freigegeben.")

    scanned = _scan_folder(folder.root_path)
    manifest_hash = _manifest_hash(scanned)

    with transaction.atomic():
        locked_process = _authorized_process(
            actor=actor,
            process_analysis_id=process.pk,
            for_update=True,
        )
        try:
            locked_folder = InvestigationSourceFolder.objects.select_for_update().get(
                pk=folder.pk,
                process_analysis=locked_process,
                is_active=True,
            )
        except InvestigationSourceFolder.DoesNotExist as exc:
            raise PermissionDenied("Der Quellenraum wurde vor dem Commit entzogen.") from exc
        if not can_edit_value_stream(actor, locked_process.stage.value_stream):
            raise PermissionDenied("Die Bearbeitungsberechtigung wurde vor dem Commit entzogen.")

        current_revision = (
            InvestigationSourceSnapshot.objects.filter(folder=locked_folder).aggregate(
                maximum=Max("revision")
            )["maximum"]
            or 0
        )
        snapshot = InvestigationSourceSnapshot.objects.create(
            folder=locked_folder,
            process_analysis=locked_process,
            revision=current_revision + 1,
            process_version=locked_process.version,
            decision_question=question,
            run_limits=run_limits,
            process_context=_process_context(locked_process),
            manifest_hash=manifest_hash,
            captured_by=actor,
        )
        first_by_hash: dict[str, InvestigationSource] = {}
        for item in scanned:
            duplicate_of = first_by_hash.get(item.content_sha256)
            source = InvestigationSource.objects.create(
                snapshot=snapshot,
                filename=item.filename,
                source_type=item.source_type,
                size_bytes=item.size_bytes,
                content_sha256=item.content_sha256,
                captured_mtime=item.captured_mtime,
                content=item.content,
                row_count=item.row_count,
                column_count=item.column_count,
                columns=list(item.columns),
                duplicate_of=duplicate_of,
            )
            first_by_hash.setdefault(item.content_sha256, source)

        refreshed = _authorized_process(
            actor=actor,
            process_analysis_id=locked_process.pk,
            for_update=True,
        )
        if refreshed.stage.value_stream_id != locked_process.stage.value_stream_id:
            raise PermissionDenied("Der Fallbezug hat sich vor dem Commit geändert.")

    return SnapshotResult(
        snapshot_id=snapshot.pk,
        revision=snapshot.revision,
        manifest_hash=snapshot.manifest_hash,
        source_count=len(scanned),
        total_bytes=sum(item.size_bytes for item in scanned),
        process_version=snapshot.process_version,
    )


def list_sources(*, actor, snapshot_id) -> SourceListResult:
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=snapshot_id)
    sources = tuple(
        SourceDescriptor(
            source_id=source.pk,
            filename=source.filename,
            source_type=source.source_type,
            size_bytes=source.size_bytes,
            content_sha256=source.content_sha256,
            captured_mtime=(
                source.captured_mtime.isoformat() if source.captured_mtime is not None else None
            ),
            row_count=source.row_count,
            column_count=source.column_count,
            columns=tuple(source.columns),
            duplicate_of_source_id=source.duplicate_of_id,
        )
        for source in snapshot.sources.select_related("duplicate_of").all()
    )
    return SourceListResult(
        snapshot_id=snapshot.pk,
        manifest_hash=snapshot.manifest_hash,
        sources=sources,
    )


def _snippet(value: str, query: str, max_chars: int = 300) -> str:
    compact = value.replace("\r", " ").replace("\n", " ")
    position = compact.casefold().find(query.casefold())
    if position < 0 or len(compact) <= max_chars:
        return compact[:max_chars]
    flank = max_chars // 2
    start = max(0, position - flank)
    end = min(len(compact), start + max_chars)
    return compact[start:end]


def _all_search_hits(snapshot: InvestigationSourceSnapshot, query: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    folded = query.casefold()
    for source in snapshot.sources.order_by("filename", "id"):
        if source.source_type in {
            InvestigationSource.SourceType.TEXT,
            InvestigationSource.SourceType.MARKDOWN,
        }:
            for line_number, line in enumerate(source.content.splitlines(), start=1):
                if folded in line.casefold():
                    hits.append(
                        SearchHit(
                            source_id=source.pk,
                            filename=source.filename,
                            locator={"line": line_number},
                            excerpt=_snippet(line, query),
                        )
                    )
            continue

        header, rows = _csv_rows(source.content)
        for row_number, row in enumerate(rows, start=1):
            for column, value in zip(header, row, strict=True):
                if folded in value.casefold():
                    hits.append(
                        SearchHit(
                            source_id=source.pk,
                            filename=source.filename,
                            locator={"row": row_number, "column": column},
                            excerpt=_snippet(value, query),
                        )
                    )
    return hits


def search_sources(*, actor, snapshot_id, request: SearchRequest) -> SearchResult:
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=snapshot_id)
    query = request.query.strip()
    if not query:
        raise _error("Eine nichtleere Suchfrage ist erforderlich.", "empty_query")
    if request.cursor < 0:
        raise _error("Der Cursor darf nicht negativ sein.", "invalid_cursor")
    if request.limit < 1 or request.limit > MAX_SEARCH_RESULTS:
        raise _error("Das Suchlimit liegt außerhalb des zulässigen Bereichs.", "invalid_limit")

    all_hits = _all_search_hits(snapshot, query)
    selected: list[SearchHit] = []
    bytes_used = 0
    index = request.cursor
    while index < len(all_hits) and len(selected) < request.limit:
        hit = all_hits[index]
        hit_bytes = len(json.dumps(asdict(hit), ensure_ascii=False, default=str).encode("utf-8"))
        if selected and bytes_used + hit_bytes > MAX_SEARCH_BYTES:
            break
        if not selected and hit_bytes > MAX_SEARCH_BYTES:
            raise _error(
                "Ein einzelner Suchtreffer überschreitet das Ergebnislimit.",
                "hit_too_large",
            )
        selected.append(hit)
        bytes_used += hit_bytes
        index += 1

    next_cursor = index if index < len(all_hits) else None
    return SearchResult(
        snapshot_id=snapshot.pk,
        query=query,
        hits=tuple(selected),
        next_cursor=next_cursor,
        total_matches=len(all_hits),
    )


def read_source(*, actor, snapshot_id, request: ReadRequest) -> ReadResult:
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=snapshot_id)
    source = _source_for_snapshot(snapshot=snapshot, source_id=request.source_id)
    if request.cursor < 0:
        raise _error("Der Cursor darf nicht negativ sein.", "invalid_cursor")
    if request.limit < 1 or request.limit > MAX_READ_ITEMS:
        raise _error("Das Leselimit liegt außerhalb des zulässigen Bereichs.", "invalid_limit")

    items: list[dict[str, Any]] = []
    if source.source_type in {
        InvestigationSource.SourceType.TEXT,
        InvestigationSource.SourceType.MARKDOWN,
    }:
        available = [
            {"line": number, "text": line}
            for number, line in enumerate(source.content.splitlines(), start=1)
        ]
    else:
        header, rows = _csv_rows(source.content)
        columns = list(request.columns) if request.columns else header
        unknown = sorted(set(columns) - set(header))
        if unknown:
            raise _error(
                "Mindestens eine angeforderte CSV-Spalte existiert nicht.",
                "missing_column",
            )
        positions = [header.index(column) for column in columns]
        available = [
            {
                "row": row_number,
                "values": {
                    column: row[position]
                    for column, position in zip(columns, positions, strict=True)
                },
            }
            for row_number, row in enumerate(rows, start=1)
        ]

    index = request.cursor
    bytes_used = 0
    while index < len(available) and len(items) < request.limit:
        item = available[index]
        item_bytes = len(json.dumps(item, ensure_ascii=False).encode("utf-8"))
        if items and bytes_used + item_bytes > MAX_READ_BYTES:
            break
        if not items and item_bytes > MAX_READ_BYTES:
            raise _error(
                "Ein einzelnes Leseelement überschreitet das Byte-Limit.",
                "item_too_large",
            )
        items.append(item)
        bytes_used += item_bytes
        index += 1
    next_cursor = index if index < len(available) else None
    return ReadResult(
        snapshot_id=snapshot.pk,
        source_id=source.pk,
        source_type=source.source_type,
        items=tuple(items),
        next_cursor=next_cursor,
    )


def _cell_type(value: str) -> str:
    raw = value.strip()
    if not raw:
        return "empty"
    if raw.casefold() in {"true", "false", "ja", "nein"}:
        return "boolean"
    try:
        int(raw)
        return "integer"
    except ValueError:
        pass
    try:
        Decimal(raw)
        return "decimal"
    except InvalidOperation:
        return "text"


def _column_type(values: list[str]) -> str:
    kinds = {_cell_type(value) for value in values if value.strip()}
    if not kinds:
        return "empty"
    if kinds <= {"integer"}:
        return "integer"
    if kinds <= {"integer", "decimal"}:
        return "decimal"
    if len(kinds) == 1:
        return next(iter(kinds))
    return "mixed"


def _record_tool_result(
    *,
    actor,
    snapshot: InvestigationSourceSnapshot,
    source: InvestigationSource,
    tool_name: str,
    parameters: dict[str, Any],
    result_payload: dict[str, Any],
    population: dict[str, Any],
    excluded_rows: list[dict[str, Any]],
    group_sizes: dict[str, int],
    missing_values: dict[str, int],
    units: dict[str, Any],
) -> InvestigationToolResult:
    _authorized_snapshot(actor=actor, snapshot_id=snapshot.pk)
    return InvestigationToolResult.objects.create(
        snapshot=snapshot,
        source=source,
        requested_by=actor,
        tool_name=tool_name,
        tool_version=TOOL_VERSION,
        source_hash=source.content_sha256,
        parameters=parameters,
        result_payload=result_payload,
        population=population,
        excluded_rows=excluded_rows,
        group_sizes=group_sizes,
        missing_values=missing_values,
        units=units,
    )


def profile_csv(*, actor, snapshot_id, request: CsvProfileRequest) -> CsvProfileResult:
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=snapshot_id)
    source = _source_for_snapshot(snapshot=snapshot, source_id=request.source_id)
    if source.source_type != InvestigationSource.SourceType.CSV:
        raise _error("profile_csv akzeptiert nur CSV-Quellen.", "wrong_source_type")

    header, rows = _csv_rows(source.content)
    columns: dict[str, dict[str, Any]] = {}
    missing_values: dict[str, int] = {}
    findings: list[str] = []
    for index, column in enumerate(header):
        values = [row[index] for row in rows]
        missing = sum(1 for value in values if not value.strip())
        inferred = _column_type(values)
        columns[column] = {
            "type": inferred,
            "missing": missing,
            "non_missing": len(rows) - missing,
        }
        missing_values[column] = missing
        if inferred == "mixed":
            findings.append(f"Spalte '{column}' enthält gemischte Typen.")

    row_tuples = [tuple(row) for row in rows]
    duplicate_rows = len(row_tuples) - len(set(row_tuples))
    if duplicate_rows:
        findings.append(f"{duplicate_rows} Dublettenzeilen erkannt.")

    result_payload = {
        "row_count": len(rows),
        "duplicate_rows": duplicate_rows,
        "columns": columns,
        "findings": findings,
    }
    stored = _record_tool_result(
        actor=actor,
        snapshot=snapshot,
        source=source,
        tool_name=InvestigationToolResult.ToolName.PROFILE_CSV,
        parameters={},
        result_payload=result_payload,
        population={"rows_total": len(rows), "included_rows": list(range(1, len(rows) + 1))},
        excluded_rows=[],
        group_sizes={},
        missing_values=missing_values,
        units={},
    )
    return CsvProfileResult(
        result_id=stored.pk,
        source_id=source.pk,
        source_hash=source.content_sha256,
        row_count=len(rows),
        duplicate_rows=duplicate_rows,
        columns=columns,
        findings=tuple(findings),
    )


def _decimal(value: str) -> Decimal | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _passes_filter(value: str, spec: FilterSpec) -> tuple[bool, bool]:
    operator = spec.operator
    if operator not in _ALLOWED_FILTER_OPERATORS:
        raise _error("Unzulässiger Filteroperator.", "invalid_filter_operator")
    if operator == "is_null":
        return not value.strip(), False
    if operator == "not_null":
        return bool(value.strip()), False
    if operator in {"eq", "neq"}:
        matched = value == str(spec.value)
        return (matched if operator == "eq" else not matched), False
    if operator in {"in", "not_in"}:
        if not isinstance(spec.value, (list, tuple)):
            raise _error("in/not_in benötigen eine Werteliste.", "invalid_filter_value")
        matched = value in {str(item) for item in spec.value}
        return (matched if operator == "in" else not matched), False

    left = _decimal(value)
    try:
        right = Decimal(str(spec.value))
    except (InvalidOperation, ValueError) as exc:
        raise _error(
            "Numerische Filter benötigen einen numerischen Vergleichswert.",
            "invalid_filter_value",
        ) from exc
    if left is None:
        return False, True
    comparisons = {
        "gt": left > right,
        "gte": left >= right,
        "lt": left < right,
        "lte": left <= right,
    }
    return comparisons[operator], False


def _aggregate(values: list[Decimal], aggregation: str) -> Decimal:
    if aggregation == "sum":
        return sum(values, Decimal("0"))
    if aggregation == "mean":
        return sum(values, Decimal("0")) / Decimal(len(values))
    if aggregation == "median":
        return Decimal(str(median(values)))
    if aggregation == "min":
        return min(values)
    if aggregation == "max":
        return max(values)
    raise _error("Unbekannte Aggregation.", "invalid_aggregation")


def _json_number(value: Decimal | int) -> str | int:
    if isinstance(value, int):
        return value
    return format(value, "f")


def compare_groups(
    *,
    actor,
    snapshot_id,
    request: CompareGroupsRequest,
) -> GroupComparisonResult:
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=snapshot_id)
    source = _source_for_snapshot(snapshot=snapshot, source_id=request.source_id)
    if source.source_type != InvestigationSource.SourceType.CSV:
        raise _error("compare_groups akzeptiert nur CSV-Quellen.", "wrong_source_type")
    if request.aggregation not in _ALLOWED_AGGREGATIONS:
        raise _error("Unzulässige Aggregation.", "invalid_aggregation")

    header, rows = _csv_rows(source.content)
    required = {request.group_by}
    required.update(spec.column for spec in request.filters)
    if request.value_column:
        required.add(request.value_column)
    if request.unit_column:
        required.add(request.unit_column)
    missing_columns = sorted(required - set(header))
    if missing_columns:
        raise _error("Mindestens eine angeforderte CSV-Spalte existiert nicht.", "missing_column")
    if request.aggregation != "count" and not request.value_column:
        raise _error("Diese Aggregation benötigt eine Wertespalte.", "missing_value_column")

    positions = {column: header.index(column) for column in required}
    filtered: list[tuple[int, list[str]]] = []
    excluded_rows: list[dict[str, Any]] = []
    filter_type_errors: list[int] = []
    for row_number, row in enumerate(rows, start=1):
        matched = True
        for spec in request.filters:
            passes, type_error = _passes_filter(row[positions[spec.column]], spec)
            if type_error:
                filter_type_errors.append(row_number)
                excluded_rows.append({"row": row_number, "reason": "filter_type_error"})
                matched = False
                break
            if not passes:
                matched = False
                break
        if matched:
            filtered.append((row_number, row))

    missing_values = {column: 0 for column in required}
    for _row_number, row in filtered:
        for column in required:
            if not row[positions[column]].strip():
                missing_values[column] += 1

    units: dict[str, Any] = {}
    findings: list[str] = []
    if filter_type_errors:
        findings.append(
            f"{len(filter_type_errors)} Zeilen wegen nichtnumerischer Filterwerte ausgeschlossen."
        )

    relevant_for_units = filtered
    if request.value_column:
        relevant_for_units = [
            item for item in filtered if item[1][positions[request.value_column]].strip()
        ]
    if request.unit_column:
        unit_values = sorted(
            {
                row[positions[request.unit_column]].strip()
                for _row_number, row in relevant_for_units
                if row[positions[request.unit_column]].strip()
            }
        )
        missing_unit_rows = [
            row_number
            for row_number, row in relevant_for_units
            if not row[positions[request.unit_column]].strip()
        ]
        units = {
            "column": request.unit_column,
            "values": unit_values,
            "missing_rows": missing_unit_rows,
        }
        if missing_unit_rows:
            findings.append(
                f"{len(missing_unit_rows)} Zeilen haben für die Wertespalte "
                "keine eindeutige Einheit."
            )
        if not unit_values and relevant_for_units:
            findings.append("Einheit für die Wertespalte ist im Vergleichsbestand unklar.")
        if len(unit_values) > 1:
            findings.append("Einheitenkonflikt: mehrere Einheiten im Vergleichsbestand.")
            result_payload = {
                "status": "blocked",
                "groups": [],
                "differences": [],
                "findings": findings,
            }
            population = {
                "rows_total": len(rows),
                "filter_matched_rows": len(filtered),
                "included_rows": [row_number for row_number, _row in filtered],
                "aggregated_rows": [],
            }
            stored = _record_tool_result(
                actor=actor,
                snapshot=snapshot,
                source=source,
                tool_name=InvestigationToolResult.ToolName.COMPARE_GROUPS,
                parameters={
                    "group_by": request.group_by,
                    "aggregation": request.aggregation,
                    "value_column": request.value_column,
                    "filters": [asdict(spec) for spec in request.filters],
                    "unit_column": request.unit_column,
                },
                result_payload=result_payload,
                population=population,
                excluded_rows=excluded_rows,
                group_sizes={},
                missing_values=missing_values,
                units=units,
            )
            return GroupComparisonResult(
                result_id=stored.pk,
                source_id=source.pk,
                source_hash=source.content_sha256,
                population=population,
                groups=(),
                differences=(),
                excluded_rows=tuple(excluded_rows),
                missing_values=missing_values,
                units=units,
                findings=tuple(findings),
            )

    grouped_values: dict[str, list[Decimal]] = {}
    grouped_counts: dict[str, int] = {}
    aggregated_rows: list[int] = []
    for row_number, row in filtered:
        group = row[positions[request.group_by]].strip() or "<null>"
        if request.aggregation == "count" and request.value_column is None:
            grouped_counts[group] = grouped_counts.get(group, 0) + 1
            aggregated_rows.append(row_number)
            continue

        value_column = request.value_column
        if value_column is None:
            raise _error(
                "Diese Aggregation benötigt eine Wertespalte.",
                "missing_value_column",
            )
        raw_value = row[positions[value_column]]
        if not raw_value.strip():
            excluded_rows.append({"row": row_number, "reason": "missing_value"})
            continue
        numeric = _decimal(raw_value)
        if request.aggregation == "count":
            grouped_counts[group] = grouped_counts.get(group, 0) + 1
            aggregated_rows.append(row_number)
            continue
        if numeric is None:
            excluded_rows.append({"row": row_number, "reason": "non_numeric_value"})
            continue
        grouped_values.setdefault(group, []).append(numeric)
        aggregated_rows.append(row_number)

    groups: list[dict[str, Any]] = []
    if request.aggregation == "count":
        for group in sorted(grouped_counts):
            groups.append(
                {
                    "group": group,
                    "value": grouped_counts[group],
                    "population": grouped_counts[group],
                }
            )
    else:
        for group in sorted(grouped_values):
            values = grouped_values[group]
            aggregate = _aggregate(values, request.aggregation)
            groups.append(
                {
                    "group": group,
                    "value": _json_number(aggregate),
                    "population": len(values),
                }
            )

    group_sizes = {item["group"]: int(item["population"]) for item in groups}
    if not groups:
        findings.append("Leere Vergleichspopulation nach Filtern und Ausschlüssen.")
    non_numeric_count = sum(1 for item in excluded_rows if item["reason"] == "non_numeric_value")
    if non_numeric_count:
        findings.append(f"{non_numeric_count} nichtnumerische Werte ausgeschlossen.")

    differences: list[dict[str, Any]] = []
    for left_index, left in enumerate(groups):
        for right in groups[left_index + 1 :]:
            try:
                left_value = Decimal(str(left["value"]))
                right_value = Decimal(str(right["value"]))
            except InvalidOperation:
                continue
            differences.append(
                {
                    "from_group": left["group"],
                    "to_group": right["group"],
                    "delta": _json_number(right_value - left_value),
                }
            )

    population = {
        "rows_total": len(rows),
        "filter_matched_rows": len(filtered),
        "included_rows": [row_number for row_number, _row in filtered],
        "aggregated_rows": aggregated_rows,
    }
    result_payload = {
        "status": "ok",
        "groups": groups,
        "differences": differences,
        "findings": findings,
        "causality_note": (
            "Aggregationen belegen Unterschiede im freigegebenen Bestand, "
            "nicht automatisch Kausalität."
        ),
    }
    parameters = {
        "group_by": request.group_by,
        "aggregation": request.aggregation,
        "value_column": request.value_column,
        "filters": [asdict(spec) for spec in request.filters],
        "unit_column": request.unit_column,
    }
    stored = _record_tool_result(
        actor=actor,
        snapshot=snapshot,
        source=source,
        tool_name=InvestigationToolResult.ToolName.COMPARE_GROUPS,
        parameters=parameters,
        result_payload=result_payload,
        population=population,
        excluded_rows=excluded_rows,
        group_sizes=group_sizes,
        missing_values=missing_values,
        units=units,
    )
    return GroupComparisonResult(
        result_id=stored.pk,
        source_id=source.pk,
        source_hash=source.content_sha256,
        population=population,
        groups=tuple(groups),
        differences=tuple(differences),
        excluded_rows=tuple(excluded_rows),
        missing_values=missing_values,
        units=units,
        findings=tuple(findings),
    )


def get_tool_result(*, actor, result_id) -> StoredToolResult:
    try:
        result = InvestigationToolResult.objects.select_related(
            "snapshot__folder",
            "snapshot__process_analysis__stage__value_stream",
            "source",
        ).get(pk=result_id)
    except (InvestigationToolResult.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Das Werkzeugresultat ist nicht zugänglich.") from exc
    _authorized_snapshot(actor=actor, snapshot_id=result.snapshot_id)
    return StoredToolResult(
        result_id=result.pk,
        tool_name=result.tool_name,
        source_id=result.source_id,
        source_hash=result.source_hash,
        parameters=result.parameters,
        result_payload=result.result_payload,
    )
