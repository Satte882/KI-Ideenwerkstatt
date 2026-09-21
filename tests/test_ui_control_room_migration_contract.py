from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
PORTFOLIO = (ROOT / "templates" / "reporting" / "portfolio.html").read_text(encoding="utf-8")
USE_CASE_DETAIL = (ROOT / "templates" / "use_cases" / "detail.html").read_text(encoding="utf-8")
MIGRATION = (ROOT / "docs" / "UI_CONTROL_ROOM_MIGRATION.md").read_text(encoding="utf-8")


def test_control_room_is_the_normal_application_shell():
    assert '<body class="ui-vnext ui-control-room {% block body_class %}{% endblock %}">' in BASE
    assert "{% block body_class %}page-portfolio{% endblock %}" in PORTFOLIO
    use_case_class = "{% block body_class %}page-use-case{% endblock %}"
    assert use_case_class in USE_CASE_DETAIL


def test_migration_contract_records_the_completed_normalization():
    assert "`body_class`" in MIGRATION
    assert "Control Room ist der Normalzustand" in MIGRATION
    assert "unter `.ui-control-room` gescoped" in MIGRATION
    assert "keine Runtime-Feature-Flags" in MIGRATION
    assert "temporäre Koexistenz ist beendet" in MIGRATION


def test_migration_contract_contains_reference_pages_and_acceptance_gates():
    assert "`templates/reporting/portfolio.html`" in MIGRATION
    assert "`templates/use_cases/detail.html`" in MIGRATION
    assert "Gate A" in MIGRATION
    assert "Gate B" in MIGRATION
    assert "Final Gate" in MIGRATION
    assert "Kein Merge auf `main` vor expliziter Freigabe" in MIGRATION


def test_migration_contract_records_ci_batch_fix_rule():
    assert "komplette Lauf abgewartet" in MIGRATION
    assert "alle fehlgeschlagenen Jobs und deren Logs vollständig geprüft" in MIGRATION
    assert "Sammel-Fix-Commit" in MIGRATION
    assert "Folge-Jobs blockiert" in MIGRATION
