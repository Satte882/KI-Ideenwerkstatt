from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ki_radar.accelerator.solution_generation_entry import (
    build_solution_generation_entry_context,
)

from .forms import SolutionSelectionForm
from .models import ProcessAnalysis, SolutionOption
from .permissions import can_edit_value_stream
from .solution_retirement import retire_solution_option
from .solution_selection import (
    comparison_blockers,
    diagnosis_readiness_blockers,
    ordered_solution_options,
    select_preferred_solution,
)


@login_required
def solution_option_compare(request, pk):
    process_analysis = get_object_or_404(
        ProcessAnalysis.objects.select_related(
            "stage__value_stream__focus",
            "stage__value_stream__owner",
        ).prefetch_related(
            "validations",
            "solution_options",
            "solution_selection_decisions__selected_option",
            "solution_selection_decisions__decided_by",
        ),
        pk=pk,
    )
    options = ordered_solution_options(process_analysis)
    blockers = comparison_blockers(options)
    diagnosis_blockers = diagnosis_readiness_blockers(process_analysis)
    incomplete_options = [option for option in options if not option.comparison_complete]
    can_select = can_edit_value_stream(
        request.user,
        process_analysis.stage.value_stream,
    )
    generation_entry = build_solution_generation_entry_context(process_analysis)
    selection_history = process_analysis.solution_selection_decisions.all()
    latest_selection = selection_history.first()

    form = SolutionSelectionForm(
        request.POST or None,
        options=options,
        initial={
            "selected_option": latest_selection.selected_option_id,
        }
        if latest_selection
        else None,
    )
    if request.method == "POST":
        if not can_select:
            raise PermissionDenied
        if form.is_valid():
            try:
                select_preferred_solution(
                    process_analysis=process_analysis,
                    selected_option=form.cleaned_data["selected_option"],
                    rationale=form.cleaned_data["rationale"],
                    actor=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Die bevorzugte Lösungsoption wurde auditierbar ausgewählt.",
                )
                comparison_url = reverse(
                    "architecture:solution_option_compare",
                    kwargs={"pk": process_analysis.pk},
                )
                return redirect(f"{comparison_url}#selection-result")

    return render(
        request,
        "architecture/solution_option_compare.html",
        {
            "process_analysis": process_analysis,
            "options": options,
            "blockers": blockers,
            "diagnosis_blockers": diagnosis_blockers,
            "incomplete_options": incomplete_options,
            "needs_more_options": len(options) < 2,
            "form": form,
            "can_select": can_select,
            "selection_history": selection_history,
            "latest_selection": latest_selection,
            **generation_entry,
        },
    )


@login_required
@require_POST
def solution_option_retire(request, pk):
    option = get_object_or_404(
        SolutionOption.objects.select_related("process_analysis__stage__value_stream"),
        pk=pk,
    )
    process_analysis = option.process_analysis
    try:
        retire_solution_option(option=option, actor=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "Lösungsoption kann nicht ausgeblendet werden: " + " ".join(exc.messages),
        )
    else:
        messages.success(
            request,
            f"„{option.name}“ wird nicht weiterverfolgt und bleibt für den "
            "Audit-Nachweis erhalten.",
        )
    comparison_url = reverse(
        "architecture:solution_option_compare",
        kwargs={"pk": process_analysis.pk},
    )
    return redirect(comparison_url)
