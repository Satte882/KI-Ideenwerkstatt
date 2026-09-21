(() => {
  "use strict";

  const EXAMPLES = {
    title: "(z. B. automatische Prüfung von Eingangsrechnungen)",
    name: "(z. B. Beschaffung bis Zahlung)",
    capability: "(z. B. Source-to-Pay oder Accounts Payable)",
    business_capability: "(z. B. Supplier Sourcing oder Customer Service Management)",
    process_area: "(z. B. Eingangsrechnungsprüfung)",
    focus_rationale:
      "(z. B. hoher wirtschaftlicher Hebel, belastbare Baseline und zugängliche Daten)",
    summary:
      "(z. B. Rechnungen werden heute manuell mit Bestellung und Wareneingang abgeglichen)",
    description: "(z. B. fachlicher Kontext, heutiges Problem und erwartetes Ergebnis)",
    problem_statement:
      "(z. B. die manuelle Prüfung dauert elf Minuten je Rechnung und verursacht Rückfragen)",
    problem_context:
      "(z. B. 2.000 Rechnungen pro Monat werden manuell geprüft; fehlende Bestellbezüge verzögern die Zahlung)",
    affected_process: "(z. B. Eingangsrechnung prüfen und freigeben)",
    target_users: "(z. B. Mitarbeitende in Buchhaltung und Einkauf)",
    intended_users: "(z. B. Mitarbeitende in Buchhaltung und Einkauf)",
    intended_purpose: "(z. B. Abweichungen erkennen und zur manuellen Prüfung vorlegen)",
    users_and_scenarios:
      "(z. B. Buchhaltung prüft Standardrechnungen; Einkauf klärt Preis- und Mengenabweichungen)",
    source_systems: "(z. B. SAP S/4HANA, Outlook und SharePoint)",
    systems: "(z. B. SAP S/4HANA, Outlook und SharePoint)",
    system_context:
      "(z. B. Outlook liefert Dokumente; der Prüfservice gleicht mit SAP ab und schreibt den Status zurück)",
    system_landscape:
      "(z. B. Ist: Outlook, SharePoint und SAP; Ziel: zusätzlicher Prüfservice in Azure mit Rückgabe an SAP)",
    documents: "(z. B. Rechnung, Bestellung und Wareneingangsbeleg)",
    data_sources: "(z. B. Rechnung, Bestellung und Wareneingangsdaten aus SAP)",
    data_requirements: "(z. B. Rechnungsnummer, Bestellposition, Menge und Preis)",
    data_context:
      "(z. B. Rechnung, Bestellung und Wareneingang werden über Bestellnummer und Position verknüpft)",
    data_flows:
      "(z. B. PDF aus Outlook → Extraktion → SAP-Abgleich → Ausnahmeliste zur manuellen Freigabe)",
    interface_description: "(z. B. Bestell- und Wareneingangsdaten über eine lesende SAP-API abrufen)",
    integrations:
      "(z. B. lesende SAP-API, SharePoint-Ablage und Rückgabe des Prüfstatus an SAP)",
    integration_impact:
      "(z. B. neue lesende SAP-Schnittstelle und Rückgabe von Prüfstatus und Begründung)",
    integration_contracts:
      "(z. B. SAP-Team verantwortet die API; Buchhaltung verantwortet Freigaberegeln und Ausnahmen)",
    architecture_artifacts_url: "(z. B. Link zum Systemkontextdiagramm)",
    artifacts_url: "(z. B. Link zum Systemkontextdiagramm)",
    external_delivery_url: "(z. B. Jira-Epic oder DevOps-Backlog)",
    evidence_url: "(z. B. freigegebene Pilot-Auswertung)",
    metric_evidence_url: "(z. B. freigegebener Messbericht oder Dashboard)",
    expected_benefit: "(z. B. Prüfzeit von elf auf fünf Minuten je Rechnung senken)",
    benefit_category: "(z. B. Durchlaufzeit, Qualität, Kosten oder Risikoreduktion)",
    metric_name: "(z. B. durchschnittliche Prüfzeit je Rechnung)",
    metric_unit: "(z. B. Minuten je Rechnung)",
    metric_baseline: "(z. B. 11)",
    metric_target: "(z. B. 5)",
    metric_actual: "(z. B. 4,8)",
    metric_measurement_method:
      "(z. B. Mittelwert aus 100 zufällig ausgewählten Rechnungen über vier Wochen)",
    metric_measurement_period: "(z. B. vier Wochen nach Pilotstart)",
    baseline: "(z. B. derzeit elf Minuten Prüfzeit je Rechnung)",
    baseline_metrics: "(z. B. elf Minuten je Rechnung und fünf Rückfragen pro Woche)",
    success_criterion: "(z. B. mindestens 40 Prozent kürzere Prüfzeit bei unveränderter Fehlerquote)",
    target_value: "(z. B. höchstens fünf Minuten je Rechnung)",
    realized_result: "(z. B. durchschnittlich 4,8 Minuten je Rechnung im vierwöchigen Pilot)",
    provider: "(z. B. Microsoft)",
    product_name: "(z. B. Azure Document Intelligence)",
    model_name: "(z. B. internes Klassifikationsmodell v1)",
    one_time_cost: "(z. B. 15000)",
    recurring_cost: "(z. B. 800 pro Monat)",
    scope: "(z. B. vom Rechnungseingang bis zur Zahlungsfreigabe)",
    strategic_objective:
      "(z. B. Durchlaufzeit senken, Skontoverluste vermeiden und Entscheidungen nachvollziehbar machen)",
    stakeholders: "(z. B. Buchhaltung, Einkauf, Fachbereich, Datenschutz und IT)",
    constraints: "(z. B. SAP bleibt führendes System; Freigaben erfolgen weiterhin durch Menschen)",
    pain_points: "(z. B. manuelle Suche, Medienbrüche und wiederholte Rückfragen)",
    handoffs: "(z. B. Buchhaltung übergibt Preisabweichungen an den Einkauf)",
    bottlenecks: "(z. B. fehlende Bestellnummern verursachen Wartezeiten von zwei Arbeitstagen)",
    exceptions: "(z. B. Teilrechnungen, Gutschriften und abweichende Mengeneinheiten)",
    target_state_principles:
      "(z. B. Standardfälle automatisieren, Abweichungen transparent begründen und manuell freigeben)",
    application_impact: "(z. B. Erweiterung des bestehenden Beschaffungsportals um eine Prüfansicht)",
    technology_constraints: "(z. B. Betrieb ausschließlich in der bestehenden Azure-Umgebung)",
    risks: "(z. B. unvollständige Stammdaten können zu falschen Zuordnungen führen)",
    assumptions: "(z. B. mindestens 90 Prozent der Rechnungen enthalten eine gültige Bestellnummer)",
    dependencies: "(z. B. SAP-Schnittstelle, vollständige Stammdaten und Freigabe durch IT-Security)",
    architecture_fit:
      "(z. B. nutzt bestehende Identitäts-, Logging-, Integrations- und Betriebsstandards)",
    architecture_decisions:
      "(z. B. SAP bleibt führend; Verarbeitung erfolgt in Azure; Freigaben bleiben manuell)",
    human_oversight: "(z. B. Preisabweichungen über zehn Prozent werden manuell freigegeben)",
    logging_and_audit:
      "(z. B. Eingabedokument, erkannte Werte, Regelentscheidung und manuelle Freigabe revisionssicher protokollieren)",
    operations_and_support:
      "(z. B. Fachsupport durch Buchhaltung, technischer Betrieb durch IT; Alarm bei fehlgeschlagenen SAP-Aufrufen)",
    support_responsibility: "(z. B. fachlich Buchhaltung, technisch IT-Betrieb)",
    rationale:
      "(z. B. hoher Nutzen bei ausreichender Datenqualität und beherrschbarem Integrationsaufwand)",
    conditions: "(z. B. Vier-Augen-Prinzip, Security-Freigabe und Nachmessung nach 60 Tagen)",
    trigger: "(z. B. eine neue Rechnung geht im zentralen Postfach ein)",
    outcome: "(z. B. die Rechnung ist geprüft, verbucht und zur Zahlung freigegeben)",
    target_outcome:
      "(z. B. Standardrechnungen sind innerhalb von fünf Minuten geprüft; Abweichungen liegen begründet vor)",
    solution_outline:
      "(z. B. Dokumente extrahieren, mit SAP-Daten abgleichen und nur Abweichungen zur Prüfung vorlegen)",
    functional_requirements:
      "(z. B. Rechnung extrahieren, Bestellbezug prüfen und Abweichungen mit Begründung anzeigen)",
    non_functional_requirements:
      "(z. B. Antwortzeit unter zehn Sekunden, 99,5 Prozent Verfügbarkeit und revisionssichere Protokollierung)",
    security_privacy_requirements:
      "(z. B. Entra-ID, rollenbasierter Zugriff und Verarbeitung ausschließlich in der EU)",
    mvp_scope:
      "(z. B. PDF-Rechnungen mit Bestellnummer; ein Postfach, eine SAP-Buchungskreisgruppe und manuelle Freigabe)",
    acceptance_criteria:
      "(z. B. mindestens 95 Prozent der Standardrechnungen werden korrekt zugeordnet)",
    test_scenarios:
      "(z. B. Standardrechnung, Preisabweichung, fehlende Bestellnummer und nicht erreichbare SAP-API)",
    measurement_plan:
      "(z. B. Prüfzeit und Fehlerquote vier Wochen lang für mindestens 100 Rechnungen messen)",
    in_scope: "(z. B. PDF-Rechnungen mit vorhandener Bestellnummer)",
    out_of_scope: "(z. B. handschriftliche Belege und Rechnungen ohne Bestellung)",
    initial_backlog:
      "(z. B. Dokumenteingang anbinden; Felder extrahieren; SAP-Abgleich implementieren; Ausnahmeworkflow testen)",
    handover_notes:
      "(z. B. fachliche Ansprechpartner, offene Entscheidungen und benötigte Zugänge vor Sprintstart klären)",
  };

  const LABEL_EXAMPLES = [
    {
      pattern: /(nachweis|evidenz|messbeleg)/i,
      example: "(z. B. Link zur freigegebenen Analyse, Pilotmessung oder Auswertung)",
    },
    {
      pattern: /(architektur.*(link|diagramm)|diagramm)/i,
      example: "(z. B. Link zum Systemkontext-, Integrations- oder Datenflussdiagramm)",
    },
    {
      pattern: /(begründung|rationale)/i,
      example: "(z. B. hoher Nutzen bei tragfähiger Datenlage und beherrschbaren Risiken)",
    },
    {
      pattern: /annahme/i,
      example: "(z. B. mindestens 90 Prozent der Vorgänge enthalten die benötigte Referenznummer)",
    },
    {
      pattern: /abhängigkeit/i,
      example: "(z. B. verfügbare Schnittstelle, vollständige Stammdaten und fachliche Freigabe)",
    },
    {
      pattern: /risiko/i,
      example: "(z. B. unvollständige Daten führen zu falschen Zuordnungen oder manueller Nacharbeit)",
    },
  ];

  const TYPE_FALLBACKS = {
    email: "(z. B. vorname.nachname@unternehmen.de)",
    number: "(z. B. 15)",
    search: "(z. B. Rechnungsprüfung, UC-0042 oder Einkauf)",
    tel: "(z. B. +49 89 12345678)",
    text: "(z. B. fachlich eindeutige Bezeichnung oder kurze konkrete Angabe)",
    url: "(z. B. Link zum freigegebenen Dokument, Arbeitsergebnis oder Dashboard)",
  };

  const PLACEHOLDER_TYPES = new Set(["text", "email", "url", "tel", "number", "search"]);
  const STATE_CLASSES = [
    "field-guidance-required-empty",
    "field-guidance-optional-empty",
    "field-guidance-filled",
  ];

  function fieldName(control) {
    const rawName = control.name || control.id || "";
    const finalPart = rawName.split("-").pop() || rawName;
    return finalPart.replace(/^id_/, "");
  }

  function labelText(control) {
    if (!control.id) {
      return "";
    }
    const label = document.querySelector(`label[for="${control.id}"]`);
    return label ? label.textContent.replace(/\s*\*\s*$/, "").trim() : "";
  }

  function supportsPlaceholder(control) {
    if (control instanceof HTMLTextAreaElement) {
      return true;
    }
    return control instanceof HTMLInputElement && PLACEHOLDER_TYPES.has(control.type);
  }

  function inferredExample(control) {
    const label = labelText(control);
    const labelExample = LABEL_EXAMPLES.find(({ pattern }) => pattern.test(label));
    if (labelExample) {
      return labelExample.example;
    }
    if (control instanceof HTMLTextAreaElement) {
      return "(z. B. konkrete Ausgangslage, betroffene Schritte und erwartetes Ergebnis)";
    }
    if (control instanceof HTMLInputElement) {
      return TYPE_FALLBACKS[control.type] || TYPE_FALLBACKS.text;
    }
    return "";
  }

  function addExample(control) {
    if (!supportsPlaceholder(control) || control.hasAttribute("placeholder")) {
      return;
    }
    const name = fieldName(control);
    control.placeholder = EXAMPLES[name] || inferredExample(control);
  }

  function isEmpty(control) {
    if (control instanceof HTMLSelectElement && control.multiple) {
      return control.selectedOptions.length === 0;
    }
    return String(control.value || "").trim() === "";
  }

  function isRequired(control) {
    const fieldWrapper = control.closest("[id^='field-']");
    return (
      control.required ||
      control.getAttribute("aria-required") === "true" ||
      Boolean(fieldWrapper && fieldWrapper.classList.contains("field-attention"))
    );
  }

  function updateState(control) {
    control.classList.remove(...STATE_CLASSES);
    if (!isEmpty(control)) {
      control.classList.add("field-guidance-filled");
      return;
    }
    control.classList.add(
      isRequired(control) ? "field-guidance-required-empty" : "field-guidance-optional-empty"
    );
  }

  function isEligible(control) {
    if (control.disabled || control.readOnly) {
      return false;
    }
    if (control instanceof HTMLInputElement) {
      return !["hidden", "checkbox", "radio", "file", "submit", "button", "reset", "password"].includes(
        control.type
      );
    }
    return control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement;
  }

  function initializeForm(form) {
    if (form.method.toLowerCase() !== "post" || form.classList.contains("form-guidance-ignore")) {
      return;
    }
    const controls = form.querySelectorAll(".form-control, .form-select");
    controls.forEach((control) => {
      if (!isEligible(control)) {
        return;
      }
      addExample(control);
      updateState(control);
      control.addEventListener("input", () => updateState(control));
      control.addEventListener("change", () => updateState(control));
    });
  }

  function initialize() {
    document.querySelectorAll("form").forEach(initializeForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
