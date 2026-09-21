from __future__ import annotations

from urllib.parse import urlencode

from django import template
from django.urls import reverse

register = template.Library()

SELECTION_WORKFLOW = (
    ("discovery", "Discovery", ("value_stream",)),
    ("focus", "Fokus & Priorisierung", ("focus",)),
    ("use_cases", "Use Cases", ("process", "solution", "use_case")),
    ("assessment", "Bewertung", ("assessment",)),
    ("governance", "Governance", ("governance",)),
    ("approval", "Freigabe", ("approval",)),
    ("delivery", "Delivery", ("delivery",)),
)
OUTCOME_WORKFLOW = (
    ("handover", "Übergabe", ("handover",)),
    ("pilot", "Pilot", ("pilot",)),
    ("measurement", "Wirkung", ("measurement",)),
    ("outcome_decision", "Ergebnisentscheidung", ("outcome_decision",)),
    ("operation", "Betrieb", ("operation",)),
    ("closure", "Abschluss", ("closure",)),
)
WORKFLOW = SELECTION_WORKFLOW
OUTCOME_STEP_KEYS = {key for key, _label, _raw_keys in OUTCOME_WORKFLOW}
OUTCOME_STAGE_TO_STEP = {
    "handover": "handover",
    "pilot": "pilot",
    "effect": "measurement",
    "decision": "outcome_decision",
    "operation": "operation",
    "closure": "closure",
}
CONTEXT_STEP_PREFERENCE = {
    "discovery": ("value_stream",),
    "focus": ("focus",),
    "use_cases": ("use_case", "solution", "process"),
    "assessment": ("assessment",),
    "governance": ("governance",),
    "approval": ("approval",),
    "delivery": ("delivery",),
}


def _aggregate_state(raw_steps, keys):
    states = [step.state for step in raw_steps if step.key in keys]
    if not states:
        return "optional"
    if "blocked" in states:
        return "blocked"
    if "current" in states:
        return "current"
    if all(state == "optional" for state in states):
        return "optional"
    if "upcoming" in states:
        return "upcoming"
    if "complete" in states:
        return "complete"
    return "upcoming"


def _is_outcome_workspace(journey, request):
    resolver = request.resolver_match
    is_outcome_route = bool(
        resolver and resolver.namespace == "reporting" and resolver.url_name == "outcome_workspace"
    )
    has_outcome_steps = bool(
        journey and any(step.key in OUTCOME_STEP_KEYS for step in journey.steps)
    )
    return is_outcome_route or has_outcome_steps


def _workflow_definition(journey, request):
    if not _is_outcome_workspace(journey, request):
        return [(*definition, False) for definition in SELECTION_WORKFLOW]
    return [(*definition, False) for definition in OUTCOME_WORKFLOW]


def _selection_route_states(request):
    resolver = request.resolver_match
    namespace = resolver.namespace if resolver else ""
    url_name = resolver.url_name if resolver else ""
    states = {key: "context" for key, _label, _keys in SELECTION_WORKFLOW}

    if namespace == "architecture":
        states.update(
            discovery="current",
            focus="upcoming",
            use_cases="upcoming",
            assessment="upcoming",
            governance="upcoming",
            approval="upcoming",
            delivery="upcoming",
        )
    elif namespace == "use_cases" and url_name == "assessment_create":
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="complete",
            assessment="current",
            governance="upcoming",
            approval="upcoming",
            delivery="upcoming",
        )
    elif namespace == "governance":
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="complete",
            assessment="complete",
            governance="current",
            approval="upcoming",
            delivery="upcoming",
        )
    elif namespace == "use_cases" and url_name == "approval_decision_create":
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="complete",
            assessment="complete",
            governance="complete",
            approval="current",
            delivery="upcoming",
        )
    elif namespace == "use_cases":
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="current",
            assessment="upcoming",
            governance="upcoming",
            approval="upcoming",
            delivery="upcoming",
        )
    elif namespace == "delivery":
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="complete",
            assessment="complete",
            governance="complete",
            approval="complete",
            delivery="current",
        )
    elif namespace == "reviews" or (namespace == "reporting" and url_name == "dashboard"):
        states.update(
            discovery="optional",
            focus="optional",
            use_cases="complete",
            assessment="complete",
            governance="complete",
            approval="current",
            delivery="upcoming",
        )
    return states


def _outcome_current_step(request):
    current_stage = request.GET.get("stage", "pilot")
    return OUTCOME_STAGE_TO_STEP.get(current_stage, "pilot")


def _outcome_route_states(request):
    current_step = _outcome_current_step(request)
    states = {key: "upcoming" for key, _label, _keys in OUTCOME_WORKFLOW}
    states[current_step] = "current"
    return states


def _outcome_link(request, stage):
    query = {"stage": stage}
    if request.GET.get("use_case"):
        query["use_case"] = request.GET["use_case"]
    return f"{reverse('reporting:outcome_workspace')}?{urlencode(query)}"


def _global_links(request):
    return {
        "discovery": reverse("architecture:value_stream_list"),
        "focus": reverse("architecture:value_stream_list"),
        "use_cases": reverse("use_cases:list"),
        "assessment": reverse("reporting:portfolio"),
        "governance": reverse("reporting:dashboard"),
        "approval": reverse("reporting:dashboard"),
        "delivery": reverse("delivery:package_list"),
        "handover": _outcome_link(request, "handover"),
        "pilot": _outcome_link(request, "pilot"),
        "measurement": _outcome_link(request, "effect"),
        "outcome_decision": _outcome_link(request, "decision"),
        "operation": _outcome_link(request, "operation"),
        "closure": _outcome_link(request, "closure"),
    }


def _links(journey, request):
    links = _global_links(request)
    if journey is None or _is_outcome_workspace(journey, request):
        return links

    raw_steps = {step.key: step for step in journey.steps}
    for workflow_key, preferred_keys in CONTEXT_STEP_PREFERENCE.items():
        contextual = next(
            (
                raw_steps[step_key].url
                for step_key in preferred_keys
                if step_key in raw_steps and raw_steps[step_key].url
            ),
            None,
        )
        if contextual:
            links[workflow_key] = contextual
    return links


def _contextual_step(raw_steps, workflow_key):
    preferred_keys = CONTEXT_STEP_PREFERENCE.get(workflow_key, ())
    candidates = [step for step in raw_steps if step.key in preferred_keys]
    actionable = next(
        (
            step
            for step in candidates
            if step.state in {"current", "blocked"} and step.url and step.action_method != "post"
        ),
        None,
    )
    if actionable is not None:
        return actionable
    for preferred_key in preferred_keys:
        completed = next(
            (
                step
                for step in candidates
                if step.key == preferred_key
                and step.state == "complete"
                and step.url
                and step.action_method != "post"
            ),
            None,
        )
        if completed is not None:
            return completed
    return None


def _local_label(workflow_key, default_label, raw_steps, contextual_step):
    if workflow_key != "use_cases":
        return default_label
    if contextual_step is not None:
        return contextual_step.label
    if any(step.key == "use_case" and step.state == "complete" for step in raw_steps):
        return "Use Case"
    if any(step.key == "solution" and step.state == "complete" for step in raw_steps):
        return "Lösungsoption"
    if any(step.key == "process" and step.state == "complete" for step in raw_steps):
        return "Prozessanalyse"
    return "Prozess & Use Case"


@register.simple_tag
def workflow_steps(journey, request):
    definitions = _workflow_definition(journey, request)
    links = _links(journey, request)
    raw_steps = journey.steps if journey else ()
    selection_states = _selection_route_states(request)
    outcome_states = _outcome_route_states(request)
    is_outcome_workspace = _is_outcome_workspace(journey, request)
    selected_outcome_step = _outcome_current_step(request)
    result = []
    for key, label, raw_keys, divider_before in definitions:
        if journey:
            state = _aggregate_state(raw_steps, raw_keys)
        elif key in selection_states:
            state = selection_states[key]
        else:
            state = outcome_states[key]
        contextual_step = None if is_outcome_workspace else _contextual_step(raw_steps, key)
        local_url = ""
        if is_outcome_workspace:
            local_url = links[key]
        elif state in {"complete", "current", "blocked"} and contextual_step is not None:
            local_url = contextual_step.url
        result.append(
            {
                "key": key,
                "label": label,
                "state": state,
                "url": links[key],
                "local_url": local_url,
                "local_label": _local_label(key, label, raw_steps, contextual_step),
                "divider_before": divider_before,
                "view_active": is_outcome_workspace and key == selected_outcome_step,
            }
        )
    return result


@register.filter
def local_step_group(step_key):
    if step_key in {"value_stream", "focus", "process", "solution"}:
        return "analysis"
    if step_key in {"use_case", "assessment", "approval", "delivery"}:
        return "initiative"
    if step_key in OUTCOME_STEP_KEYS:
        return "outcome"
    return ""
