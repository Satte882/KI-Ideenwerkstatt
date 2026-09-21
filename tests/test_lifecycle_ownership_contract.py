from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory

from ki_radar.core.templatetags.workflow_tags import workflow_steps
from ki_radar.use_cases.workflow import JourneyState, JourneyStep

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


DESIGN = read_repo_text("DESIGN.md")
AUDIT = read_repo_text("docs", "UI_LIFECYCLE_OWNERSHIP_AUDIT.md")
VALUE_STREAM = read_repo_text("templates", "architecture", "value_stream_detail.html")
OUTCOME = read_repo_text("templates", "reporting", "outcome_workspace.html")
BASE = read_repo_text("templates", "base.html")
TOPBAR = read_repo_text("templates", "includes", "context_topbar.html")
NEXT_ACTION = read_repo_text("templates", "includes", "next_action.html")
LIFECYCLE = read_repo_text("templates", "includes", "lifecycle_rail.html")
PRIMITIVES = read_repo_text("static", "css", "ui-control-room-primitives.css")
ANALYSIS_NAVIGATION = read_repo_text("static", "css", "analysis-navigation.css")


def test_design_contract_owns_each_journey_once():
    assert (
        "Eine Journey/Datenquelle darf pro Arbeitsobjekt nur eine primäre "
        "Lifecycle-Darstellung besitzen."
    ) in DESIGN
    assert "Ein echter Subworkflow ist nur zulässig" in DESIGN
    assert "Next Action erscheint pro Arbeitsobjekt genau einmal dominant" in DESIGN
    assert "keine horizontale Scrollfläche" in DESIGN


def test_audit_distinguishes_duplicates_from_real_subworkflows():
    for classification in (
        "global-only",
        "local-only",
        "duplicate-same-source",
        "semantic-subworkflow",
    ):
        assert classification in AUDIT

    for duplicate in (
        "architecture/value_stream_detail.html",
        "architecture/process_analysis_detail.html",
        "delivery/package_detail.html",
        "governance/form.html",
        "governance/review_form.html",
        "use_cases/assessment_form.html",
        "use_cases/decision_form.html",
    ):
        assert duplicate in AUDIT

    assert "use_cases/intake_wizard.html" in AUDIT
    assert "accelerator/capture_wizard.html" in AUDIT
    assert "delivery/package_form.html" in AUDIT


def test_value_stream_reference_owns_next_action_and_lifecycle_locally():
    assert "{% block body_class %}page-value-stream{% endblock %}" in VALUE_STREAM
    assert "css/ui-control-room-primitives.css" in VALUE_STREAM
    assert VALUE_STREAM.count("includes/next_action.html") == 1
    assert VALUE_STREAM.count("includes/lifecycle_rail.html") == 1
    assert "includes/journey_stepper.html" not in VALUE_STREAM
    assert 'class="cr-next-action"' in VALUE_STREAM
    assert 'data-testid="primary-next-action-control"' not in VALUE_STREAM
    assert "journey.next_action.action_label" not in VALUE_STREAM
    assert VALUE_STREAM.index("includes/lifecycle_rail.html") < VALUE_STREAM.index(
        'class="page-header"'
    )


def test_value_stream_does_not_repeat_phase_add_as_primary_action():
    assert "can_edit and journey.next_action.key != 'value_stream'" in VALUE_STREAM
    assert "Weitere Phase ergänzen" in VALUE_STREAM
    assert NEXT_ACTION.count('data-testid="primary-next-action-control"') == 2
    assert "architecture" in NEXT_ACTION
    assert "value_stream_detail" in NEXT_ACTION


def test_context_topbar_explicitly_yields_value_stream_ownership():
    assert "request.resolver_match.namespace == 'architecture'" in TOPBAR
    assert "request.resolver_match.url_name == 'value_stream_detail'" in TOPBAR
    assert "owns Next Action and LifecycleRail locally" in TOPBAR

    request = RequestFactory().get("/architecture/value-streams/example/")
    request.user = AnonymousUser()
    request.resolver_match = SimpleNamespace(
        namespace="architecture",
        url_name="value_stream_detail",
    )
    step = JourneyStep(
        key="value_stream",
        label="Value Stream",
        state="current",
        url="/architecture/value-streams/example/",
        action_label="Phase ergänzen",
        reason="Die Phasenstruktur ist noch offen.",
    )
    journey = JourneyState(
        path_label="Value Stream Test",
        steps=(step,),
        next_action=step,
    )

    rendered = render_to_string(
        "includes/context_topbar.html",
        {"journey": journey, "request": request},
        request=request,
    )

    assert "Arbeitsfortschritt" not in rendered
    assert "journey-progress" not in rendered
    assert "journey-next-action-context" not in rendered


def test_outcome_workspace_owns_subordinate_lifecycle_once_and_locally():
    assert "{% block body_class %}page-outcome-workspace{% endblock %}" in OUTCOME
    assert OUTCOME.count("includes/lifecycle_rail.html") == 1
    assert OUTCOME.index("includes/lifecycle_rail.html") < OUTCOME.index('class="page-header')
    assert 'lifecycle_kicker="Teilprozess"' in OUTCOME
    assert OUTCOME.count('data-testid="outcome-primary-action"') == 1
    assert "Wirkung & Betrieb owns its subordinate outcome lifecycle locally" in TOPBAR
    assert BASE.count("reporting:outcome_workspace") == 2
    assert "Pilot → Wirkung → Scale Readiness → Betrieb" in BASE
    assert BASE.count("?stage=decision") == 1
    for duplicate_stage in (
        "?stage=handover",
        "?stage=effect",
        "?stage=operation",
        "?stage=closure",
    ):
        assert duplicate_stage not in BASE


def test_canonical_lifecycle_keeps_true_links_focus_and_responsive_layout():
    assert "workflow_steps journey request as workflow" in LIFECYCLE
    assert 'href="{{ step.local_url }}"' in LIFECYCLE
    assert "{% if step.local_url %}" in LIFECYCLE
    assert "cr-lifecycle-step--static" in LIFECYCLE
    assert 'aria-current="page"' in LIFECYCLE
    assert 'aria-current="step"' in LIFECYCLE
    assert ".cr-lifecycle-step:focus-visible" in PRIMITIVES
    assert "@media (max-width: 760px)" in PRIMITIVES
    assert "@media (max-width: 520px)" in PRIMITIVES
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in PRIMITIVES
    assert "grid-template-columns: 1fr" in PRIMITIVES
    assert "overflow-x" not in PRIMITIVES
    for token in ("var(--success)", "var(--warning)", "var(--danger)", "var(--ice)"):
        assert token in PRIMITIVES


def test_desktop_analysis_depth_has_only_the_sidebar_owner():
    assert "@media (min-width: 1101px)" in ANALYSIS_NAVIGATION
    desktop_rule = ANALYSIS_NAVIGATION.split("@media (min-width: 1101px)", 1)[1]
    assert ".analysis-step-actions" in desktop_rule
    assert "display: none" in desktop_rule


def test_local_value_stream_lifecycle_never_uses_global_fallback_links():
    request = RequestFactory().get("/architecture/value-streams/example/")
    request.resolver_match = SimpleNamespace(
        namespace="architecture",
        url_name="value_stream_detail",
    )
    journey = JourneyState(
        path_label="Value Stream Test",
        steps=(
            JourneyStep(
                key="value_stream",
                label="Discovery",
                state="complete",
                url="/architecture/value-streams/example/",
            ),
            JourneyStep(
                key="focus",
                label="Fokus & Priorisierung",
                state="complete",
                url="/architecture/value-streams/example/",
            ),
            JourneyStep(
                key="process",
                label="Prozessanalyse",
                state="blocked",
                url="/architecture/processes/example/edit/",
                action_label="Prozessanalyse vervollständigen",
            ),
            JourneyStep(key="solution", label="Lösungsoption", state="upcoming"),
            JourneyStep(key="use_case", label="Use Case", state="upcoming"),
            JourneyStep(key="assessment", label="Bewertung", state="upcoming"),
            JourneyStep(key="governance", label="Governance", state="optional"),
            JourneyStep(key="approval", label="Freigabe", state="upcoming"),
            JourneyStep(key="delivery", label="Delivery", state="upcoming"),
        ),
        next_action=None,
    )

    steps = {step["key"]: step for step in workflow_steps(journey, request)}

    assert steps["discovery"]["local_url"] == "/architecture/value-streams/example/"
    assert steps["focus"]["local_url"] == "/architecture/value-streams/example/"
    assert steps["use_cases"]["local_label"] == "Prozessanalyse"
    assert steps["use_cases"]["local_url"] == "/architecture/processes/example/edit/"
    for key in ("assessment", "governance", "approval", "delivery"):
        assert steps[key]["local_url"] == ""


def test_outcome_lifecycle_links_remain_local_workspace_view_switches():
    request = RequestFactory().get("/wirkung-betrieb/?stage=pilot&use_case=example")
    request.resolver_match = SimpleNamespace(
        namespace="reporting",
        url_name="outcome_workspace",
    )

    steps = workflow_steps(None, request)

    assert len(steps) == 6
    assert all(step["local_url"].startswith("/wirkung-betrieb/?") for step in steps)
    assert all("use_case=example" in step["local_url"] for step in steps)
