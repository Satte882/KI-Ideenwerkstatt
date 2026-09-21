from __future__ import annotations

import hashlib
import unicodedata
from enum import StrEnum

from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction
from django.utils import timezone

from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase

from .candidate_state import supersede_open_candidates
from .catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from .extraction_contract import EXTRACTION_PROMPT_VERSION, EXTRACTION_SCHEMA_VERSION
from .field_registry import UnsupportedAdoptionField, assert_adoptable_field
from .models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionCandidate,
)


class CandidateSnapshotError(ValueError):
    pass


class CandidateValidity(StrEnum):
    VALID = "valid"
    TARGET_MISSING = "target_missing"
    TARGET_INACTIVE = "target_inactive"
    STALE = "stale"


def canonicalize_text(value: str | None) -> str:
    """Normalize only presentation-equivalent text differences for conflict hashes."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("Nur Textwerte können kanonisiert werden.")

    normalized = unicodedata.normalize(
        "NFC",
        value.replace("\r\n", "\n").replace("\r", "\n"),
    )
    normalized_lines = [line.rstrip(" \t") for line in normalized.split("\n")]
    return "\n".join(normalized_lines).strip()


def canonical_text_hash(value: str | None) -> str:
    return hashlib.sha256(canonicalize_text(value).encode("utf-8")).hexdigest()


def _target_model(capture_type: str):
    if capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        return ValueStream
    if capture_type == CaptureSession.CaptureType.USE_CASE:
        return UseCase
    raise CandidateSnapshotError("Unbekannter Capture-Typ.")


def _bound_target_id(session: CaptureSession):
    if session.capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        return session.target_value_stream_id
    if session.capture_type == CaptureSession.CaptureType.USE_CASE:
        return session.target_use_case_id
    return None


def _target_is_inactive(target) -> bool:
    if isinstance(target, ValueStream):
        return target.status == ValueStream.Status.ARCHIVED
    if isinstance(target, UseCase):
        return target.is_archived
    return True


def _text_model_value(target, field_name: str) -> str:
    try:
        model_field = target._meta.get_field(field_name)
    except FieldDoesNotExist as exc:
        raise CandidateSnapshotError("Das vorgeschlagene Zielfeld existiert nicht.") from exc
    if not isinstance(model_field, (models.CharField, models.TextField)):
        raise CandidateSnapshotError("Das vorgeschlagene Zielfeld ist kein Textfeld.")
    value = getattr(target, field_name)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CandidateSnapshotError("Der aktuelle Zielwert ist kein Textwert.")
    return value


def adoption_field_name(suggestion: CaptureFieldSuggestion) -> str | None:
    """Resolve an extraction target path to an explicitly adoptable model field."""

    field_name = suggestion.target_field
    prefix = f"{suggestion.target_object_type}."
    if field_name.startswith(prefix):
        field_name = field_name[len(prefix) :]
    if "." in field_name or "[]" in field_name:
        return None
    try:
        assert_adoptable_field(
            target_type=suggestion.target_object_type,
            field_name=field_name,
        )
    except UnsupportedAdoptionField:
        return None
    return field_name


@transaction.atomic
def create_adoption_candidates(*, analysis_id) -> list[FieldAdoptionCandidate]:
    analysis = (
        CaptureAnalysis.objects.select_for_update().select_related("session").get(pk=analysis_id)
    )
    session = analysis.session
    if analysis.status != CaptureAnalysis.Status.SUCCESS:
        raise CandidateSnapshotError("Nur erfolgreiche Analysen können Kandidaten erzeugen.")
    if analysis.capture_type != session.capture_type:
        raise CandidateSnapshotError("Analyse und Capture Session haben unterschiedliche Typen.")

    target_id = _bound_target_id(session)
    if target_id is None:
        raise CandidateSnapshotError("Die Capture Session besitzt kein Zielobjekt.")
    target_model = _target_model(session.capture_type)
    try:
        target = target_model.objects.get(pk=target_id)
    except target_model.DoesNotExist as exc:
        raise CandidateSnapshotError("Das gebundene Zielobjekt existiert nicht mehr.") from exc
    if _target_is_inactive(target):
        raise CandidateSnapshotError("Das gebundene Zielobjekt ist inaktiv.")

    suggestions = analysis.suggestions.filter(
        target_object_type=session.capture_type,
        target_group_key="",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
    ).order_by("target_field")
    created_candidates = []
    for suggestion in suggestions:
        field_name = adoption_field_name(suggestion)
        if field_name is None:
            continue
        existing_candidate = FieldAdoptionCandidate.objects.filter(suggestion=suggestion).first()
        if existing_candidate is not None:
            created_candidates.append(existing_candidate)
            continue
        if not isinstance(suggestion.suggested_value, str):
            raise CandidateSnapshotError("Der Vorschlagswert ist kein Textwert.")
        previous_value = _text_model_value(target, field_name)
        supersede_open_candidates(
            target_object_type=session.capture_type,
            target_object_id=target.pk,
            target_field=field_name,
            exclude_suggestion_id=suggestion.pk,
        )
        candidate = FieldAdoptionCandidate.objects.create(
            suggestion=suggestion,
            target_object_type=session.capture_type,
            target_object_id=target.pk,
            target_field=field_name,
            proposed_value=canonicalize_text(suggestion.suggested_value),
            previous_value=canonicalize_text(previous_value),
            previous_value_hash=canonical_text_hash(previous_value),
            target_updated_at=target.updated_at,
            source_revision=analysis.source_revision,
            source_hash=analysis.source_hash,
            catalog_version=analysis.catalog_version,
            answer_schema_version=analysis.answer_schema_version,
            prompt_version=analysis.prompt_version,
            extraction_schema_version=analysis.extraction_schema_version,
        )
        created_candidates.append(candidate)
    return created_candidates


def candidate_validity(candidate: FieldAdoptionCandidate, *, now=None) -> CandidateValidity:
    checked_now = now or timezone.now()
    suggestion = candidate.suggestion
    analysis = suggestion.analysis
    session = analysis.session
    target_model = _target_model(candidate.target_object_type)
    try:
        target = target_model.objects.get(pk=candidate.target_object_id)
    except target_model.DoesNotExist:
        return CandidateValidity.TARGET_MISSING
    if _target_is_inactive(target):
        return CandidateValidity.TARGET_INACTIVE

    expected_versions = (
        CATALOG_VERSION_V1,
        ANSWER_SCHEMA_VERSION,
        EXTRACTION_PROMPT_VERSION,
        EXTRACTION_SCHEMA_VERSION,
    )
    candidate_versions = (
        candidate.catalog_version,
        candidate.answer_schema_version,
        candidate.prompt_version,
        candidate.extraction_schema_version,
    )
    analysis_versions = (
        analysis.catalog_version,
        analysis.answer_schema_version,
        analysis.prompt_version,
        analysis.extraction_schema_version,
    )
    session_target_id = _bound_target_id(session)
    is_stale = (
        analysis.status != CaptureAnalysis.Status.SUCCESS
        or session.status != CaptureSession.Status.COMPLETED
        or session.expires_at <= checked_now
        or session.revision != candidate.source_revision
        or analysis.source_revision != candidate.source_revision
        or analysis.source_hash != candidate.source_hash
        or candidate_versions != expected_versions
        or analysis_versions != candidate_versions
        or session.catalog_version != candidate.catalog_version
        or session.schema_version != candidate.answer_schema_version
        or analysis.capture_type != candidate.target_object_type
        or session.capture_type != candidate.target_object_type
        or session_target_id != candidate.target_object_id
    )
    if is_stale:
        return CandidateValidity.STALE
    return CandidateValidity.VALID
