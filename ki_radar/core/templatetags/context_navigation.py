from __future__ import annotations

from urllib.parse import urlsplit

from django import template
from django.urls import reverse

from ki_radar.core.navigation import safe_internal_url

register = template.Library()

DOMINANT_ACTION_ROUTES = {
    ("use_cases", "detail"),
    ("delivery", "package_detail"),
    ("architecture", "process_analysis_detail"),
    ("architecture", "value_stream_detail"),
    ("reporting", "outcome_workspace"),
}


def _path(url: str | None) -> str:
    return urlsplit(url or "").path


def _same_destination(left: str | None, right: str | None) -> bool:
    left_path = _path(left)
    return bool(left_path and left_path == _path(right))


def _link(url: str, label: str) -> dict[str, str]:
    return {"url": url, "label": label}


@register.inclusion_tag("includes/context_navigation.html", takes_context=True)
def context_navigation(context):
    request = context["request"]
    match = request.resolver_match
    route = (match.namespace, match.url_name)

    back = None
    overview = None
    use_case = context.get("use_case")
    package = context.get("package")
    process_analysis = context.get("process_analysis")
    value_stream = context.get("value_stream")
    selected_use_case = context.get("selected_use_case")

    if package is not None:
        package_url = package.get_absolute_url()
        use_case_url = package.use_case.get_absolute_url()
        if route == ("delivery", "package_detail"):
            back = _link(use_case_url, "Zum Use Case")
            overview = _link(reverse("delivery:package_list"), "Delivery Übersicht")
        else:
            requested = safe_internal_url(request, context.get("return_to"), package_url)
            if not _same_destination(requested, package_url):
                back = _link(requested, "Zum Arbeitskontext")
                overview = _link(package_url, "Delivery Package")
            else:
                back = _link(package_url, "Zum Delivery Package")
    elif process_analysis is not None:
        process_url = process_analysis.get_absolute_url()
        if route == ("architecture", "process_analysis_detail"):
            back = _link(
                process_analysis.stage.value_stream.get_absolute_url(),
                "Zum Value Stream",
            )
        else:
            back = _link(process_url, "Zur Prozessanalyse")
    elif value_stream is not None:
        value_stream_url = value_stream.get_absolute_url()
        if route == ("architecture", "value_stream_detail"):
            back = _link(reverse("architecture:value_stream_list"), "Value Streams")
        else:
            back = _link(value_stream_url, "Zum Value Stream")
    elif selected_use_case is not None and route == ("reporting", "outcome_workspace"):
        back = _link(selected_use_case.get_absolute_url(), "Zum Use Case")
    elif use_case is not None:
        use_case_url = use_case.get_absolute_url()
        if route == ("use_cases", "detail"):
            back = _link(reverse("use_cases:list"), "Use Cases")
        else:
            requested = safe_internal_url(request, context.get("return_to"), use_case_url)
            if not _same_destination(requested, use_case_url):
                back = _link(requested, "Zum Arbeitskontext")
                overview = _link(use_case_url, "Use Case Übersicht")
            else:
                back = _link(use_case_url, "Zum Use Case")

    recommendation = None
    journey = context.get("journey")
    step = journey.next_action if journey is not None else None
    if route not in DOMINANT_ACTION_ROUTES and step is not None:
        target = step.url
        if target and step.action_method != "post":
            occupied = [request.get_full_path()]
            if back:
                occupied.append(back["url"])
            if overview:
                occupied.append(overview["url"])
            if not any(_same_destination(target, item) for item in occupied):
                recommendation = _link(target, step.action_label or step.label)

    return {
        "back": back,
        "overview": overview,
        "recommendation": recommendation,
    }
