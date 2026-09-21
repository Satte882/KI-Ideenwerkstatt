from pathlib import Path

CSS = Path("static/css/architecture.css").read_text(encoding="utf-8")
NAVIGATION_JS = Path("static/js/analysis-navigation.js").read_text(encoding="utf-8")


def test_architecture_grids_follow_content_instead_of_fixed_card_slots():
    assert "repeat(auto-fit, minmax(220px, 1fr))" in CSS
    assert "repeat(auto-fit, minmax(280px, 1fr))" in CSS
    assert ".architecture-summary-grid > *" in CSS
    assert "align-items: start" in CSS
    assert "min-height: 150px" not in CSS


def test_value_stream_stages_are_compact_by_default():
    assert "grid-auto-columns: clamp(270px, 30vw, 360px)" in CSS
    assert ".value-stream-stage { position: relative; min-height: 0; height: auto" in CSS
    assert "min-height: 420px" not in CSS
    assert ".kpi-strip-responsive" in CSS
    assert "repeat(auto-fit, minmax(150px, 1fr))" in CSS


def test_long_architecture_content_uses_native_keyboard_accessible_disclosures():
    assert 'document.createElement("details")' in NAVIGATION_JS
    assert 'document.createElement("summary")' in NAVIGATION_JS
    assert 'stage.querySelectorAll(":scope > .stage-facts, :scope > .stage-use-cases")' in (
        NAVIGATION_JS
    )
    assert 'document.querySelectorAll(".architecture-artifact-grid > section")' in NAVIGATION_JS
    assert "contentLength < 180" in NAVIGATION_JS
    assert 'document.querySelectorAll(".alert > ul")' in NAVIGATION_JS
    assert "Phasendetails anzeigen" in NAVIGATION_JS
    assert "Quellendetails anzeigen" in NAVIGATION_JS
    assert "summary:focus-visible" in CSS


def test_five_focus_criteria_override_the_obsolete_inline_column_count():
    assert "strip.children.length !== 5" in NAVIGATION_JS
    assert 'strip.style.removeProperty("grid-template-columns")' in NAVIGATION_JS
    assert 'strip.classList.add("kpi-strip-responsive")' in NAVIGATION_JS
