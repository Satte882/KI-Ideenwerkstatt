from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.core.navigation import requested_return_to, with_return_to

from .blockers import build_blocker_details
from .governance_status import build_governance_statuses
from .lean_decision_forms import (
    ApprovalDecisionForm,
    DecisionAssessmentForm,
    SecondApprovalReviewForm,
)
from .models import ApprovalDecision, UseCase
from .services import (
    approval_check,
    can_review_conditional_decision,
    confirm_conditional_decision,
    create_decision_assessment,
    return_conditional_decision,
    submit_approval_decision,
)
from .status_dimensions import build_use_case_status_dimensions
from .workflow import build_use_case_journey

DECISION_OPTIONS = (
    UseCase.DecisionStatus.DEFERRED,
    UseCase.DecisionStatus.APPROVED,
    UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
    UseCase.DecisionStatus.NOT_PURSUED,
)


def _decision_use_case_queryset():
    return UseCase.objects.select_related(
        "business_unit",
        "business_owner",
        "coordinator",
        "technical_owner",
        "architecture_origin__stage__value_stream",
        "architecture_origin__stage__value_stream__focus",
        "architecture_origin__process_analysis",
        "architecture_origin__solution_option",
    ).prefetch_related(
        "governance_assessments",
        "governance_reviews",
        "decision_assessments",
        "approval_decisions",
        "delivery_packages",
    )


def _selected_decision_status(request, assessment) -> str:
    selected = (
        request.POST.get("decision_status")
        if request.method == "POST"
        else request.GET.get("decision_status")
    )
    return selected if selected in DECISION_OPTIONS else assessment.recommendation


def _decision_choice_url(use_case: UseCase, status: str, return_to: str) -> str:
    query = urlencode({"decision_status": status, "return_to": return_to})
    return f"{reverse('use_cases:approval_decision_create', kwargs={'pk': use_case.pk})}?{query}"


def _available_decision_alternatives(
    *,
    use_case: UseCase,
    actor,
    selected_status: str,
    return_to: str,
) -> list[dict[str, str]]:
    alternatives = []
    for status in DECISION_OPTIONS:
        if status == selected_status:
            continue
        check = approval_check(
            use_case=use_case,
            target_status=status,
            actor=actor,
            governance_confirmed=True,
        )
        if not check.blockers:
            alternatives.append(
                {
                    "status": status,
                    "label": UseCase.DecisionStatus(status).label,
                    "url": _decision_choice_url(use_case, status, return_to),
                }
            )
    return alternatives


@login_required
def assessment_create(request, pk):
    if not is_coordinator(request.user):
        raise PermissionDenied
    use_case = get_object_or_404(_decision_use_case_queryset(), pk=pk)
    return_to = requested_return_to(request, use_case.get_absolute_url())
    if use_case.status != UseCase.Status.REVIEW:
        messages.warning(
            request,
            "Eine strukturierte Bewertung ist ausschließlich im Status Review möglich.",
        )
        return redirect(use_case.get_absolute_url())
    if request.method == "POST":
        form = DecisionAssessmentForm(request.POST)
        if form.is_valid():
            try:
                assessment = create_decision_assessment(
                    use_case=use_case,
                    actor=request.user,
                    data=form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    f"Bewertung v{assessment.version} wurde gespeichert. Confidence: "
                    f"{assessment.confidence_label}.",
                )
                return redirect(return_to)
    else:
        form = DecisionAssessmentForm()
    journey = build_use_case_journey(use_case, request.user)
    return render(
        request,
        "use_cases/assessment_form.html",
        {
            "form": form,
            "use_case": use_case,
            "journey": journey,
            "status_dimensions": build_use_case_status_dimensions(use_case, journey),
            "return_to": return_to,
        },
    )


@login_required
def approval_decision_create(request, pk):
    if not is_coordinator(request.user):
        raise PermissionDenied
    use_case = get_object_or_404(_decision_use_case_queryset(), pk=pk)
    return_to = requested_return_to(request, use_case.get_absolute_url())
    assessment = use_case.decision_assessments.first()
    if assessment is None:
        messages.warning(request, "Vor einer Entscheidung ist eine strukturierte Bewertung nötig.")
        return redirect(
            with_return_to(
                reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk}),
                return_to,
            )
        )

    selected_status = _selected_decision_status(request, assessment)
    if request.method == "POST":
        form = ApprovalDecisionForm(request.POST, actor=request.user, use_case=use_case)
        if form.is_valid():
            selected_status = form.cleaned_data["decision_status"]
            hard_check = approval_check(
                use_case=use_case,
                target_status=selected_status,
                actor=request.user,
                governance_confirmed=True,
            )
            if hard_check.blockers:
                form.add_error(
                    None,
                    (
                        "Die Entscheidung ist nicht ausführbar, solange harte "
                        "Voraussetzungen offen sind."
                    ),
                )
            else:
                try:
                    decision = submit_approval_decision(
                        use_case=use_case,
                        actor=request.user,
                        data=form.cleaned_data,
                    )
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    if decision.is_pending_second_approval:
                        messages.info(
                            request,
                            "Die Freigabe mit Auflagen wurde zur unabhängigen Zweitprüfung "
                            f"an {decision.second_approval_assignee.get_display_name()} "
                            "zugewiesen.",
                        )
                    else:
                        messages.success(request, "Die Entscheidung wurde verbindlich gespeichert.")
                    return redirect(return_to)
    else:
        form = ApprovalDecisionForm(
            initial={"decision_status": selected_status},
            actor=request.user,
            use_case=use_case,
        )

    hard_check = approval_check(
        use_case=use_case,
        target_status=selected_status,
        actor=request.user,
        governance_confirmed=True,
    )
    blocker_details = build_blocker_details(use_case, hard_check.blockers)
    journey = build_use_case_journey(use_case, request.user)
    return render(
        request,
        "use_cases/decision_form.html",
        {
            "form": form,
            "use_case": use_case,
            "assessment": assessment,
            "journey": journey,
            "status_dimensions": build_use_case_status_dimensions(use_case, journey),
            "governance_statuses": build_governance_statuses(use_case),
            "approval_check": hard_check,
            "approval_blocker_details": blocker_details,
            "first_approval_blocker": blocker_details[0] if blocker_details else None,
            "decision_form_enabled": not hard_check.blockers,
            "selected_status": selected_status,
            "selected_status_label": UseCase.DecisionStatus(selected_status).label,
            "decision_alternatives": _available_decision_alternatives(
                use_case=use_case,
                actor=request.user,
                selected_status=selected_status,
                return_to=return_to,
            ),
            "deciding_actor": request.user,
            "return_to": return_to,
        },
    )


@login_required
def second_approval_review(request, decision_id):
    decision = get_object_or_404(
        ApprovalDecision.objects.select_related(
            "use_case__business_owner",
            "use_case__coordinator",
            "assessment__assessed_by",
            "decided_by",
            "condition_owner",
            "second_approval_assignee",
            "second_approved_by",
            "second_approval_returned_by",
        ),
        pk=decision_id,
    )
    from .permissions import can_view_use_case

    if not can_view_use_case(request.user, decision.use_case):
        raise PermissionDenied

    can_act = can_review_conditional_decision(decision=decision, actor=request.user)
    form = SecondApprovalReviewForm(request.POST or None)
    if request.method == "POST":
        if not can_act:
            raise PermissionDenied
        if form.is_valid():
            try:
                if form.cleaned_data["action"] == "confirm":
                    confirm_conditional_decision(decision=decision, actor=request.user)
                    messages.success(request, "Die unabhängige Zweitprüfung wurde bestätigt.")
                else:
                    return_conditional_decision(
                        decision=decision,
                        actor=request.user,
                        reason=form.cleaned_data.get("return_reason", ""),
                    )
                    messages.info(
                        request,
                        "Die Entscheidung wurde zur Überarbeitung zurückgegeben.",
                    )
            except (PermissionDenied, ValidationError) as exc:
                form.add_error(None, exc)
            else:
                return redirect(decision.use_case)

    return render(
        request,
        "use_cases/second_approval_review.html",
        {
            "decision": decision,
            "use_case": decision.use_case,
            "assessment": decision.assessment,
            "governance_statuses": build_governance_statuses(decision.use_case),
            "form": form,
            "can_act": can_act,
        },
    )
