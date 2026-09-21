from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "reporting" / "portfolio.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "ui-control-room-portfolio.css").read_text(encoding="utf-8")
SHARED_CSS = (ROOT / "static" / "css" / "ui-control-room-primitives.css").read_text(
    encoding="utf-8"
)


def test_portfolio_opts_into_control_room_without_changing_global_shell():
    assert "{% block body_class %}page-portfolio{% endblock %}" in TEMPLATE
    assert "ui-control-room-primitives.css" in TEMPLATE
    assert "ui-control-room-portfolio.css" in TEMPLATE
    assert ".ui-control-room.page-portfolio .app-topbar" in CSS
    assert "display: none" in CSS


def test_portfolio_uses_compact_status_strip_instead_of_metric_cards():
    assert 'class="cr-stat-strip"' in TEMPLATE
    assert 'class="cr-stat"' in TEMPLATE
    assert "metric-card" not in TEMPLATE
    assert "cr-page-header__summary" in TEMPLATE
    assert "in der Matrix" in TEMPLATE
    assert "mit Klärungsbedarf" in TEMPLATE


def test_portfolio_keeps_decision_matrix_as_primary_surface():
    assert 'class="portfolio-decision-surface"' in TEMPLATE
    assert 'id="portfolio-matrix-title"' in TEMPLATE
    assert 'role="table"' in TEMPLATE
    assert 'class="portfolio-secondary-view"' in TEMPLATE
    assert "Tabellarische Matrix-Alternative" in TEMPLATE


def test_portfolio_domain_name_precedes_secondary_count():
    label_position = TEMPLATE.index("{{ group.label }}")
    count_position = TEMPLATE.index("{{ group.total }} Use Cases")

    assert label_position < count_position
    assert "portfolio-domain-count" in TEMPLATE


def test_portfolio_styles_are_scoped_and_responsive_after_primitive_extraction():
    assert CSS.count(".ui-control-room.page-portfolio") >= 20
    assert ".ui-control-room .cr-" in SHARED_CSS
    assert "@media (max-width: 1300px)" in SHARED_CSS
    assert "@media (max-width: 760px)" in CSS
    assert "@media (max-width: 520px)" in CSS
    assert "overflow: auto" in CSS
    assert ".portfolio-unclassified-row > div" in CSS
    assert "width: 100%" in CSS
