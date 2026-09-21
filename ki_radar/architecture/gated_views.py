from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from . import views
from .focus import get_value_stream_focus
from .models import ValueStream, ValueStreamStage
from .stage_focus import (
    ensure_single_stage_focus,
    get_stage_focus_decision,
)

PHASE_COMPLETION_REQUIRED_MESSAGE = (
    "Der Value Stream ist noch im Entwurf. Ergänze zuerst die End-to-End-Phasen "
    "und setze den Status anschließend auf Aktiv."
)
STREAM_FOCUS_REQUIRED_MESSAGE = (
    "Der Value Stream muss zuerst vollständig bewertet und für die Prozessdetailanalyse "
    "ausgewählt werden."
)
FOCUS_STAGE_REQUIRED_MESSAGE = (
    "Wähle und begründe zuerst die Fokusphase anhand der gemeinsamen Kriterien."
)
OTHER_STAGE_MESSAGE = (
    "Diese Phase ist nicht als Fokusphase ausgewählt. Öffne die gespeicherte Fokusphase "
    "oder passe die Phasenentscheidung nachvollziehbar an."
)


def _active_stage_or_redirect(request, pk):
    stage = get_object_or_404(
        ValueStreamStage.objects.select_related("value_stream"),
        pk=pk,
    )
    if stage.value_stream.status != ValueStream.Status.ACTIVE:
        messages.warning(request, PHASE_COMPLETION_REQUIRED_MESSAGE)
        return stage, redirect(stage.value_stream)
    return stage, None


def _selected_stage_or_redirect(request, stage):
    focus = get_value_stream_focus(stage.value_stream)
    if focus is None or not focus.is_selected:
        messages.warning(request, STREAM_FOCUS_REQUIRED_MESSAGE)
        return redirect(stage.value_stream)

    decision = get_stage_focus_decision(stage.value_stream)
    if decision is None and ensure_single_stage_focus(stage=stage, actor=request.user):
        decision = get_stage_focus_decision(stage.value_stream)
    if decision is None:
        messages.warning(request, FOCUS_STAGE_REQUIRED_MESSAGE)
        return redirect("architecture:stage_focus_select", pk=stage.value_stream_id)
    if decision.selected_stage_id != stage.pk:
        messages.warning(request, OTHER_STAGE_MESSAGE)
        return redirect(stage.value_stream)
    return None


@login_required
def stage_start_use_case(request, pk):
    stage, blocked_response = _active_stage_or_redirect(request, pk)
    if blocked_response is not None:
        return blocked_response
    blocked_response = _selected_stage_or_redirect(request, stage)
    if blocked_response is not None:
        return blocked_response
    return views.stage_start_use_case(request, pk=pk)


@login_required
def process_analysis_create(request, stage_id):
    stage, blocked_response = _active_stage_or_redirect(request, stage_id)
    if blocked_response is not None:
        return blocked_response
    blocked_response = _selected_stage_or_redirect(request, stage)
    if blocked_response is not None:
        return blocked_response
    return views.process_analysis_create(request, stage_id=stage_id)
