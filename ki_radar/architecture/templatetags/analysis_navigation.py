from django import template
from django.core.exceptions import ObjectDoesNotExist

from ki_radar.architecture.analysis_navigation import build_analysis_navigation

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
    return {"analysis_navigation": _navigation_from_context(context)}


@register.inclusion_tag(
    "architecture/includes/analysis_step_actions.html",
    takes_context=True,
)
def analysis_step_actions(context):
    return {"analysis_navigation": _navigation_from_context(context)}
