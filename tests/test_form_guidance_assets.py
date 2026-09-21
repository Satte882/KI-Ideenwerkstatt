from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_base_template_loads_form_guidance_assets():
    base_template = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert "{% static 'css/form-guidance.css' %}" in base_template
    assert "{% static 'js/form-guidance.js' %}" in base_template


def test_form_guidance_contract_covers_examples_and_dynamic_states():
    script = (ROOT / "static" / "js" / "form-guidance.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "static" / "css" / "form-guidance.css").read_text(encoding="utf-8")

    assert "(z. B. automatische Prüfung von Eingangsrechnungen)" in script
    assert "field-guidance-required-empty" in script
    assert "field-guidance-optional-empty" in script
    assert "field-guidance-filled" in script
    assert 'control.addEventListener("input"' in script
    assert 'control.addEventListener("change"' in script
    assert "control.required" in script
    assert 'form.method.toLowerCase() !== "post"' in script

    assert ".field-guidance-required-empty" in stylesheet
    assert ".field-guidance-optional-empty" in stylesheet
    assert ".field-guidance-filled" in stylesheet
    assert "::placeholder" in stylesheet
    assert ".field-error .form-control.field-guidance-filled" in stylesheet
    assert ".field-attention .form-control.field-guidance-filled" not in stylesheet


def test_form_guidance_uses_informative_examples_instead_of_repeating_labels():
    script = (ROOT / "static" / "js" / "form-guidance.js").read_text(encoding="utf-8")

    assert "kurze konkrete Angabe zu" not in script
    assert "EXAMPLES[name] || inferredExample(control)" in script
    assert "LABEL_EXAMPLES" in script
    assert "TYPE_FALLBACKS" in script

    assert "evidence_url:" in script
    assert "freigegebene Pilot-Auswertung" in script
    assert "metric_evidence_url:" in script
    assert "freigegebener Messbericht oder Dashboard" in script
    assert "artifacts_url:" in script
    assert "Link zum Systemkontextdiagramm" in script
    assert "external_delivery_url:" in script
    assert "Jira-Epic oder DevOps-Backlog" in script

    assert "architecture_decisions:" in script
    assert "SAP bleibt führend; Verarbeitung erfolgt in Azure" in script
    assert "data_flows:" in script
    assert "PDF aus Outlook → Extraktion → SAP-Abgleich" in script
    assert "dependencies:" in script
    assert "SAP-Schnittstelle, vollständige Stammdaten" in script

    assert "Link zum freigegebenen Dokument, Arbeitsergebnis oder Dashboard" in script
    assert "konkrete Ausgangslage, betroffene Schritte und erwartetes Ergebnis" in script
