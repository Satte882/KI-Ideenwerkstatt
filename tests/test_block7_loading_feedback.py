from pathlib import Path


def test_solution_generation_submit_has_local_progress_feedback_and_double_submit_guard():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "js" / "copilot-submit-guard.js").read_text(encoding="utf-8")

    assert 'form[action*="/solution-generation/start/"]' in script
    assert 'form.dataset.submitted === "true"' in script
    assert 'button.setAttribute("aria-busy", "true")' in script
    assert "spinner-border spinner-border-sm" in script
    assert "KI-Entwürfe werden erstellt …" in script
    assert "KI-Generierung läuft. Das kann einige Sekunden dauern." in script
    assert 'status.setAttribute("role", "status")' in script
    assert 'status.setAttribute("aria-live", "polite")' in script
    assert "waitForPaint: true" in script
    assert script.count("window.requestAnimationFrame") >= 2
    assert "HTMLFormElement.prototype.submit.call(form)" in script
