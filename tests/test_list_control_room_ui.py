from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


TEMPLATES = {
    "use_cases": read_repo_text("templates", "use_cases", "list.html"),
    "value_streams": read_repo_text("templates", "architecture", "value_stream_list.html"),
    "delivery": read_repo_text("templates", "delivery", "package_list.html"),
    "captures": read_repo_text("templates", "accelerator", "capture_list.html"),
    "monthly": read_repo_text("templates", "reviews", "monthly.html"),
}
SECTION = read_repo_text("templates", "reviews", "section.html")
CSS = read_repo_text("static", "css", "ui-control-room-lists.css")
MIGRATION = read_repo_text("docs", "UI_CONTROL_ROOM_MIGRATION.md")


def test_all_ap6_list_pages_opt_into_shared_control_room_patterns():
    expected_pages = {
        "use_cases": "page-use-case-list",
        "value_streams": "page-value-stream-list",
        "delivery": "page-delivery-list",
        "captures": "page-capture-list",
        "monthly": "page-monthly-review",
    }

    for name, page_class in expected_pages.items():
        template = TEMPLATES[name]
        assert f"{{% block body_class %}}{page_class}{{% endblock %}}" in template
        assert "css/ui-control-room-primitives.css" in template
        assert "css/ui-control-room-lists.css" in template
        assert "cr-page-header" in template


def test_table_lists_keep_real_links_headers_and_explicit_empty_states():
    for name in ("use_cases", "delivery", "captures"):
        template = TEMPLATES[name]
        assert "cr-list-table" in template
        assert "<thead" in template
        assert "<th" in template
        assert "href=" in template
        assert "cr-empty-state" in template


def test_use_case_filters_adopt_shared_filter_contract_without_query_changes():
    template = TEMPLATES["use_cases"]
    for name in ("q", "business_domain", "status", "review_state", "business_value"):
        assert f'name="{name}"' in template
    assert "cr-filter-deck" in template
    assert "cr-filter-grid" in template
    assert "cr-filter-reset" in template


def test_value_streams_use_scan_friendly_link_grid_and_monthly_review_is_not_card_wall():
    assert "cr-list-card-grid" in TEMPLATES["value_streams"]
    assert 'class="cr-list-card architecture-card"' in TEMPLATES["value_streams"]
    assert "cr-review-grid" in TEMPLATES["monthly"]
    assert "cr-review-section" in SECTION
    assert 'class="card' not in SECTION
    assert "list-group" not in SECTION


def test_list_styles_are_scoped_responsive_and_accessible():
    assert ".ui-control-room .cr-list" in CSS
    assert "position: sticky" in CSS
    assert ":focus-visible" in CSS
    assert "@media (max-width: 760px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "overflow: auto" in CSS
    assert "var(--line-soft)" in CSS
    assert "#" not in CSS
    assert "rgb(" not in CSS
    assert "hsl(" not in CSS


def test_migration_contract_records_completed_ap6_list_rollout():
    assert "## AP6" in MIGRATION
    assert "migrierte Querschnitts- und Listenseiten" in MIGRATION
    assert "Use-Case-Liste" in MIGRATION
    assert "Value-Stream-Liste" in MIGRATION
    assert "Delivery-Liste" in MIGRATION
    assert "Monatsreview" in MIGRATION
    assert "keine Query-Parameter" in MIGRATION
