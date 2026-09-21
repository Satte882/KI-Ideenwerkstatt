from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


PORTFOLIO = read_repo_text("templates", "reporting", "portfolio.html")
PORTFOLIO_CSS = read_repo_text("static", "css", "ui-control-room-portfolio.css")
PRIMITIVES = read_repo_text("static", "css", "ui-control-room-primitives.css")
DASHBOARD = read_repo_text("templates", "reporting", "dashboard.html")
OUTCOME = read_repo_text("templates", "reporting", "outcome_workspace.html")
USE_CASE_LIST = read_repo_text("templates", "use_cases", "list.html")
CONTRACT = read_repo_text("docs", "UI_CONTROL_ROOM_PRIMITIVES.md")


def test_portfolio_loads_shared_primitives_before_page_styles():
    shared = "css/ui-control-room-primitives.css"
    page = "css/ui-control-room-portfolio.css"

    assert shared in PORTFOLIO
    assert page in PORTFOLIO
    assert PORTFOLIO.index(shared) < PORTFOLIO.index(page)


def test_gate_a_patterns_are_consumed_as_shared_primitives():
    expected = (
        "cr-page-header",
        "cr-section-heading",
        "cr-stat-strip",
        "cr-filter-grid",
        "cr-inline-note",
        "cr-empty-state",
    )

    for class_name in expected:
        assert class_name in PORTFOLIO
        assert f".{class_name}" in PRIMITIVES


def test_extracted_rules_are_not_duplicated_in_portfolio_stylesheet():
    old_page_scoped_names = (
        ".portfolio-command-header",
        ".portfolio-filter-grid",
        ".portfolio-stat-strip",
        ".portfolio-section-heading",
        ".portfolio-inline-note",
        ".portfolio-empty-copy",
    )

    for selector in old_page_scoped_names:
        assert selector not in PORTFOLIO_CSS


def test_shared_primitives_are_scoped_and_use_semantic_color_tokens():
    assert ".ui-control-room .cr-" in PRIMITIVES
    assert "#" not in PRIMITIVES
    assert "rgb(" not in PRIMITIVES
    assert "hsl(" not in PRIMITIVES
    assert "var(--line-soft)" in PRIMITIVES
    assert "var(--ink)" in PRIMITIVES
    assert "var(--muted)" in PRIMITIVES


def test_each_extracted_pattern_has_a_real_second_consumer():
    assert "cr-page-header" in DASHBOARD
    assert "cr-stat-strip" in DASHBOARD
    assert "outcome-page-header" in OUTCOME
    assert "outcome-summary-grid" in OUTCOME
    assert "cr-filter-deck" in USE_CASE_LIST
    assert "cr-filter-grid" in USE_CASE_LIST
    assert "cr-empty-state" in USE_CASE_LIST


def test_contract_keeps_primitives_presentational_and_defers_work_objects():
    assert "keine View-Logik" in CONTRACT
    assert "keine fachlichen Entscheidungen" in CONTRACT
    assert "keine neuen Template-Partials" in CONTRACT
    assert "Die zweiten Verbraucher" in CONTRACT
    assert "Adoption erfolgt" in CONTRACT
    assert "LifecycleRail" in CONTRACT
    assert "DecisionState" in CONTRACT
    assert "nicht generalisiert" in CONTRACT
