from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .focus import get_value_stream_focus
from .models import ValueStream
from .permissions import can_edit_value_stream
from .stage_focus import StageFocusDecision, get_stage_focus_decision
from .stage_focus_forms import StageFocusForm


@login_required
def stage_focus_select(request, pk):
    value_stream = get_object_or_404(
        ValueStream.objects.select_related("focus", "stage_focus_decision").prefetch_related(
            "stages"
        ),
        pk=pk,
    )
    if not can_edit_value_stream(request.user, value_stream):
        raise PermissionDenied

    focus = get_value_stream_focus(value_stream)
    if value_stream.status != ValueStream.Status.ACTIVE:
        messages.warning(
            request,
            "Schließe zuerst die grobe Phasenerfassung ab und setze den Value Stream auf Aktiv.",
        )
        return redirect(value_stream)
    if focus is None or not focus.is_selected:
        messages.warning(
            request,
            "Der Value Stream muss zuerst für die Prozessdetailanalyse ausgewählt werden.",
        )
        return redirect(value_stream)
    if not value_stream.stages.exists():
        messages.warning(request, "Für die Fokusentscheidung muss mindestens eine Phase vorliegen.")
        return redirect(value_stream)

    decision = get_stage_focus_decision(value_stream)
    form = StageFocusForm(
        request.POST or None,
        value_stream=value_stream,
        decision=decision,
    )
    if request.method == "POST" and form.is_valid():
        StageFocusDecision.objects.update_or_create(
            value_stream=value_stream,
            defaults={
                "selected_stage": form.cleaned_data["selected_stage"],
                "criteria_snapshot": form.criteria_snapshot(),
                "rationale": form.cleaned_data["rationale"],
                "is_short_path": form.cleaned_data["is_short_path"],
                "short_path_reason": form.cleaned_data.get("short_path_reason", ""),
                "selected_by": request.user,
            },
        )
        messages.success(
            request,
            "Fokusphase, Kriterien und Auswahlbegründung wurden gespeichert.",
        )
        return redirect(value_stream)

    return render(
        request,
        "architecture/stage_focus_form.html",
        {
            "value_stream": value_stream,
            "form": form,
            "decision": decision,
        },
    )
