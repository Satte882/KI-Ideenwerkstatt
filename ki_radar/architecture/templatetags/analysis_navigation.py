from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from ki_radar.architecture.analysis_navigation import (
    analysis_step_url,
    build_analysis_navigation,
)

register = template.Library()


def _first_process_analysis(value_stream):
    try:
        focus_decision = value_stream.stage_focus_decision
    except ObjectDoesNotExist:
        focus_decision = None

    if focus_decision is not None:
        analyses = list(focus_decision.selected_stage.process_analyses.all())
        if analyses:
            return analyses[0]

    for stage in value_stream.stages.all():
        analyses = list(stage.process_analyses.all())
        if analyses:
            return analyses[0]
    return None


PROCESS_CONTEXT_ROUTE_KEYS = {
    ("architecture", "process_analysis_detail"): "process",
    ("architecture", "solution_option_compare"): "compare",
    ("accelerator", "investigation_detail"): "brief",
    ("accelerator", "investigation_source"): "brief",
    ("accelerator", "investigation_tool_result"): "brief",
}


def _process_context_from_context(context):
    request = context.get("request")
    if request is None or request.resolver_match is None:
        return None

    active_key = PROCESS_CONTEXT_ROUTE_KEYS.get(
        (request.resolver_match.namespace, request.resolver_match.url_name)
    )
    if active_key is None:
        return None
    if active_key == "process" and getattr(request, "GET", {}).get("analysis_step") == "solution":
        active_key = "solution"

    run = context.get("run")
    process_analysis = context.get("process_analysis")
    if process_analysis is None and run is not None:
        process_analysis = run.process_analysis
    if process_analysis is None:
        return None

    decision_brief_run = run
    if decision_brief_run is None:
        latest_materialization = context.get("latest_investigation_materialization")
        if latest_materialization is not None:
            decision_brief_run = latest_materialization.run
    if decision_brief_run is None:
        decision_brief_run = context.get("latest_investigation_run")
    if decision_brief_run is None:
        decision_brief_run = (
            process_analysis.investigation_runs.filter(evidence_campaign__isnull=True)
            .order_by("-created_at")
            .first()
        )

    value_stream = process_analysis.stage.value_stream
    value_stream_url = value_stream.get_absolute_url()

    process_url = process_analysis.get_absolute_url()

    return {
        "active_key": active_key,
        "value_stream_url": analysis_step_url(value_stream_url, "value_stream"),
        "focus_url": analysis_step_url(value_stream_url, "focus"),
        "process_url": analysis_step_url(process_url, "process"),
        "solution_url": analysis_step_url(process_url, "solution"),
        "decision_brief_url": (
            reverse(
                "accelerator:investigation_detail",
                kwargs={"run_id": decision_brief_run.pk},
            )
            if decision_brief_run is not None
            else None
        ),
        "comparison_url": reverse(
            "architecture:solution_option_compare",
            kwargs={"pk": process_analysis.pk},
        ),
    }


def _navigation_from_context(context):
    request = context.get("request")
    journey = context.get("journey")
    explicit_process = context.get("process_analysis")
    value_stream = context.get("value_stream")

    if explicit_process is not None:
        value_stream = explicit_process.stage.value_stream
    if request is None or journey is None or value_stream is None:
        return None

    process_analysis = explicit_process or _first_process_analysis(value_stream)
    default_step = "process" if explicit_process is not None else "value_stream"
    return build_analysis_navigation(
        journey=journey,
        value_stream=value_stream,
        process_analysis=process_analysis,
        requested_step=request.GET.get("analysis_step"),
        default_step=default_step,
    )


@register.inclusion_tag(
    "architecture/includes/analysis_sidebar.html",
    takes_context=True,
)
def analysis_sidebar(context):
    process_context_navigation = _process_context_from_context(context)
    return {
        "process_context_navigation": process_context_navigation,
        "analysis_navigation": (
            None if process_context_navigation is not None else _navigation_from_context(context)
        ),
    }


@register.inclusion_tag(
    "architecture/includes/analysis_step_actions.html",
    takes_context=True,
)
def analysis_step_actions(context):
    return {"analysis_navigation": _navigation_from_context(context)}
