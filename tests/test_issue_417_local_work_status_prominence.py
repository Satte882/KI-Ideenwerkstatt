from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


TEMPLATE = read_repo_text("templates", "includes", "local_work_status.html")
PRIMITIVES = read_repo_text("static", "css", "ui-control-room-primitives.css")
DISCLOSURE_NAVIGATION = read_repo_text("static", "js", "disclosure-navigation.js")
NEXT_ACTION = read_repo_text("templates", "includes", "next_action.html")
WORKSPACE_TEMPLATES = (
    read_repo_text("templates", "use_cases", "detail.html"),
    read_repo_text("templates", "delivery", "package_detail.html"),
    read_repo_text("templates", "architecture", "process_analysis_detail.html"),
    read_repo_text("templates", "reporting", "outcome_workspace.html"),
)


def test_issue_417_uses_one_prominent_pattern_across_all_four_workspaces():
    assert TEMPLATE.count('class="cr-local-work-status"') == 4
    assert TEMPLATE.count('class="cr-local-work-status__header"') == 4
    assert TEMPLATE.count('class="cr-local-work-status__items"') == 4
    assert TEMPLATE.count('data-testid="local-work-status"') == 4
    assert TEMPLATE.count("Auf dieser Seite ·") == 4
    assert "Bewertung, Governance, Freigabe und Metrik" in TEMPLATE
    assert "Readiness-Sektionen dieses Delivery Packages" in TEMPLATE
    assert "Prozessanalyse, Validierung, Arbeitsgestaltung und Lösungsoptionen" in TEMPLATE
    assert "Wirkungsmessung, Delivery und Scale Review" in TEMPLATE


def test_issue_417_preserves_status_text_and_existing_navigation_targets():
    for state_label in ("Erledigt", "Offen", "Blockiert", "Optional"):
        assert state_label in TEMPLATE

    for target in (
        "assessment",
        "governance-evidence",
        "decision-history",
        "metric-title",
        "process-validation",
        "prozessanalyse",
        "arbeitsgestaltung",
        "loesungsoptionen",
        "outcome-measurement",
        "outcome-delivery-context",
        "outcome-scale-review",
    ):
        assert target in TEMPLATE


def test_issue_417_uses_shared_tokens_and_keeps_active_location_visible():
    assert ".ui-control-room .cr-local-work-status" in PRIMITIVES
    assert ".ui-control-room .cr-local-work-status__items" in PRIMITIVES
    assert 'aria-current="location"' in PRIMITIVES
    assert "var(--surface-2)" in PRIMITIVES
    assert "var(--ice)" in PRIMITIVES
    assert "var(--success)" in PRIMITIVES
    assert "var(--warning)" in PRIMITIVES
    assert "var(--danger)" in PRIMITIVES
    assert "var(--touch-target-min)" in PRIMITIVES
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in PRIMITIVES
    assert "grid-template-columns: 1fr;" in PRIMITIVES


def test_issue_417_places_local_navigation_directly_after_global_lifecycle():
    assert "includes/local_work_status.html" not in NEXT_ACTION
    for workspace in WORKSPACE_TEMPLATES:
        lifecycle = workspace.index("includes/lifecycle_rail.html")
        local_status = workspace.index("includes/local_work_status.html")
        assert lifecycle < local_status


def test_issue_417_tracks_active_target_in_document_order():
    assert "targets.sort" in DISCLOSURE_NAVIGATION
    assert "compareDocumentPosition" in DISCLOSURE_NAVIGATION
