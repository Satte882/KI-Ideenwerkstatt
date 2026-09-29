"""Read-only projection of the AP2 decision basis and focused factual clarification."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ki_radar.architecture.architecture_advisor import explain_architecture
from ki_radar.architecture.architecture_assessment_models import SolutionArchitectureAssessment
from ki_radar.governance.services import current_governance_status

from .ap2_decision_governance import (
    GOVERNANCE_FIELDS,
    QUESTION_LABELS,
    AP2DecisionGovernanceError,
    answer_ap2_governance_unknowns,
)
from .models import UseCase
from .permissions import can_edit_use_case, can_view_use_case


@login_required
def ap2_decision_surface(request, pk):
    use_case = get_object_or_404(UseCase, pk=pk)
    if not can_view_use_case(request.user, use_case):
        raise PermissionDenied
    try:
        origin = use_case.architecture_origin
    except ObjectDoesNotExist as exc:
        raise PermissionDenied(
            "Diese Entscheidungsgrundlage benötigt einen Architecture-Ursprung."
        ) from exc
    process = origin.process_analysis
    option = origin.solution_option
    if process is None or option is None:
        raise PermissionDenied("Diese Entscheidungsgrundlage benötigt eine gewählte AI-Lösung.")
    selection = process.solution_selection_decisions.order_by("-decided_at").first()
    selection_is_current = bool(selection and selection.selected_option_id == option.pk)
    if not option.starts_ai_use_case:
        raise PermissionDenied("Eine menschlich ausgewählte AI-Lösung ist erforderlich.")
    draft = use_case.ap2_governance_draft or {}
    if request.method == "POST":
        if not can_edit_use_case(request.user, use_case) or not selection_is_current:
            raise PermissionDenied
        facts = draft.get("facts", {})
        unknown_names = [
            name for name in GOVERNANCE_FIELDS if facts.get(name, {}).get("value") == "unknown"
        ]
        try:
            answer_ap2_governance_unknowns(
                use_case=use_case,
                actor=request.user,
                source_hash=request.POST.get("source_hash", ""),
                answers={name: request.POST.get(name, "") for name in unknown_names},
            )
        except (ValidationError, AP2DecisionGovernanceError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, "Governance-Fakten wurden geklärt und das Screening vorbereitet."
            )
        return redirect(reverse("use_cases:ap2_decision_surface", kwargs={"pk": pk}))

    architecture = SolutionArchitectureAssessment.objects.filter(solution_option=option).first()
    architecture_open_points = (
        explain_architecture(
            architecture.architecture_mode,
            architecture.reason_codes,
        ).open_points
        if architecture
        else ()
    )
    governance = current_governance_status(use_case)
    governance_facts = [
        {
            "name": name,
            "question": QUESTION_LABELS[name],
            "value": draft["facts"][name]["value"],
            "value_label": {
                "yes": "Ja",
                "no": "Nein",
                "unknown": "Unbekannt",
            }.get(draft["facts"][name]["value"], "Unbekannt"),
            "rationale": draft["facts"][name]["rationale"],
            "source_ids": draft["facts"][name]["source_ids"],
        }
        for name in GOVERNANCE_FIELDS
        if name in draft.get("facts", {})
    ]
    unknowns = [
        {
            "name": name,
            "question": QUESTION_LABELS[name],
            "rationale": draft["facts"][name]["rationale"],
        }
        for name in GOVERNANCE_FIELDS
        if draft.get("facts", {}).get(name, {}).get("value") == "unknown"
    ]
    options = list(process.solution_options.order_by("name"))
    return render(
        request,
        "use_cases/ap2_decision_surface.html",
        {
            "use_case": use_case,
            "process": process,
            "selection": selection,
            "selection_is_current": selection_is_current,
            "option": option,
            "options": options,
            "architecture": architecture,
            "architecture_open_points": architecture_open_points,
            "assessment": use_case.decision_assessments.first(),
            "governance": governance,
            "draft": draft,
            "unknowns": unknowns,
            "governance_facts": governance_facts,
            "planning_unknowns": use_case.ap2_planning_provenance.get("unknowns", []),
            "can_answer": can_edit_use_case(request.user, use_case),
        },
    )
