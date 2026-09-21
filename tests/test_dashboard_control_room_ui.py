from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


TEMPLATE = read_repo_text("templates", "reporting", "dashboard.html")
CSS = read_repo_text("static", "css", "ui-control-room-dashboard.css")


def test_dashboard_opts_into_control_room_cross_section_pattern():
    assert "{% block body_class %}page-dashboard{% endblock %}" in TEMPLATE
    assert "css/ui-control-room-primitives.css" in TEMPLATE
    assert "css/ui-control-room-dashboard.css" in TEMPLATE
    assert TEMPLATE.index("css/ui-control-room-primitives.css") < TEMPLATE.index(
        "css/ui-control-room-dashboard.css"
    )
    assert "includes/journey_stepper.html" not in TEMPLATE
    assert "includes/lifecycle_rail.html" not in TEMPLATE


def test_dashboard_replaces_card_wall_with_flat_hierarchy():
    assert 'class="metric-grid"' not in TEMPLATE
    assert "app-card" not in TEMPLATE
    assert "metric-card" not in TEMPLATE
    assert "table-card" not in TEMPLATE
    assert "eyebrow" not in TEMPLATE
    assert "cr-page-header" in TEMPLATE
    assert "cr-stat-strip" in TEMPLATE
    assert "dashboard-worklist" in TEMPLATE

    order = ("cr-page-header", "cr-stat-strip", "dashboard-worklist")
    positions = [TEMPLATE.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_dashboard_prioritizes_immediate_steering_metrics_in_status_strip():
    stat_strip = TEMPLATE.split('<dl class="cr-stat-strip dashboard-stat-strip"', 1)[1].split(
        "</dl>", 1
    )[0]
    order = (
        "Überfällig",
        "Blockiert",
        "Aktive Vorhaben",
        "Nutzen gemessen",
        "Ziel erreicht",
    )
    positions = [stat_strip.index(label) for label in order]
    assert positions == sorted(positions)


def test_dashboard_preserves_metrics_actions_and_worklist_sources():
    for value in (
        "active_total",
        "blocked_total",
        "overdue_total",
        "measured_total",
        "achieved_total",
    ):
        assert value in TEMPLATE

    assert "{% worklist_rows next_steps as task_rows %}" in TEMPLATE
    assert "{% for row in task_rows %}" in TEMPLATE
    assert "{% for item in decision_queue %}" in TEMPLATE
    assert "{{ row.action_url }}" in TEMPLATE
    assert "{{ row.use_case.get_absolute_url }}" in TEMPLATE
    assert "{{ item.get_absolute_url }}" in TEMPLATE
    assert "{{ item.blocker_details.0.target_href }}" in TEMPLATE
    assert "{% url 'use_cases:list' %}" in TEMPLATE
    assert "{% url 'reviews:monthly' %}" in TEMPLATE
    assert "nav_is_coordinator" in TEMPLATE


def test_dashboard_keeps_keyboard_operable_task_and_decision_views():
    assert 'id="tasks-tab"' in TEMPLATE
    assert 'data-bs-target="#tasks-pane"' in TEMPLATE
    assert 'aria-controls="tasks-pane"' in TEMPLATE
    assert 'aria-selected="true"' in TEMPLATE
    assert 'id="decisions-tab"' in TEMPLATE
    assert 'data-bs-target="#decisions-pane"' in TEMPLATE
    assert 'aria-controls="decisions-pane"' in TEMPLATE
    assert 'aria-selected="false"' in TEMPLATE
    assert 'tabindex="0"' in TEMPLATE
    assert '<th scope="col">' in TEMPLATE


def test_dashboard_css_is_page_scoped_and_uses_semantic_tokens():
    assert ".ui-control-room.page-dashboard" in CSS
    assert "#" not in CSS
    assert "rgb(" not in CSS
    assert "hsl(" not in CSS
    assert "var(--line-soft)" in CSS
    assert "var(--muted)" in CSS
    assert "var(--ice)" in CSS
    assert "var(--warning)" in CSS
    assert "var(--danger)" in CSS
    assert "overflow-x" not in CSS


def test_dashboard_status_strip_and_switch_are_responsive_without_page_scroll():
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in CSS
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in CSS
    assert "grid-template-columns: 1fr" in CSS
    assert ".dashboard-stat-strip .cr-stat:nth-child(3)" in CSS
    assert "@media (max-width: 1180px)" in CSS
    assert "@media (max-width: 760px)" in CSS
    assert ".dashboard-view-switch__button:focus-visible" in CSS
