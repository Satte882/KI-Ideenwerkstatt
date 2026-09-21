from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ANALYSIS_STEP_PARAMETER = "analysis_step"
ANALYSIS_STEP_DEFINITIONS = (
    ("value_stream", "Value Stream", "value-stream"),
    ("focus", "Fokus & Priorisierung", "fokus-priorisierung"),
    ("process", "Prozessanalyse", "prozessanalyse"),
    ("solution", "Lösungsoptionen", "loesungsoptionen"),
)
ANALYSIS_STEP_KEYS = frozenset(key for key, _, _ in ANALYSIS_STEP_DEFINITIONS)


@dataclass(frozen=True)
class AnalysisNavigationStep:
    key: str
    label: str
    state: str
    url: str | None
    is_active: bool


@dataclass(frozen=True)
class AnalysisNavigation:
    steps: tuple[AnalysisNavigationStep, ...]
    active_key: str
    previous: AnalysisNavigationStep | None
    next: AnalysisNavigationStep | None


def analysis_step_url(base_url: str, step_key: str) -> str:
    """Return the canonical, durable URL for a local analysis step."""
    fragments = {key: fragment for key, _, fragment in ANALYSIS_STEP_DEFINITIONS}
    if step_key not in fragments:
        raise ValueError(f"Unknown analysis step: {step_key}")

    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[ANALYSIS_STEP_PARAMETER] = step_key
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            fragments[step_key],
        )
    )


def build_analysis_navigation(
    *,
    journey,
    value_stream,
    process_analysis=None,
    requested_step: str | None = None,
    default_step: str = "value_stream",
) -> AnalysisNavigation:
    journey_steps = {step.key: step for step in getattr(journey, "steps", ())}
    value_stream_url = value_stream.get_absolute_url()
    process_url = process_analysis.get_absolute_url() if process_analysis is not None else None

    target_urls = {
        "value_stream": analysis_step_url(value_stream_url, "value_stream"),
        "focus": analysis_step_url(value_stream_url, "focus"),
        "process": analysis_step_url(process_url, "process") if process_url else None,
        "solution": analysis_step_url(process_url, "solution") if process_url else None,
    }
    available_keys = {key for key, url in target_urls.items() if url}

    if requested_step in ANALYSIS_STEP_KEYS and requested_step in available_keys:
        active_key = requested_step
    elif default_step in available_keys:
        active_key = default_step
    else:
        active_key = next(iter(available_keys), "value_stream")

    steps = tuple(
        AnalysisNavigationStep(
            key=key,
            label=label,
            state=getattr(journey_steps.get(key), "state", "upcoming"),
            url=target_urls[key],
            is_active=key == active_key,
        )
        for key, label, _ in ANALYSIS_STEP_DEFINITIONS
    )
    available_steps = [step for step in steps if step.url]
    active_index = next(
        (index for index, step in enumerate(available_steps) if step.key == active_key),
        0,
    )
    previous_step = available_steps[active_index - 1] if active_index > 0 else None
    next_step = (
        available_steps[active_index + 1] if active_index + 1 < len(available_steps) else None
    )
    return AnalysisNavigation(
        steps=steps,
        active_key=active_key,
        previous=previous_step,
        next=next_step,
    )
