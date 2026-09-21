from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


BASE = _read("templates", "base.html")
LOGIN = _read("templates", "accounts", "login.html")
SETTINGS = _read("config", "settings", "base.py")
TOKENS = _read("static", "css", "ui-vnext-tokens.css")
LISTS = _read("static", "css", "ui-control-room-lists.css")
WORKSPACES = _read("static", "css", "ui-control-room-workspaces.css")
DASHBOARD = _read("templates", "reporting", "dashboard.html")
USE_CASE_LIST = _read("templates", "use_cases", "list.html")
MONTHLY_REVIEW = _read("templates", "reviews", "monthly.html")


def test_control_room_is_the_single_normal_application_state():
    assert 'class="ui-vnext ui-control-room {% block body_class %}' in BASE
    assert "{% block body_class %}page-login{% endblock %}" in LOGIN
    assert not ROOT.joinpath("templates", "includes", "journey_stepper.html").exists()
    for path in ROOT.joinpath("templates").rglob("*.html"):
        assert "{% block body_class %}ui-control-room" not in path.read_text(encoding="utf-8")


def test_sidebar_starts_with_steering_then_follows_the_workflow():
    primary_labels = (
        "Steuerung",
        "Arbeitsvorrat",
        "Portfolio",
        "Monatsreview",
        "Vorhaben",
        "Analyse",
        "Use Cases",
    )
    positions = [BASE.index(label) for label in primary_labels]
    assert positions == sorted(positions)
    delivery_position = BASE.index("href=\"{% url 'delivery:package_list' %}\"")
    workspace_separator_position = BASE.index("sidebar-workspace-separator")
    outcome_position = BASE.index("reporting:outcome_workspace", workspace_separator_position)
    assert positions[-1] < delivery_position < workspace_separator_position < outcome_position
    assert "href=\"{% url 'reporting:dashboard' %}\"" in BASE
    assert 'LOGIN_REDIRECT_URL = "reporting:dashboard"' in SETTINGS


def test_lifecycle_template_library_has_one_authoritative_registration():
    libraries = list(ROOT.joinpath("ki_radar").rglob("workflow_tags.py"))
    assert libraries == [ROOT / "ki_radar" / "core" / "templatetags" / "workflow_tags.py"]


def test_removed_legacy_stepper_has_no_template_or_css_consumers():
    for path in (
        *ROOT.joinpath("templates").rglob("*.html"),
        *ROOT.joinpath("static", "css").rglob("*.css"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "journey_stepper" not in source, path
        assert "journey-stepper" not in source, path
        assert "journey-step" not in source, path


def test_shared_accessibility_contract_is_present():
    assert ":focus-visible" in TOKENS
    assert "@media (prefers-reduced-motion: reduce)" in TOKENS
    assert "min-height: 42px" in WORKSPACES
    assert ":focus-visible" in WORKSPACES
    assert "overflow: auto" in LISTS


def test_primary_worklists_use_semantic_tables_and_times():
    for template in (DASHBOARD, USE_CASE_LIST):
        assert '<th scope="col">' in template
        assert "<time datetime=" in template
    assert "<time datetime=" in MONTHLY_REVIEW
    assert "state_label" in DASHBOARD
