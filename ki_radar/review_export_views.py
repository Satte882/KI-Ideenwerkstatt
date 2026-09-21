from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.review_export import (
    build_process_review_context,
    build_use_case_review_context,
    build_value_stream_review_context,
    render_review_markdown,
)
from ki_radar.review_export_security import sanitize_external_markdown
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_view_use_case


def _markdown_response(content: str, *, filename_stem: str) -> HttpResponse:
    safe_stem = slugify(filename_stem) or "llm-review"
    response = HttpResponse(
        sanitize_external_markdown(content),
        content_type="text/markdown; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{safe_stem}.md"'
    return response


@login_required
@require_GET
def value_stream_review_export(request, pk):
    value_stream = get_object_or_404(
        ValueStream.objects.select_related("business_unit", "focus").prefetch_related("stages"),
        pk=pk,
    )
    context = build_value_stream_review_context(value_stream, request.user)
    return _markdown_response(
        render_review_markdown(context),
        filename_stem=f"llm-review-value-stream-{value_stream.name}",
    )


@login_required
@require_GET
def process_review_export(request, pk):
    process_analysis = get_object_or_404(
        ProcessAnalysis.objects.select_related(
            "stage__value_stream__business_unit",
            "stage__value_stream__focus",
        ).prefetch_related(
            "validations",
            "solution_options",
            "solution_selection_decisions__selected_option",
        ),
        pk=pk,
    )
    context = build_process_review_context(process_analysis, request.user)
    return _markdown_response(
        render_review_markdown(context),
        filename_stem=f"llm-review-process-{process_analysis.name}",
    )


@login_required
@require_GET
def use_case_review_export(request, pk):
    use_case = get_object_or_404(
        UseCase.objects.select_related(
            "business_unit",
            "business_owner",
            "coordinator",
            "technical_owner",
            "classification",
            "architecture_origin__stage__value_stream",
            "architecture_origin__stage__value_stream__focus",
            "architecture_origin__process_analysis",
            "architecture_origin__solution_option",
        ).prefetch_related(
            "decision_assessments",
            "governance_assessments",
            "reviews",
            "delivery_packages__section_reviews",
        ),
        pk=pk,
    )
    if not can_view_use_case(request.user, use_case):
        raise PermissionDenied
    context = build_use_case_review_context(use_case, request.user)
    return _markdown_response(
        render_review_markdown(context),
        filename_stem=f"llm-review-{use_case.short_id or use_case.title}",
    )
