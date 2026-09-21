from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


TEMPLATE = read_repo_text("templates", "use_cases", "detail.html")
DECISION_STATE = read_repo_text("templates", "includes", "decision_state.html")
LIFECYCLE_RAIL = read_repo_text("templates", "includes", "lifecycle_rail.html")
CONTEXT_TOPBAR = read_repo_text("templates", "includes", "context_topbar.html")
CSS = read_repo_text("static", "css", "ui-control-room-use-case.css")
PRIMITIVES = read_repo_text("static", "css", "ui-control-room-primitives.css")
TOPBAR_CSS = read_repo_text("static", "css", "context-topbar.css")
README = read_repo_text("README.md")


def test_use_case_detail_composes_shared_work_object_patterns():
    assert "{% block body_class %}page-use-case{% endblock %}" in TEMPLATE
    assert "includes/decision_state.html" in TEMPLATE
    assert "includes/lifecycle_rail.html" in TEMPLATE
    assert "includes/next_action.html" not in TEMPLATE
    assert "includes/journey_stepper.html" not in TEMPLATE

    shared = "css/ui-control-room-primitives.css"
    page = "css/ui-control-room-use-case.css"
    assert shared in TEMPLATE
    assert page in TEMPLATE
    assert TEMPLATE.index(shared) < TEMPLATE.index(page)
    assert ".ui-control-room.page-use-case" in CSS


def test_decision_workspace_hierarchy_places_lifecycle_and_decisions_before_secondary_information():
    parent_order = (
        "includes/lifecycle_rail.html",
        "use-case-overview",
        "includes/decision_state.html",
        'id="assessment"',
        "metric-title",
        "business-context-title",
        'id="review-copilot"',
        'id="decision-history"',
    )
    positions = [TEMPLATE.index(marker) for marker in parent_order]
    assert positions == sorted(positions)

    decision_order = ("decision-state", "decision-readiness", "next-action")
    positions = [DECISION_STATE.index(marker) for marker in decision_order]
    assert positions == sorted(positions)


def test_all_existing_use_case_actions_remain_reachable_with_existing_permissions():
    rendered_sources = TEMPLATE + DECISION_STATE
    routes = (
        "use_cases:edit",
        "reviews:create",
        "use_cases:assessment_create",
        "use_cases:approval_decision_create",
        "use_cases:second_approval_review",
        "governance:create",
        "notifications:evidence_create",
        "use_cases:copilot",
    )
    for route in routes:
        assert route in rendered_sources

    assert "can_edit" in TEMPLATE
    assert "nav_is_coordinator" in TEMPLATE
    assert "journey.next_action.key != 'pilot_start'" in TEMPLATE
    assert "journey.next_action.key != 'assessment'" in TEMPLATE
    assert "journey.next_action.key != 'approval'" in rendered_sources
    assert "journey.next_action.key != 'governance'" in TEMPLATE
    assert "Lifecycle-Review" not in TEMPLATE
    assert "Entscheidung dokumentieren" in TEMPLATE
    assert "Stammdaten bearbeiten" not in TEMPLATE


def test_section_actions_own_edit_paths_without_reintroducing_readiness_hard_stops():
    page_header_start = TEMPLATE.index('id="use-case-overview"')
    page_header_end = TEMPLATE.index("</header>", page_header_start)
    page_header = TEMPLATE[page_header_start:page_header_end]
    assert "reviews:create" in page_header
    assert "use_cases:edit" not in page_header
    assert "use_cases:assessment_create" not in page_header
    assert "use_cases:approval_decision_create" not in page_header

    assessment_start = TEMPLATE.index('id="assessment"')
    assessment_end = TEMPLATE.index("</section>", assessment_start)
    assessment = TEMPLATE[assessment_start:assessment_end]
    assert 'data-testid="assessment-edit-action"' in assessment
    assert 'data-testid="approval-decision-action"' in assessment
    assert 'data-testid="assessment-negative-decision-action"' in assessment
    assert "use_case.status == 'review'" in assessment
    assert "blocker_details" not in assessment
    assert "decision_check.blockers" not in assessment

    metric_start = TEMPLATE.index('id="metric-title"')
    metric_end = TEMPLATE.index("</section>", metric_start)
    metric = TEMPLATE[metric_start:metric_end]
    assert 'data-testid="metric-edit-action"' in metric
    assert "#field-metric_name" in metric

    context_start = TEMPLATE.index('id="business-context-title"')
    context_end = TEMPLATE.index("</section>", context_start)
    context = TEMPLATE[context_start:context_end]
    assert 'data-testid="business-context-edit-action"' in context
    assert "#field-problem_statement" in context


def test_next_action_is_owned_once_by_decision_state_on_migrated_work_object():
    assert DECISION_STATE.count("includes/next_action.html") == 1
    assert 'id="next-action"' in DECISION_STATE
    assert "includes/next_action.html" not in TEMPLATE

    use_case_guard = "request.resolver_match.namespace == 'use_cases'"
    detail_guard = "request.resolver_match.url_name == 'detail'"
    assert use_case_guard in CONTEXT_TOPBAR
    assert detail_guard in CONTEXT_TOPBAR
    assert CONTEXT_TOPBAR.index(use_case_guard) < CONTEXT_TOPBAR.index(
        "{% workflow_steps journey request as workflow %}"
    )


def test_global_lifecycle_requires_real_work_context_instead_of_list_fallbacks():
    work_context_guard = "{% elif journey %}"
    assert work_context_guard in CONTEXT_TOPBAR
    assert "Wirkung & Betrieb owns its subordinate outcome lifecycle locally" in CONTEXT_TOPBAR
    assert "url_name == 'portfolio'" not in CONTEXT_TOPBAR
    assert "Von der Discovery bis zur umsetzbaren Übergabe" not in CONTEXT_TOPBAR
    assert CONTEXT_TOPBAR.index(work_context_guard) < CONTEXT_TOPBAR.index(
        "{% workflow_steps journey request as workflow %}"
    )


def test_lifecycle_navigation_is_scroll_free_on_desktop_and_compact_on_mobile():
    assert "{% workflow_steps journey request as workflow %}" in LIFECYCLE_RAIL
    assert 'href="{{ step.local_url }}"' in LIFECYCLE_RAIL
    assert "cr-lifecycle-step--static" in LIFECYCLE_RAIL
    assert 'aria-current="page"' in LIFECYCLE_RAIL
    assert 'aria-current="step"' in LIFECYCLE_RAIL
    assert "cr-lifecycle-step--{{ step.state }}" in LIFECYCLE_RAIL
    assert ".ui-control-room .cr-lifecycle-rail__steps" in PRIMITIVES
    assert "overflow-x: auto" not in PRIMITIVES
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in PRIMITIVES
    assert "grid-template-columns: 1fr" in PRIMITIVES

    assert ".journey-progress" in TOPBAR_CSS
    assert "overflow-x: auto" not in TOPBAR_CSS
    assert "flex-wrap: wrap" in TOPBAR_CSS
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in TOPBAR_CSS
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in TOPBAR_CSS


def test_blocker_links_and_second_approval_remain_true_links():
    assert "{{ first_blocker.target_href }}" in DECISION_STATE
    assert "{{ blocker.target_href }}" in DECISION_STATE
    assert "use_cases:second_approval_review" in DECISION_STATE
    readiness = DECISION_STATE.index('id="decision-readiness"')
    next_action = DECISION_STATE.index('id="next-action"')
    assert "disabled" not in DECISION_STATE[readiness:next_action]


def test_gate_b_work_object_patterns_are_shared_primitives():
    assert "cr-decision-state" in DECISION_STATE
    assert "cr-decision-readiness" in DECISION_STATE
    assert "cr-next-action" in DECISION_STATE
    assert "cr-lifecycle-rail" in LIFECYCLE_RAIL
    assert ".ui-control-room .cr-decision-state" in PRIMITIVES
    assert ".ui-control-room .cr-decision-readiness" in PRIMITIVES
    assert ".ui-control-room .cr-next-action" in PRIMITIVES
    assert ".ui-control-room .cr-lifecycle-rail" in PRIMITIVES


def test_control_room_css_uses_semantic_tokens_without_new_raw_colors():
    for stylesheet in (CSS, PRIMITIVES):
        assert "#" not in stylesheet
        assert "rgb(" not in stylesheet
        assert "hsl(" not in stylesheet
        assert "var(--line-soft)" in stylesheet
        assert "var(--muted)" in stylesheet

    assert "var(--ice)" in PRIMITIVES
    assert "var(--warning)" in PRIMITIVES
    assert "var(--danger)" in PRIMITIVES


def test_readme_describes_contextual_lifecycle_instead_of_permanent_journey():
    assert "kontextbezogen" in README
    assert "Querschnitts- und Listensichten" in README
    assert "dauerhaft sichtbar" not in README


def test_issue_410_keeps_active_work_visible_and_secondary_detail_collapsible():
    assert 'id="upcoming-gate-readiness"' in DECISION_STATE
    assert 'data-testid="governance-status-summary"' in TEMPLATE
    assert 'id="governance-evidence-details"' in TEMPLATE
    assert 'id="assessment-evidence"' in TEMPLATE
    assert 'id="metric-evidence"' in TEMPLATE
