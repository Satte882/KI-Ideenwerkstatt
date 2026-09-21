from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from .models import CaptureAnalysis
from .structured_models import StructuredAdoptionBatch, StructuredAdoptionItem
from .structured_review import (
    StructuredReviewAction,
    StructuredReviewError,
    build_review_context,
    commit_review_batch,
    decide_review_item,
    get_or_create_review_batch,
)


def _owned_analysis(*, actor, analysis_id) -> CaptureAnalysis:
    return get_object_or_404(
        CaptureAnalysis.objects.select_related("session"),
        pk=analysis_id,
        session__owner=actor,
    )


def _owned_batch(*, actor, analysis_id, batch_id) -> StructuredAdoptionBatch:
    return get_object_or_404(
        StructuredAdoptionBatch.objects.select_related("analysis__session"),
        pk=batch_id,
        analysis_id_snapshot=analysis_id,
        created_by=actor,
    )


@login_required
def structured_review(request, analysis_id):
    analysis = _owned_analysis(actor=request.user, analysis_id=analysis_id)
    try:
        batch = get_or_create_review_batch(analysis_id=analysis.id, actor=request.user)
    except PermissionDenied:
        raise
    except StructuredReviewError as exc:
        messages.error(request, str(exc))
        return redirect("accelerator:analysis_detail", analysis_id=analysis.id)
    context = build_review_context(batch)
    context.update({"analysis": analysis, "session": analysis.session})
    return render(request, "accelerator/structured_review.html", context)


@login_required
@require_POST
@sensitive_post_parameters("edited_value")
def structured_review_decide(request, analysis_id, batch_id, item_id):
    analysis = _owned_analysis(actor=request.user, analysis_id=analysis_id)
    batch = _owned_batch(
        actor=request.user,
        analysis_id=analysis.id,
        batch_id=batch_id,
    )
    item = get_object_or_404(StructuredAdoptionItem, pk=item_id, batch=batch)
    try:
        action = StructuredReviewAction(request.POST.get("action", ""))
    except ValueError as exc:
        raise Http404 from exc
    edited_fields = {
        key.removeprefix("field_"): value
        for key, value in request.POST.items()
        if key.startswith("field_")
    }
    try:
        decide_review_item(
            batch_id=batch.id,
            item_id=item.id,
            actor=request.user,
            action=action,
            edited_value=request.POST.get("edited_value"),
            edited_fields=edited_fields,
            stage_reference=request.POST.get("stage_reference", ""),
        )
    except PermissionDenied:
        raise
    except StructuredReviewError as exc:
        messages.error(request, str(exc))
    else:
        if action == StructuredReviewAction.REJECT:
            messages.success(request, "Das Item wurde verworfen.")
        elif action == StructuredReviewAction.EDIT:
            messages.success(request, "Die bearbeitete Interpretation wurde bestätigt.")
        else:
            messages.success(request, "Die Interpretation wurde bestätigt.")
    return redirect("accelerator:structured_review", analysis_id=analysis.id)


@login_required
@require_POST
def structured_review_commit(request, analysis_id, batch_id):
    analysis = _owned_analysis(actor=request.user, analysis_id=analysis_id)
    batch = _owned_batch(
        actor=request.user,
        analysis_id=analysis.id,
        batch_id=batch_id,
    )
    try:
        result = commit_review_batch(batch_id=batch.id, actor=request.user)
    except PermissionDenied:
        raise
    except StructuredReviewError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(
            request,
            (
                "Der strukturierte Batch konnte nicht übernommen werden. "
                "Es wurden keine Teilobjekte gespeichert."
            ),
        )
    else:
        if result.outcome.value == "replayed":
            messages.info(
                request, "Der bereits abgeschlossene Batch wurde unverändert wiedergegeben."
            )
        else:
            messages.success(request, "Der strukturierte Entwurf wurde vollständig übernommen.")
    return redirect("accelerator:structured_review", analysis_id=analysis.id)
