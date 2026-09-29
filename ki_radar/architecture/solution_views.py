from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ki_radar.accelerator.investigation_models import InvestigationMaterialization
from ki_radar.accelerator.solution_generation_entry import (
    build_solution_generation_entry_context,
)
from ki_radar.use_cases.services import create_use_case_from_selected_solution

from .forms import SolutionSelectionForm
from .models import ProcessAnalysis, SolutionOption
from .permissions import can_edit_value_stream
from .process_decision_presentation import suggested_confirmed_cause
from .solution_retirement import retire_solution_option
from .solution_selection import (
    comparison_blockers,
    confirm_diagnosis_and_select_solution,
    diagnosis_readiness_blockers,
    focus_readiness_blockers,
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
    focus_blockers = focus_readiness_blockers(process_analysis)
    incomplete_options = [option for option in options if not option.comparison_complete]
    can_select = can_edit_value_stream(
        request.user,
        process_analysis.stage.value_stream,
    )
    generation_entry = build_solution_generation_entry_context(process_analysis)
    selection_history = process_analysis.solution_selection_decisions.all()
    latest_selection = selection_history.first()
    latest_investigation_materialization = (
        InvestigationMaterialization.objects.select_related("run", "brief_revision")
        .filter(
            run__process_analysis=process_analysis,
            run__evidence_campaign__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    diagnosis_confirmation_required = diagnosis_blockers == ["bestätigte Ursache"]
    confirmed_cause_candidate = suggested_confirmed_cause(
        process_analysis=process_analysis,
        latest_materialization=latest_investigation_materialization,
    )
    form = SolutionSelectionForm(
        request.POST or None,
        options=options,
        confirmed_causes_initial=confirmed_cause_candidate,
        process_version=process_analysis.version,
        require_diagnosis_confirmation=diagnosis_confirmation_required,
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
                if diagnosis_confirmation_required:
                    decision = confirm_diagnosis_and_select_solution(
                        process_analysis=process_analysis,
                        selected_option=form.cleaned_data["selected_option"],
                        confirmed_causes=form.cleaned_data["confirmed_causes"],
                        rationale=form.cleaned_data["rationale"],
                        expected_process_version=form.cleaned_data["process_version"],
                        actor=request.user,
                    )
                else:
                    decision = select_preferred_solution(
                        process_analysis=process_analysis,
                        selected_option=form.cleaned_data["selected_option"],
                        rationale=form.cleaned_data["rationale"],
                        actor=request.user,
                    )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if decision.selected_option.starts_ai_use_case:
                    try:
                        use_case_result = create_use_case_from_selected_solution(
                            decision=decision,
                            actor=request.user,
                        )
                    except (PermissionDenied, ValidationError) as exc:
                        messages.warning(
                            request,
                            "Die Lösungsentscheidung ist gespeichert; der direkte AI-Use-Case-"
                            "Handoff benötigt noch Klärung: "
                            + " ".join(exc.messages),
                        )
                    else:
                        verb = "erzeugt" if use_case_result.created else "wiederverwendet"
                        messages.success(
                            request,
                            f"AI-Use-Case {use_case_result.use_case.short_id} wurde "
                            f"{verb}; die Lösungsentscheidung bleibt die Herkunft.",
                        )
                else:
                    messages.success(
                        request,
                        "Non-AI-Lösung verbindlich ausgewählt; es wurde bewusst kein "
                        "KI-Use-Case erzeugt.",
                    )
                if diagnosis_confirmation_required:
                    messages.success(
                        request,
                        "Kernbefund und bevorzugte Lösungsoption wurden auditierbar bestätigt.",
                    )
                comparison_url = reverse(
                    "architecture:solution_option_compare",
                    kwargs={"pk": process_analysis.pk},
                )
                return redirect(f"{comparison_url}#selection-result")

    selected_use_case = None
    if latest_selection is not None:
        selected_origin = (
            latest_selection.selected_option.use_case_origins.select_related("use_case")
            .order_by("-created_at")
            .first()
        )
        if selected_origin is not None:
            selected_use_case = selected_origin.use_case

    return render(
        request,
        "architecture/solution_option_compare.html",
        {
            "process_analysis": process_analysis,
            "options": options,
            "blockers": blockers,
            "diagnosis_blockers": diagnosis_blockers,
            "focus_blockers": focus_blockers,
            "selection_blocked": bool(
                blockers
                or focus_blockers
                or (diagnosis_blockers and not diagnosis_confirmation_required)
            ),
            "diagnosis_confirmation_required": diagnosis_confirmation_required,
            "confirmed_cause_candidate": confirmed_cause_candidate,
            "incomplete_options": incomplete_options,
            "needs_more_options": len(options) < 2,
            "form": form,
            "can_select": can_select,
            "selection_history": selection_history,
            "latest_selection": latest_selection,
            "selected_use_case": selected_use_case,
            "latest_investigation_materialization": latest_investigation_materialization,
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
