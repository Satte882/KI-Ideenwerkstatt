from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DETAIL = ROOT.joinpath("templates", "use_cases", "detail.html").read_text(encoding="utf-8")
DECISION_STATE = ROOT.joinpath("templates", "includes", "decision_state.html").read_text(
    encoding="utf-8"
)
NEXT_ACTION = ROOT.joinpath("templates", "includes", "next_action.html").read_text(encoding="utf-8")
FORM = ROOT.joinpath("templates", "use_cases", "form.html").read_text(encoding="utf-8")
GOVERNANCE_JOURNEY = ROOT.joinpath("ki_radar", "use_cases", "governance_journey.py").read_text(
    encoding="utf-8"
)
WORKFLOW = ROOT.joinpath("ki_radar", "use_cases", "workflow.py").read_text(encoding="utf-8")


def test_use_case_has_one_primary_lifecycle_and_no_status_dimension_duplicate():
    assert DETAIL.index("includes/lifecycle_rail.html") < DETAIL.index('id="use-case-overview"')
    assert "<dt>Lifecycle</dt>" not in DECISION_STATE
    assert "<dt>Erfolgsmetrik</dt>" not in DECISION_STATE
    assert "Aktueller Arbeitszustand" not in DETAIL
    assert "request.resolver_match.namespace == 'use_cases'" in NEXT_ACTION
    assert '{% include "includes/status_dimensions.html" %}' in NEXT_ACTION


def test_decision_status_and_origin_remove_audit_d_duplicates():
    assert DECISION_STATE.count("{{ use_case.get_decision_status_display }}") == 1
    assert "<dt>Use Case</dt>" not in DETAIL
    assert DETAIL.count("Nächste Lifecycle-Entscheidung") == 1


def test_assessment_and_metric_prioritize_decision_information():
    recommendation = DETAIL.index('uc-data-label">Empfehlung')
    confidence = DETAIL.index('uc-data-label">Hergeleitete Confidence')
    metadata = DETAIL.index('uc-data-label">Bewertungsdetails')
    assert recommendation < confidence < metadata

    target = DETAIL.index("<small>Ziel</small>")
    actual = DETAIL.index("<small>Ist</small>")
    baseline = DETAIL.index("<small>Baseline</small>")
    assert target < actual < baseline
    assert "Begründung, Evidenz und Metadaten anzeigen" in DETAIL
    assert "Messgrundlage und Nachweis anzeigen" in DETAIL


def test_secondary_information_uses_native_disclosure():
    for summary in (
        "Ursprung & strategischen Kontext anzeigen",
        "Begründungen, Prüfmetadaten und Nachweise anzeigen",
        "OpenRouter Review-Copilot anzeigen",
        "Entscheidungs- und Änderungshistorie anzeigen",
    ):
        assert summary in DETAIL
    assert DETAIL.count("<details") >= 5
    assert 'data-bs-toggle="collapse"' not in DETAIL


def test_governance_keeps_current_state_visible_and_lifecycle_target_reachable():
    assert '<section class="uc-side-panel" id="governance-evidence"' in DETAIL
    assert 'data-testid="governance-status-summary"' in DETAIL
    assert 'id="governance-evidence-details"' in DETAIL
    assert 'id="governance-evidence-details" open' not in DETAIL
    assert "#status-dimensions" not in GOVERNANCE_JOURNEY
    assert "#governance-evidence" in GOVERNANCE_JOURNEY
    assert 'id="decision-history"' in DETAIL
    assert "#approval" not in WORKFLOW
    assert "#decision-history" in WORKFLOW


def test_review_entry_is_secondary_and_canonical_review_action_wins():
    assert "Lifecycle-Review" not in DETAIL
    assert "Entscheidung dokumentieren" in DETAIL
    assert "journey.next_action.key != 'pilot_start'" in DETAIL
    assert "Die Entscheidung wird im bestehenden Review dokumentiert" in NEXT_ACTION
    assert "Statusänderungen erfolgen weiterhin ausschließlich über das Review" in NEXT_ACTION


def test_disabled_role_assignments_explain_read_only_reason():
    assert "field.field.disabled" in FORM
    assert "field.name == 'business_owner'" in FORM
    assert "field.name == 'coordinator'" in FORM
    assert "Schreibgeschützt." in FORM
    assert "Nur KI-Koordinatoren können diese Zuordnung" in FORM
