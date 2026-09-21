from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.status_dimensions import build_use_case_status_dimensions
from ki_radar.use_cases.workflow import build_use_case_journey

from .forms import GovernanceAssessmentForm, GovernanceReviewForm
from .models import GovernanceReview
from .services import (
    REVIEW_DEFINITIONS,
    create_screening_review_artifacts,
    current_governance_status,
    latest_review_for_screening,
    review_definition,
    review_history,
    sync_completion_from_review,
)


def _next_required_review(use_case: UseCase) -> str | None:
    governance = current_governance_status(use_case)
    if not governance.incomplete_required_reviews:
        return None
    return governance.incomplete_required_reviews[0].definition.review_type


def _next_url(use_case: UseCase) -> str:
    next_review = _next_required_review(use_case)
    if next_review:
        return reverse(
            "governance:review",
            kwargs={"use_case_id": use_case.pk, "review_type": next_review},
        )
    if use_case.decision_assessments.exists():
        return reverse("use_cases:approval_decision_create", kwargs={"pk": use_case.pk})
    return use_case.get_absolute_url()


def _page_context(use_case: UseCase, user) -> dict:
    journey = build_use_case_journey(use_case, user)
    return {
        "journey": journey,
        "status_dimensions": build_use_case_status_dimensions(use_case, journey),
    }


@login_required
@transaction.atomic
def assessment_create(request, use_case_id):
    if not is_coordinator(request.user):
        raise PermissionDenied
    use_case = get_object_or_404(UseCase, pk=use_case_id)
    if request.method == "POST":
        form = GovernanceAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.use_case = use_case
            assessment.reviewer = request.user
            assessment._history_user = request.user
            assessment.save()

            update_fields = ["updated_at"]
            for config in REVIEW_DEFINITIONS.values():
                required = getattr(assessment, config.required_field)
                setattr(use_case, config.required_field, required)
                setattr(use_case, config.completed_field, False)
                update_fields.extend([config.required_field, config.completed_field])
            use_case._history_user = request.user
            use_case.save(update_fields=update_fields)
            create_screening_review_artifacts(assessment=assessment, actor=request.user)

            decision_assessment = use_case.decision_assessments.first()
            if decision_assessment is not None:
                decision_assessment.governance_precheck_completed = True
                decision_assessment.save(update_fields=["governance_precheck_completed"])

            messages.success(
                request,
                "Governance-Screening wurde gespeichert. Für alle Fachbereiche wurden "
                "nachvollziehbare Statusartefakte angelegt.",
            )
            return redirect(_next_url(use_case))
    else:
        form = GovernanceAssessmentForm()
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "use_case": use_case,
            **_page_context(use_case, request.user),
        },
    )


@login_required
@transaction.atomic
def review_create(request, use_case_id, review_type):
    if not is_coordinator(request.user):
        raise PermissionDenied
    if review_type not in REVIEW_DEFINITIONS:
        raise Http404

    use_case = get_object_or_404(UseCase, pk=use_case_id)
    governance = current_governance_status(use_case)
    screening = governance.screening
    if screening is None:
        messages.warning(
            request,
            "Vor einer Fachprüfung muss zuerst das Governance-Screening abgeschlossen werden.",
        )
        return redirect("governance:create", use_case_id=use_case.pk)

    config = review_definition(review_type)
    state = next(item for item in governance.reviews if item.definition.review_type == review_type)
    required = state.required
    latest_review = latest_review_for_screening(
        use_case=use_case,
        review_type=review_type,
        screening=screening,
    )
    history = review_history(use_case=use_case, review_type=review_type)
    form = None

    if required:
        if request.method == "POST":
            form = GovernanceReviewForm(
                request.POST,
                responsible_role=config.responsible_role,
            )
            if form.is_valid():
                review = form.save(commit=False)
                review.use_case = use_case
                review.screening = screening
                review.review_type = review_type
                review.status = GovernanceReview.Status.COMPLETED
                review.reviewer = request.user
                try:
                    review.full_clean()
                except ValidationError as exc:
                    for field_name, field_errors in exc.message_dict.items():
                        target = field_name if field_name in form.fields else None
                        for error in field_errors:
                            form.add_error(target, error)
                else:
                    review._history_user = request.user
                    review.save()
                    sync_completion_from_review(
                        use_case=use_case,
                        review=review,
                        actor=request.user,
                    )
                    messages.success(
                        request,
                        f"{config.label} wurde als eigenständiges Prüfartefakt gespeichert.",
                    )
                    return redirect(_next_url(use_case))
        else:
            form = GovernanceReviewForm(responsible_role=config.responsible_role)

    return render(
        request,
        "governance/review_form.html",
        {
            "use_case": use_case,
            "screening": screening,
            "review_type": review_type,
            "review_label": config.label,
            "review_required": required,
            "review_rationale": screening.review_rationale(review_type),
            "latest_review": latest_review,
            "review_history": history,
            "form": form,
            **_page_context(use_case, request.user),
        },
    )
