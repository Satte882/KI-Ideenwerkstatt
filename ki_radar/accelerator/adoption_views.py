from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from .adoption_policy import field_adoption_enabled
from .adoption_service import (
    AdoptionDisabled,
    AdoptionOutcome,
    adopt_field_candidate,
    reject_field_candidate,
)
from .models import FieldAdoptionCandidate


def _owned_candidate(*, actor, analysis_id, candidate_id) -> FieldAdoptionCandidate:
    return get_object_or_404(
        FieldAdoptionCandidate.objects.select_related("suggestion__analysis__session"),
        pk=candidate_id,
        suggestion__analysis_id=analysis_id,
        suggestion__analysis__session__owner=actor,
    )


def _ensure_enabled() -> None:
    if not field_adoption_enabled():
        raise Http404


def _redirect_to_analysis(candidate: FieldAdoptionCandidate):
    return redirect("accelerator:analysis_detail", analysis_id=candidate.suggestion.analysis_id)


def _message_result(request, result) -> None:
    if result.outcome == AdoptionOutcome.ADOPTED:
        messages.success(request, "Der Feldvorschlag wurde übernommen.")
    elif result.outcome == AdoptionOutcome.ADOPTED_EDITED:
        messages.success(request, "Der bearbeitete Feldvorschlag wurde übernommen.")
    elif result.outcome == AdoptionOutcome.REJECTED:
        messages.success(request, "Der Feldvorschlag wurde verworfen.")
    elif result.outcome == AdoptionOutcome.CONFLICT:
        messages.error(
            request,
            "Das Zielfeld wurde zwischenzeitlich geändert. Es wurde nichts überschrieben.",
        )
    elif result.outcome == AdoptionOutcome.ACTION_NOT_ALLOWED:
        messages.error(
            request,
            "Diese Aktion ist bei der ausgewiesenen Unsicherheit nicht erlaubt.",
        )
    elif result.outcome == AdoptionOutcome.VALIDATION_FAILED:
        details = " ".join(message for values in result.errors.values() for message in values)
        messages.error(request, details or "Der Feldwert ist fachlich nicht gültig.")
    elif result.outcome == AdoptionOutcome.PERMISSION_DENIED:
        messages.error(request, "Für dieses Zielfeld fehlt die Bearbeitungsberechtigung.")
    elif result.outcome == AdoptionOutcome.IN_PROGRESS:
        messages.info(request, "Der Feldvorschlag wird bereits verarbeitet.")
    else:
        messages.error(request, "Der Feldvorschlag konnte nicht verarbeitet werden.")


@login_required
@require_POST
@sensitive_post_parameters("edited_value")
def candidate_adopt(request, analysis_id, candidate_id):
    _ensure_enabled()
    candidate = _owned_candidate(
        actor=request.user,
        analysis_id=analysis_id,
        candidate_id=candidate_id,
    )
    mode = request.POST.get("mode", "direct")
    if mode not in {"direct", "edited"}:
        raise Http404
    edited_value = request.POST.get("edited_value") if mode == "edited" else None
    try:
        result = adopt_field_candidate(
            candidate_id=candidate.pk,
            actor=request.user,
            edited_value=edited_value,
        )
    except AdoptionDisabled as exc:
        raise Http404 from exc
    _message_result(request, result)
    return _redirect_to_analysis(candidate)


@login_required
@require_POST
def candidate_reject(request, analysis_id, candidate_id):
    _ensure_enabled()
    candidate = _owned_candidate(
        actor=request.user,
        analysis_id=analysis_id,
        candidate_id=candidate_id,
    )
    try:
        result = reject_field_candidate(candidate_id=candidate.pk, actor=request.user)
    except AdoptionDisabled as exc:
        raise Http404 from exc
    _message_result(request, result)
    return _redirect_to_analysis(candidate)
