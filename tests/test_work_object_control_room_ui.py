from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _template(*parts):
    return ROOT.joinpath("templates", *parts).read_text(encoding="utf-8")


WORK_OBJECTS = {
    "process": _template("architecture", "process_analysis_detail.html"),
    "delivery": _template("delivery", "package_detail.html"),
    "governance": _template("governance", "form.html"),
    "governance_review": _template("governance", "review_form.html"),
    "assessment": _template("use_cases", "assessment_form.html"),
    "decision": _template("use_cases", "decision_form.html"),
}
REMAINING_DETAILS = (
    ("architecture", "solution_option_compare.html"),
    ("accelerator", "analysis_detail.html"),
    ("accelerator", "capture_review.html"),
    ("accelerator", "solution_generation_preview.html"),
    ("accelerator", "structured_review.html"),
    ("use_cases", "second_approval_review.html"),
    ("delivery", "methodology_reference.html"),
)
REMAINING_FORMS = (
    ("use_cases", "form.html"),
    ("use_cases", "intake_wizard.html"),
    ("architecture", "process_analysis_form.html"),
    ("architecture", "process_validation_form.html"),
    ("architecture", "solution_option_form.html"),
    ("architecture", "stage_focus_form.html"),
    ("architecture", "stage_form.html"),
    ("architecture", "value_stream_form.html"),
    ("delivery", "package_form.html"),
    ("reviews", "form.html"),
    ("notifications", "evidence_form.html"),
    ("accelerator", "capture_start.html"),
    ("accelerator", "capture_wizard.html"),
)
TOPBAR = _template("includes", "context_topbar.html")
NEXT_ACTION = _template("includes", "next_action.html")
CSS = ROOT.joinpath("static", "css", "ui-control-room-workspaces.css").read_text(encoding="utf-8")


def test_migrated_work_objects_share_one_local_lifecycle_owner():
    for name, template in WORK_OBJECTS.items():
        assert "{% block body_class %}page-" in template, name
        assert "css/ui-control-room-primitives.css" in template, name
        assert "css/ui-control-room-workspaces.css" in template, name
        assert template.count("includes/lifecycle_rail.html") == 1, name
        assert "includes/journey_stepper.html" not in template, name
        assert template.index("includes/lifecycle_rail.html") < template.index(
            'class="cr-page-header'
        ), name


def test_detail_workspaces_render_one_canonical_next_action():
    for name in ("process", "delivery"):
        assert WORK_OBJECTS[name].count("includes/next_action.html") == 1
        assert 'id="next-action"' in WORK_OBJECTS[name]

    assert 'data-testid="primary-next-action-control"' not in WORK_OBJECTS["process"]
    assert "process_analysis_detail" in NEXT_ACTION
    assert "package_detail" in NEXT_ACTION


def test_forms_keep_post_validation_and_primary_submit_controls():
    for name in ("governance", "governance_review", "assessment", "decision"):
        template = WORK_OBJECTS[name]
        assert 'method="post"' in template, name
        assert "{% csrf_token %}" in template, name
        assert "cr-work-form" in template, name
        assert 'class="btn btn-primary"' in template, name


def test_context_topbar_yields_to_all_migrated_local_owners():
    for route_name in (
        "process_analysis_detail",
        "package_detail",
        "assessment_create",
        "approval_decision_create",
    ):
        assert route_name in TOPBAR
    assert "Migrated Governance forms own LifecycleRail locally" in TOPBAR


def test_delivery_semantic_subworkflow_remains_intact():
    delivery = WORK_OBJECTS["delivery"]
    assert "delivery-section-card" in delivery
    assert "row.review" in delivery
    assert "package_section_review" in delivery


def test_workspace_css_is_scoped_responsive_and_accessible():
    assert CSS.count(".ui-control-room") >= 10
    assert "@media (max-width: 900px)" in CSS
    assert "@media (max-width: 520px)" in CSS
    assert "min-height: 42px" in CSS
    assert ":focus-visible" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "overflow-x" not in CSS


def test_remaining_detail_workspaces_use_shared_control_room_primitives():
    for parts in REMAINING_DETAILS:
        template = _template(*parts)
        assert "{% block body_class %}page-detail-workspace" in template, parts
        assert "css/ui-control-room-primitives.css" in template, parts
        assert "css/ui-control-room-workspaces.css" in template, parts


def test_remaining_forms_and_true_wizards_use_shared_control_room_primitives():
    for parts in REMAINING_FORMS:
        template = _template(*parts)
        assert "{% block body_class %}page-form-workspace" in template, parts
        assert "css/ui-control-room-primitives.css" in template, parts
        assert "css/ui-control-room-workspaces.css" in template, parts
        assert 'method="post"' in template, parts
        assert "{% csrf_token %}" in template, parts

    for wizard in (
        _template("use_cases", "intake_wizard.html"),
        _template("accelerator", "capture_wizard.html"),
    ):
        assert "wizard-stepper" in wizard
        assert 'role="progressbar"' in wizard
