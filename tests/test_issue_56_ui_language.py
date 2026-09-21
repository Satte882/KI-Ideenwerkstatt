from pathlib import Path

from ki_radar.architecture.focus import ValueStreamFocus

TEMPLATE_ROOT = Path("templates/architecture")
STATIC_JS_ROOT = Path("static/js")


def _template(name: str) -> str:
    return (TEMPLATE_ROOT / name).read_text(encoding="utf-8")


def _static_js(name: str) -> str:
    return (STATIC_JS_ROOT / name).read_text(encoding="utf-8")


def test_primary_analysis_headings_are_task_oriented():
    value_stream = _template("value_stream_detail.html")
    process_analysis = _template("process_analysis_detail.html")
    solution_form = _template("solution_option_form.html")

    assert "<strong>Zielbild und Leitplanken</strong>" in value_stream
    assert '<h2 class="h6 mb-0">Ist-Prozess und Ursachen</h2>' in process_analysis
    assert "<h2>Vertiefende Analyseinformationen</h2>" in process_analysis
    assert "<summary>Systeme und Daten</summary>" in process_analysis
    assert "<strong>Lösungsoptionen vergleichen</strong>" in process_analysis
    assert "<strong>Lösungsoption bewerten</strong>" in solution_form

    assert "<strong>TOGAF-light: Architecture Vision</strong>" not in value_stream
    assert "<strong>Business Architecture · ADM Phase B</strong>" not in process_analysis
    assert (
        "<strong>Information Systems &amp; Technology · ADM Phasen C/D</strong>"
        not in process_analysis
    )
    assert "<strong>Lösungsoptionen · ADM Phase E</strong>" not in process_analysis
    assert "<strong>Opportunities &amp; Solutions · ADM Phase E</strong>" not in solution_form


def test_methodology_remains_available_as_secondary_context():
    value_stream = _template("value_stream_detail.html")
    process_analysis = _template("process_analysis_detail.html")

    assert "Methodik: TOGAF-light, Architecture Vision (ADM Phase A)." in value_stream
    assert "Methodik: Business Architecture (ADM Phase B)." in process_analysis
    assert "Methodik: Information Systems &amp; Technology (ADM Phasen C/D)." in process_analysis
    assert "Methodik: Opportunities &amp; Solutions (ADM Phase E)." in process_analysis


def test_methodology_is_promoted_next_to_the_heading():
    navigation_js = _static_js("analysis-navigation.js")

    assert 'const marker = " Methodik: ";' in navigation_js
    assert 'label.className = "small text-muted fw-normal ms-1";' in navigation_js
    assert "label.textContent = `(${methodology})`;" in navigation_js
    assert 'heading.insertAdjacentElement("afterend", label);' in navigation_js


def test_process_analysis_action_and_focus_status_use_consistent_language():
    value_stream = _template("value_stream_detail.html")
    stage_focus = _template("stage_focus_form.html")

    assert "Prozess im Detail analysieren" in value_stream
    assert "Prozessdetailanalyse" in value_stream
    assert "Prozessdetailanalyse" in stage_focus
    assert ValueStreamFocus.Status.SELECTED.label == "Für Prozessanalyse ausgewählt"
