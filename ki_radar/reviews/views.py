from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_workspace import (
    build_outcome_workspace_journey,
    outcome_workspace_url,
)
from ki_radar.use_cases.permissions import can_end_use_case, can_start_pilot
from ki_radar.use_cases.scale_readiness import evaluate_scale_readiness
from ki_radar.use_cases.services import current_decision_check

from .lean_forms import ReviewForm
from .models import Review
from .services import create_review


@login_required
def review_create(request, use_case_id):
    use_case = get_object_or_404(
        UseCase.objects.select_related("business_owner", "technical_owner").prefetch_related(
            "governance_assessments",
            "governance_reviews",
            "delivery_packages",
        ),
        pk=use_case_id,
    )
    requested_action = request.GET.get("action")
    posted_decision = request.POST.get("decision") if request.method == "POST" else ""
    coordinator_access = is_coordinator(request.user)

    pilot_start_only = requested_action == "pilot_start" or (
        posted_decision == Review.Decision.START_PILOT and not coordinator_access
    )
    end_only = requested_action == "closure" or (
        posted_decision == Review.Decision.END and not coordinator_access
    )

    if pilot_start_only:
        if not can_start_pilot(request.user, use_case):
            raise PermissionDenied
    elif end_only:
        if not can_end_use_case(request.user, use_case):
            raise PermissionDenied
    elif not coordinator_access:
        raise PermissionDenied

    if request.method == "POST":
        form = ReviewForm(
            request.POST,
            use_case=use_case,
            actor=request.user,
            pilot_start_only=pilot_start_only,
            requested_action=requested_action,
        )
        if form.is_valid():
            try:
                create_review(use_case=use_case, actor=request.user, data=form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, exc)
            else:
                if pilot_start_only:
                    messages.success(request, "Der Pilot wurde verbindlich gestartet.")
                    return redirect(outcome_workspace_url("pilot", use_case=use_case))
                if form.cleaned_data.get("decision") == Review.Decision.END:
                    messages.success(request, "Der Use Case wurde fachlich beendet.")
                    return redirect(outcome_workspace_url("closure", use_case=use_case))
                messages.success(request, "Review und Entscheidung wurden gespeichert.")
                if form.scale_readiness_result is not None:
                    return redirect(outcome_workspace_url("decision", use_case=use_case))
                return redirect(use_case)
    else:
        form = ReviewForm(
            use_case=use_case,
            actor=request.user,
            pilot_start_only=pilot_start_only,
            requested_action=requested_action,
        )
    return render(
        request,
        "reviews/form.html",
        {
            "form": form,
            "use_case": use_case,
            "decision_check": current_decision_check(use_case),
            "pilot_start_only": pilot_start_only,
            "journey": build_outcome_workspace_journey(use_case, request.user),
        },
    )


@login_required
@require_POST
def scale_readiness_preview(request, use_case_id):
    if not is_coordinator(request.user):
        raise PermissionDenied
    use_case = get_object_or_404(
        UseCase.objects.select_related("business_owner", "technical_owner").prefetch_related(
            "governance_assessments",
            "governance_reviews",
            "delivery_packages",
        ),
        pk=use_case_id,
    )
    result = evaluate_scale_readiness(use_case, request.POST)
    return render(
        request,
        "reviews/includes/scale_readiness_summary.html",
        {"scale_result": result, "use_case": use_case, "is_preview_update": True},
    )


@login_required
def monthly_review(request):
    if not is_coordinator(request.user):
        raise PermissionDenied
    today = timezone.localdate()
    queryset = (
        UseCase.objects.filter(is_archived=False)
        .exclude(status=UseCase.Status.ENDED)
        .select_related("business_owner", "business_unit")
    )
    context = {
        "today": today,
        "overdue": queryset.filter(next_review_date__lt=today),
        "due_soon": queryset.filter(
            next_review_date__gte=today, next_review_date__lte=today + timedelta(days=30)
        ),
        "missing_review_date": queryset.filter(next_review_date__isnull=True),
        "stale": queryset.filter(updated_at__date__lt=today - timedelta(days=60)),
        "pilots_without_result": queryset.filter(status=UseCase.Status.PILOT, metric_actual=None),
        "missing_governance": queryset.filter(governance_assessments__isnull=True).distinct(),
    }
    return render(request, "reviews/monthly.html", context)
