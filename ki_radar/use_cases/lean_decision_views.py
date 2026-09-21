from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.core.navigation import requested_return_to

from . import decision_views as legacy
from .models import UseCase
from .services import approval_check, submit_approval_decision
from .status_dimensions import build_use_case_status_dimensions
from .workflow import build_use_case_journey

NEGATIVE_DECISION_OPTIONS = (
    (UseCase.DecisionStatus.DEFERRED, UseCase.DecisionStatus.DEFERRED.label),
    (UseCase.DecisionStatus.NOT_PURSUED, UseCase.DecisionStatus.NOT_PURSUED.label),
)


class NegativeDecisionForm(forms.Form):
    decision_status = forms.ChoiceField(
        choices=NEGATIVE_DECISION_OPTIONS,
        label="Entscheidung",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    rationale = forms.CharField(
        label="Entscheidungsbegründung",
        widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
    )


def _selected_negative_status(request) -> str:
    selected = (
        request.POST.get("decision_status")
        if request.method == "POST"
        else request.GET.get("decision_status")
    )
    allowed = {value for value, _label in NEGATIVE_DECISION_OPTIONS}
    return selected if selected in allowed else UseCase.DecisionStatus.DEFERRED


@login_required
def approval_decision_create(request, pk):
    """Allow an early negative portfolio decision without forcing an assessment.

    Once an assessment exists, the established decision workspace remains the canonical UI.
    Positive approvals are intentionally unavailable here and continue to require an assessment.
    """

    if not is_coordinator(request.user):
        raise PermissionDenied

    use_case = get_object_or_404(legacy._decision_use_case_queryset(), pk=pk)
    if use_case.decision_assessments.exists():
        return legacy.approval_decision_create(request, pk)
    if use_case.status != UseCase.Status.REVIEW:
        messages.warning(
            request,
            (
                "Eine Portfolioentscheidung ohne Bewertung ist ausschließlich "
                "im Status Review möglich."
            ),
        )
        return redirect(use_case)

    return_to = requested_return_to(request, use_case.get_absolute_url())
    selected_status = _selected_negative_status(request)
    form = NegativeDecisionForm(
        request.POST or None,
        initial={"decision_status": selected_status},
    )

    if request.method == "POST" and form.is_valid():
        selected_status = form.cleaned_data["decision_status"]
        check = approval_check(
            use_case=use_case,
            target_status=selected_status,
            actor=request.user,
        )
        if check.blockers:
            form.add_error(None, "Die Entscheidung ist derzeit nicht ausführbar.")
        else:
            try:
                submit_approval_decision(
                    use_case=use_case,
                    actor=request.user,
                    data={
                        "decision_status": selected_status,
                        "rationale": form.cleaned_data["rationale"],
                        "governance_confirmed": False,
                        "conditions": "",
                        "condition_owner": None,
                        "condition_due_date": None,
                        "second_approval_assignee": None,
                    },
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Die Portfolioentscheidung wurde verbindlich gespeichert.",
                )
                return redirect(return_to)

    check = approval_check(
        use_case=use_case,
        target_status=selected_status,
        actor=request.user,
    )
    journey = build_use_case_journey(use_case, request.user)
    return render(
        request,
        "use_cases/negative_decision_form.html",
        {
            "form": form,
            "use_case": use_case,
            "journey": journey,
            "status_dimensions": build_use_case_status_dimensions(use_case, journey),
            "approval_check": check,
            "selected_status": selected_status,
            "selected_status_label": UseCase.DecisionStatus(selected_status).label,
            "assessment_url": reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk}),
            "return_to": return_to,
        },
    )
