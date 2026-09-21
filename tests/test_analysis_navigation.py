from types import SimpleNamespace

import pytest

from ki_radar.architecture.analysis_navigation import (
    analysis_step_url,
    build_analysis_navigation,
)


class AbsoluteUrlObject:
    def __init__(self, url):
        self.url = url

    def get_absolute_url(self):
        return self.url


def journey(*states):
    return SimpleNamespace(
        steps=tuple(SimpleNamespace(key=key, state=state) for key, state in states)
    )


def test_analysis_step_url_preserves_query_and_adds_fragment():
    url = analysis_step_url(
        "/architecture/value-streams/7/?source=portfolio",
        "focus",
    )

    assert url == (
        "/architecture/value-streams/7/?source=portfolio&analysis_step=focus#fokus-priorisierung"
    )


def test_analysis_step_url_rejects_unknown_step():
    with pytest.raises(ValueError, match="Unknown analysis step"):
        analysis_step_url("/architecture/value-streams/7/", "unknown")


def test_navigation_uses_canonical_targets_and_active_step():
    navigation = build_analysis_navigation(
        journey=journey(
            ("value_stream", "complete"),
            ("focus", "complete"),
            ("process", "complete"),
            ("solution", "current"),
        ),
        value_stream=AbsoluteUrlObject("/architecture/value-streams/7/"),
        process_analysis=AbsoluteUrlObject("/architecture/process-analyses/11/"),
        requested_step="focus",
    )

    steps = {step.key: step for step in navigation.steps}
    assert navigation.active_key == "focus"
    assert steps["focus"].is_active is True
    assert steps["focus"].url.endswith("?analysis_step=focus#fokus-priorisierung")
    assert steps["process"].url.endswith("?analysis_step=process#prozessanalyse")
    assert steps["solution"].url.endswith("?analysis_step=solution#loesungsoptionen")
    assert navigation.previous.key == "value_stream"
    assert navigation.next.key == "process"


def test_invalid_requested_step_falls_back_to_page_default():
    navigation = build_analysis_navigation(
        journey=journey(
            ("value_stream", "complete"),
            ("focus", "complete"),
            ("process", "complete"),
            ("solution", "complete"),
        ),
        value_stream=AbsoluteUrlObject("/architecture/value-streams/7/"),
        process_analysis=AbsoluteUrlObject("/architecture/process-analyses/11/"),
        requested_step="invalid",
        default_step="process",
    )

    assert navigation.active_key == "process"
    assert navigation.previous.key == "focus"
    assert navigation.next.key == "solution"


def test_process_steps_remain_unlinked_until_analysis_exists():
    navigation = build_analysis_navigation(
        journey=journey(
            ("value_stream", "complete"),
            ("focus", "current"),
            ("process", "upcoming"),
            ("solution", "upcoming"),
        ),
        value_stream=AbsoluteUrlObject("/architecture/value-streams/7/"),
        requested_step="process",
    )

    steps = {step.key: step for step in navigation.steps}
    assert navigation.active_key == "value_stream"
    assert steps["process"].url is None
    assert steps["solution"].url is None
    assert navigation.previous is None
    assert navigation.next.key == "focus"
