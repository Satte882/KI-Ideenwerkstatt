from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import FieldAdoptionCandidate


class CandidateTransitionError(RuntimeError):
    pass


TERMINAL_CANDIDATE_STATUSES = frozenset(
    {
        FieldAdoptionCandidate.Status.ADOPTED,
        FieldAdoptionCandidate.Status.ADOPTED_EDITED,
        FieldAdoptionCandidate.Status.REJECTED,
        FieldAdoptionCandidate.Status.CONFLICT,
        FieldAdoptionCandidate.Status.SUPERSEDED,
        FieldAdoptionCandidate.Status.STALE,
        FieldAdoptionCandidate.Status.FAILED,
    }
)


@dataclass(frozen=True)
class CandidateReservation:
    candidate: FieldAdoptionCandidate
    acquired: bool


def reserve_candidate(*, candidate_id, actor) -> CandidateReservation:
    """Atomically reserve one open candidate without locking the target object yet."""
    reserved_at = timezone.now()
    updated = FieldAdoptionCandidate.objects.filter(
        pk=candidate_id,
        status=FieldAdoptionCandidate.Status.OPEN,
    ).update(
        status=FieldAdoptionCandidate.Status.PROCESSING,
        processing_by=actor,
        processing_started_at=reserved_at,
        resolved_at=None,
        error_code="",
        updated_at=reserved_at,
    )
    candidate = FieldAdoptionCandidate.objects.select_related("processing_by").get(pk=candidate_id)
    return CandidateReservation(candidate=candidate, acquired=updated == 1)


def complete_candidate(*, candidate_id, actor, status: str, error_code: str = ""):
    """Complete a reserved candidate once; repeated identical completion is idempotent."""
    if status not in TERMINAL_CANDIDATE_STATUSES:
        raise CandidateTransitionError("Der Zielstatus ist kein terminaler Kandidatenstatus.")

    resolved_at = timezone.now()
    updated = FieldAdoptionCandidate.objects.filter(
        pk=candidate_id,
        status=FieldAdoptionCandidate.Status.PROCESSING,
        processing_by=actor,
    ).update(
        status=status,
        resolved_at=resolved_at,
        error_code=error_code,
        updated_at=resolved_at,
    )
    candidate = FieldAdoptionCandidate.objects.select_related("processing_by").get(pk=candidate_id)
    if updated == 1 or candidate.status == status:
        return candidate
    raise CandidateTransitionError(
        "Der Kandidat wurde nicht von diesem Benutzer reserviert oder bereits anders abgeschlossen."
    )


@transaction.atomic
def supersede_open_candidates(
    *,
    target_object_type: str,
    target_object_id,
    target_field: str,
    exclude_suggestion_id=None,
) -> int:
    """Resolve older open candidates for the same field before a new one is created."""
    resolved_at = timezone.now()
    candidates = FieldAdoptionCandidate.objects.filter(
        target_object_type=target_object_type,
        target_object_id=target_object_id,
        target_field=target_field,
        status=FieldAdoptionCandidate.Status.OPEN,
    )
    if exclude_suggestion_id is not None:
        candidates = candidates.exclude(suggestion_id=exclude_suggestion_id)
    return candidates.update(
        status=FieldAdoptionCandidate.Status.SUPERSEDED,
        resolved_at=resolved_at,
        error_code="superseded_by_new_candidate",
        updated_at=resolved_at,
    )
