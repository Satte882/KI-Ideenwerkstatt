from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


PORTFOLIO = read_repo_text("templates", "reporting", "portfolio.html")
PORTFOLIO_CSS = read_repo_text("static", "css", "ui-control-room-portfolio.css")
TOKENS = read_repo_text("static", "css", "ui-vnext-tokens.css")
DESIGN = read_repo_text("DESIGN.md")


def test_portfolio_prioritizes_decision_work_before_secondary_analysis():
    order = (
        "cr-filter-deck",
        "cr-stat-strip",
        "portfolio-decision-section",
        "portfolio-unclassified-section",
        "portfolio-domain-section",
        "portfolio-landscape-section",
    )
    positions = [PORTFOLIO.index(marker) for marker in order]

    assert positions == sorted(positions)
    assert "Klärungsbedarf · {{ unclassified_total }}" in PORTFOLIO
    assert "Nicht einordenbare Use Cases" in PORTFOLIO


def test_portfolio_header_does_not_repeat_status_strip_totals():
    header = PORTFOLIO.split('<header class="cr-page-header">', 1)[1].split("</header>", 1)[0]

    assert "visible_total" not in header
    assert "classified_total" not in header
    assert "unclassified_total" not in header
    assert "in der Matrix" in header
    assert "mit Klärungsbedarf" in header


def test_secondary_portfolio_analysis_uses_native_disclosures():
    assert PORTFOLIO.count('<details class="portfolio-secondary-view') == 2
    assert "Tabellarische Matrix-Alternative" in PORTFOLIO
    assert "Portfolio-Landkarte nach {{ landscape_group_label }}" in PORTFOLIO
    assert 'data-bs-toggle="collapse"' not in PORTFOLIO
    assert 'data-bs-target="' not in PORTFOLIO

    domain_section = PORTFOLIO.index("portfolio-domain-section")
    landscape_details = PORTFOLIO.index("Portfolio-Landkarte nach {{ landscape_group_label }}")
    clarification = PORTFOLIO.index("portfolio-unclassified-section")

    assert clarification < domain_section < landscape_details


def test_compact_domain_orientation_remains_visible_and_explains_its_scope():
    assert '<section class="cr-section portfolio-domain-section"' in PORTFOLIO
    assert "Fachdomänen im Gesamtbestand" in PORTFOLIO
    assert "unabhängig von den Portfoliofiltern" in PORTFOLIO
    domain_section = PORTFOLIO.split('<section class="cr-section portfolio-domain-section"', 1)[
        1
    ].split("</section>", 1)[0]
    assert "<details" not in domain_section


def test_landscape_reopens_after_grouping_navigation():
    assert (
        '<details class="portfolio-secondary-view portfolio-secondary-analysis"'
        "{% if landscape_expanded %} open{% endif %}>"
    ) in PORTFOLIO


def test_matrix_status_and_confidence_are_not_communicated_by_color_alone():
    chip = (
        "{{ item.classification.get_business_domain_display }} · "
        "{{ item.get_decision_status_display }} · Confidence "
        "{{ item.portfolio_confidence_label }}"
    )

    assert chip in PORTFOLIO
    assert "Confidence hoch" in PORTFOLIO
    assert "Confidence mittel" in PORTFOLIO
    assert "Confidence niedrig" in PORTFOLIO
    assert 'aria-label="Entscheidungsstatus-Legende"' in PORTFOLIO
    assert "Status immer zusätzlich durch Text vermitteln" in DESIGN


def test_clarification_items_remain_directly_actionable():
    assert 'class="portfolio-unclassified-row"' in PORTFOLIO
    assert 'href="{{ entry.item.get_absolute_url }}"' in PORTFOLIO
    assert "{{ entry.reason }}" in PORTFOLIO
    assert "Alle sichtbaren Use Cases sind in der Matrix einordenbar." in PORTFOLIO


def test_portfolio_responsive_and_accessibility_contracts_remain_intact():
    assert 'class="portfolio-matrix-scroll overflow-auto pb-2"' in PORTFOLIO
    assert "@media (max-width: 760px)" in PORTFOLIO_CSS
    assert "@media (max-width: 520px)" in PORTFOLIO_CSS
    assert ".portfolio-unclassified-row" in PORTFOLIO_CSS
    assert "overflow-x" not in PORTFOLIO_CSS
    assert ":focus-visible" in TOKENS
    assert "@media (prefers-reduced-motion: reduce)" in TOKENS
    assert "Mobile stapelt Bedienelemente" in DESIGN
